"""
V2 Agentic Loop — Step-by-step execution with self-validation and user-input requests.

Loop flow (mirrors the design diagram):
  1.  Start vision stream, capture initial screen.
  2.  LLM  → todo list  (screen + task + system prompt)
  3.  For each step in todo list:
        a. Capture current screen
        b. LLM  → HID commands  (screen + todo + step + task)
        c. Execute HID commands via HID API
        d. Capture screen *after* execution
        e. LLM  → evaluate  (new screen + step + task + todo)
        f. Branch:
             "done"        → mark step complete, advance
             "retry"       → up to MAX_STEP_RETRIES, then mark failed
             "needs_input" → emit SSE event, block until user responds,
                             then retry with enriched context
             "fatal_error" → abort entire loop
  4.  Capture final screen → LLM → final report → emit to frontend.

All inter-service communication uses httpx async clients so the loop runs
entirely inside a FastAPI asyncio event-loop without blocking the server.
"""

import asyncio
import ctypes
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent output recorder — persists run artefacts to agent_outputs/
# ---------------------------------------------------------------------------
AGENT_OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "agent_outputs"


class AgentRunRecorder:
    """
    Writes structured JSON artefacts for one V2 run into:
        agent_outputs/run_<YYYYMMDD_HHMMSS>/
            perception.json        – raw initial screen / vision data
            latest_perception.json – most-recent screen data (updated each step)
            action_plan.json       – todo list + HID commands per step
            action_result.json     – execution outcomes per step
            full_cycle.json        – complete merged record of the whole run
    """

    def __init__(self, user_task: str, run_id: str) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = AGENT_OUTPUTS_DIR / f"run_{ts}"
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.user_task = user_task
        self.run_id = run_id
        self.started_at = datetime.now(timezone.utc).isoformat()

        # Mutable accumulators
        self.initial_screen: dict = {}
        self.latest_screen: dict = {}
        self.session_memory = RunPerceptionMemory(self.run_dir, run_id, user_task)
        self.todo_result: dict = {}
        # per-step records: keyed by step id
        self.step_plans: Dict[int, dict] = {}      # hid commands + reasoning
        self.step_results: Dict[int, dict] = {}    # evaluation outcomes
        self.final_report: dict = {}

    def _normalize_perception(self, screen_data: dict) -> dict:
        """Normalize various vision service response wrappers into a
        consistent perception dict that contains `elements` and related keys.

        This is a compatibility shim for older callers that expected the
        vision payload at the top level. Do not change semantics of the
        original data — only prefer nested `vision_data`/`vision_output`.
        """
        if not isinstance(screen_data, dict):
            return screen_data or {}

        # Common wrappers used by the vision service
        if "vision_data" in screen_data and isinstance(screen_data["vision_data"], dict):
            return screen_data["vision_data"]
        if "vision_output" in screen_data and isinstance(screen_data["vision_output"], dict):
            return screen_data["vision_output"]
        # Some endpoints return the final payload under 'vision' or 'final'
        if "vision" in screen_data and isinstance(screen_data["vision"], dict):
            return screen_data["vision"]
        if "final" in screen_data and isinstance(screen_data["final"], dict):
            return screen_data["final"]

        # Already in expected shape (has elements) — return as-is
        if "elements" in screen_data or "element_count" in screen_data:
            return screen_data

        # Fallback: return original object so nothing is lost
        return screen_data

    # ------------------------------------------------------------------
    def _write(self, filename: str, data: Any) -> None:
        path = self.run_dir / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("AgentRunRecorder: failed to write %s — %s", filename, exc)

    # ------------------------------------------------------------------
    def record_initial_screen(self, screen_data: dict) -> dict:
        norm = self._normalize_perception(screen_data)
        merged = self.session_memory.merge_screen(norm)
        self.initial_screen = merged
        self.latest_screen = merged
        self._write("perception.json", merged)
        self._write("latest_perception.json", merged)
        return merged

    def record_screen(self, screen_data: dict) -> dict:
        norm = self._normalize_perception(screen_data)
        merged = self.session_memory.merge_screen(norm)
        self.latest_screen = merged
        self._write("latest_perception.json", merged)
        return merged

    def record_todo(self, todo_result: dict) -> None:
        self.todo_result = todo_result
        # Write an early action_plan.json with the planned steps
        self._flush_action_plan()

    def record_step_plan(self, step: dict, hid_commands: list, reasoning: str) -> None:
        sid = step.get("id", 0)
        self.step_plans[sid] = {
            "step_id": sid,
            "action": step.get("action"),
            "target": step.get("target"),
            "expected_result": step.get("expected_result"),
            "hid_commands": hid_commands,
            "reasoning": reasoning,
        }
        self._flush_action_plan()

    def record_step_result(
        self,
        step: dict,
        exec_result: dict,
        evaluation: dict,
        attempt: int,
    ) -> None:
        sid = step.get("id", 0)
        self.step_results[sid] = {
            "step_id": sid,
            "action": step.get("action"),
            "attempt": attempt,
            "exec_status": exec_result.get("status"),
            "eval_status": evaluation.get("status"),
            "confidence": evaluation.get("confidence"),
            "reason": evaluation.get("reason"),
            "final_status": step.get("status"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._flush_action_result()

    def record_final_report(self, report: dict) -> None:
        self.final_report = report
        self._flush_full_cycle()

    # ------------------------------------------------------------------
    def _flush_action_plan(self) -> None:
        data = {
            "run_id": self.run_id,
            "user_task": self.user_task,
            "started_at": self.started_at,
            "todo": self.todo_result,
            "step_plans": list(self.step_plans.values()),
        }
        self._write("action_plan.json", data)

    def _flush_action_result(self) -> None:
        done = sum(1 for r in self.step_results.values() if r.get("final_status") == "done")
        total = len(self.todo_result.get("steps", []))
        data = {
            "run_id": self.run_id,
            "status": "success" if done == total and total > 0 else "partial",
            "total_executed": len(self.step_results),
            "steps_done": done,
            "steps_total": total,
            "step_results": list(self.step_results.values()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._write("action_result.json", data)

    def _flush_full_cycle(self) -> None:
        data = {
            "run_id": self.run_id,
            "user_task": self.user_task,
            "started_at": self.started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "vision_used": True,
            "perception": self.initial_screen,
            "todo": self.todo_result,
            "step_plans": list(self.step_plans.values()),
            "step_results": list(self.step_results.values()),
            "final_report": self.final_report,
            "session_memory": self.session_memory.snapshot(),
        }
        self._write("full_cycle.json", data)
        # Also keep latest_perception up-to-date
        self._write("latest_perception.json", self.latest_screen)


class RunPerceptionMemory:
    """
    Run-scoped fallback memory for repeated one-shot perception calls.

    Tracks the best-known bbox for each logical element and emits a merged
    screen payload that includes cached fallbacks when the latest frame misses
    a target.
    """

    def __init__(
        self,
        run_dir: Path,
        run_id: str,
        user_task: str,
        stale_after_misses: int = 2,
        confidence_floor: float = 0.40,
        decay_per_miss: float = 0.90,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.run_id = run_id
        self.user_task = user_task
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.started_at
        self.stale_after_misses = max(1, int(stale_after_misses))
        self.confidence_floor = max(0.0, min(1.0, float(confidence_floor)))
        self.decay_per_miss = max(0.0, min(1.0, float(decay_per_miss)))
        self.frame_index = 0
        self.known_elements: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return str(value or "").strip().lower()

    def _key(self, element: Dict[str, Any]) -> str:
        element_type = self._normalize_text(element.get("type"))
        label = self._normalize_text(element.get("label"))
        element_id = self._normalize_text(element.get("id"))
        if label and element_type:
            return f"{element_type}:{label}"
        if label:
            return f"label:{label}"
        if element_id:
            return f"id:{element_id}"
        return f"type:{element_type or 'unknown'}"

    @staticmethod
    def _copy_bbox(element: Dict[str, Any]) -> list[float] | None:
        bbox = element.get("bbox") or element.get("frame_bbox")
        if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
            return None
        try:
            return [float(v) for v in bbox]
        except Exception:
            return None

    def _persist(self, snapshot: Dict[str, Any]) -> None:
        try:
            path = self.run_dir / "session_memory.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("RunPerceptionMemory: failed to write session_memory.json — %s", exc)

    def update(self, screen_data: dict) -> Dict[str, Any]:
        elements = screen_data.get("current_elements") or screen_data.get("elements") or []
        current_keys = set()
        current_elements: List[Dict[str, Any]] = []
        self.updated_at = datetime.now(timezone.utc).isoformat()

        for element in elements:
            if not isinstance(element, dict):
                continue
            key = self._key(element)
            current_keys.add(key)
            bbox = self._copy_bbox(element)
            confidence = float(element.get("confidence", 0.0) or 0.0)
            record = self.known_elements.get(key)

            if record is None:
                record = {
                    "element_key": key,
                    "element_type": str(element.get("type") or ""),
                    "label": str(element.get("label") or ""),
                    "bbox": bbox,
                    "confidence": confidence,
                    "source": str(element.get("source") or "vision"),
                    "first_seen_frame": screen_data.get("frame_name"),
                    "last_seen_frame": screen_data.get("frame_name"),
                    "first_seen_index": self.frame_index,
                    "last_seen_index": self.frame_index,
                    "first_seen_at": self.updated_at,
                    "last_seen_at": self.updated_at,
                    "seen_count": 1,
                    "miss_count": 0,
                    "stale": False,
                    "cached": False,
                }
                self.known_elements[key] = record
            else:
                if bbox is not None and (record.get("bbox") is None or confidence >= float(record.get("confidence", 0.0))):
                    record["bbox"] = bbox
                if confidence >= float(record.get("confidence", 0.0)):
                    record["confidence"] = confidence
                if element.get("source"):
                    record["source"] = str(element.get("source"))
                record["element_type"] = str(element.get("type") or record.get("element_type") or "")
                record["label"] = str(element.get("label") or record.get("label") or "")
                record["last_seen_frame"] = screen_data.get("frame_name")
                record["last_seen_index"] = self.frame_index
                record["last_seen_at"] = self.updated_at
                record["seen_count"] = int(record.get("seen_count", 0)) + 1
                record["miss_count"] = 0
                record["stale"] = False
                record["cached"] = False

            normalized = dict(element)
            normalized["session_memory_key"] = key
            normalized["cached"] = False
            current_elements.append(normalized)

        for key, record in self.known_elements.items():
            if key in current_keys:
                continue
            record["miss_count"] = int(record.get("miss_count", 0)) + 1
            record["cached"] = True
            if record["miss_count"] >= self.stale_after_misses:
                record["stale"] = True
            confidence = float(record.get("confidence", 0.0) or 0.0)
            if confidence > 0.0:
                record["confidence"] = max(self.confidence_floor, round(confidence * self.decay_per_miss, 4))

        self.frame_index += 1
        snapshot = self.snapshot(screen_data=screen_data, current_elements=current_elements)
        self._persist(snapshot)
        return snapshot

    def merge_screen(self, screen_data: dict) -> dict:
        snapshot = self.update(screen_data)
        merged = dict(screen_data)
        merged["current_elements"] = snapshot["current_elements"]
        merged["resolved_elements"] = snapshot["resolved_elements"]
        merged["session_memory"] = snapshot
        merged["elements"] = snapshot["resolved_elements"] or snapshot["current_elements"] or merged.get("elements", [])
        merged["element_count"] = len(merged.get("elements", []))
        return merged

    def snapshot(self, screen_data: Optional[dict] = None, current_elements: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        current_elements = current_elements or []
        current_keys = {self._key(elem) for elem in current_elements if isinstance(elem, dict)}
        resolved_elements: List[Dict[str, Any]] = []

        for element in current_elements:
            if isinstance(element, dict):
                resolved_elements.append(dict(element))

        for key, record in self.known_elements.items():
            if key in current_keys or record.get("stale") or not record.get("bbox"):
                continue
            resolved_elements.append(
                {
                    "id": f"memory_{key}",
                    "type": record.get("element_type", ""),
                    "label": record.get("label", ""),
                    "description": "Cached from an earlier frame in the same run",
                    "state": "cached",
                    "bbox": list(record.get("bbox") or []),
                    "confidence": float(record.get("confidence", 0.0) or 0.0),
                    "source": record.get("source", "session_memory"),
                    "last_seen_frame": record.get("last_seen_frame"),
                    "last_seen_index": record.get("last_seen_index"),
                    "stale": True,
                    "cached": True,
                    "session_memory_key": key,
                }
            )

        return {
            "run_id": self.run_id,
            "user_task": self.user_task,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "stale_after_misses": self.stale_after_misses,
            "confidence_floor": self.confidence_floor,
            "decay_per_miss": self.decay_per_miss,
            "frame_index": self.frame_index,
            "known_elements": self.known_elements,
            "current_elements": current_elements,
            "resolved_elements": resolved_elements,
            "screen_data": screen_data or {},
        }


# ---------------------------------------------------------------------------
# Service endpoints (match existing microservice ports)
# ---------------------------------------------------------------------------
VISION_BASE_URL = "http://localhost:8001"
LLM_BASE_URL = "http://localhost:8002"
HID_API_URL = "http://localhost:3015/hid/command"


def _remap_to_absolute_coords(screen_data: dict) -> dict:
    """
    Remap each element's dx/dy to use absolute webcam-frame coordinates
    (frame_dx / frame_dy) instead of screen-relative coordinates.

    The vision pipeline produces both:
      dx/dy       -- screen-relative (offset from cropped screen top-left)
      frame_dx/dy -- absolute (offset from full webcam frame top-left)

    The LLM uses dx/dy values to generate HID mouse_move commands, so we must
    replace dx/dy with frame_dx/dy before sending vision data to the LLM so
    that generated coordinates are correct for the physical HID device.
    """
    return _remap_coordinate_payload(screen_data)


def _remap_coordinate_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return [_remap_coordinate_payload(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    remapped: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in ("elements", "current_elements", "resolved_elements") and isinstance(value, list):
            remapped[key] = [_remap_element_coords(elem) for elem in value]
        else:
            remapped[key] = _remap_coordinate_payload(value)
    return remapped


def _remap_element_coords(elem: Any) -> Any:
    if not isinstance(elem, dict):
        return elem

    new_elem = dict(elem)
    frame_dx = new_elem.get("frame_dx")
    frame_dy = new_elem.get("frame_dy")
    if frame_dx is not None:
        try:
            new_elem["dx"] = int(round(float(frame_dx)))
        except Exception:
            pass
    if frame_dy is not None:
        try:
            new_elem["dy"] = int(round(float(frame_dy)))
        except Exception:
            pass

    bbox = new_elem.get("bbox")
    if ("dx" not in new_elem or "dy" not in new_elem) and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            x1, y1, x2, y2 = (float(v) for v in bbox)
            new_elem["dx"] = int(round((x1 + x2) * 0.5))
            new_elem["dy"] = int(round((y1 + y2) * 0.5))
        except Exception:
            pass

    return new_elem


def _get_cursor_position() -> tuple[int, int]:
    """Best-effort current cursor position on Windows."""
    try:
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        point = POINT()
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
            return int(point.x), int(point.y)
    except Exception:
        pass
    return 0, 0

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
MAX_STEP_RETRIES = 3        # maximum execution attempts per step
UI_SETTLE_DELAY = 1.5       # seconds to wait for UI to react after HID commands
INPUT_TIMEOUT = 300.0       # seconds to wait for user-provided data


# =============================================================================
# Vision helpers
# =============================================================================

async def _start_vision_stream() -> dict:
    """Start the continuous webcam/screen capture stream (non-blocking)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{VISION_BASE_URL}/vision/start",
                params={
                    "camera_index": 0,
                    "save_interval": 1,
                    "provider": "gemini",
                },
            )
            return resp.json()
        except Exception as exc:
            logger.error("Vision start failed: %s", exc)
            return {"status": "error", "detail": str(exc)}


async def _stop_vision_stream() -> dict:
    """Stop the vision stream (best-effort cleanup)."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(f"{VISION_BASE_URL}/vision/stop")
            return resp.json()
        except Exception as exc:
            logger.error("Vision stop failed: %s", exc)
            return {"status": "error"}


async def _capture_screen() -> dict:
    """
    Take a completely standalone single-shot capture.
    Does NOT require a streaming session — creates its own disposable session,
    processes one frame, and returns.  This avoids accumulating hundreds of
    background stream frames on disk.
    """
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{VISION_BASE_URL}/vision/capture",
                params={
                    "camera_index": 0,
                    "provider": "gemini",
                    "use_current_session": False,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("Screen capture failed: %s", exc)
            return {"elements": [], "error": str(exc)}


# =============================================================================
# LLM planning helpers  (proxy through LLM microservice on port 8002)
# =============================================================================

async def _plan_todo_list(screen_data: dict, user_task: str) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/llm/plan_todos",
            json={"instruction": user_task, "visual_data": screen_data},
        )
        resp.raise_for_status()
        return resp.json()


async def _plan_step_hid(
    screen_data: dict,
    todo_list: List[dict],
    step: dict,
    user_task: str,
) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/llm/plan_step_hid",
            json={
                "instruction": user_task,
                "visual_data": screen_data,
                "todo_list": todo_list,
                "current_step": step,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _evaluate_step(
    new_screen: dict,
    step: dict,
    user_task: str,
    todo_list: List[dict],
) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/llm/evaluate_step",
            json={
                "instruction": user_task,
                "visual_data": new_screen,
                "step": step,
                "todo_list": todo_list,
            },
        )
        resp.raise_for_status()
        return resp.json()


async def _generate_final_report(
    final_screen: dict,
    user_task: str,
    todo_list: List[dict],
) -> dict:
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{LLM_BASE_URL}/llm/final_report",
            json={
                "instruction": user_task,
                "visual_data": final_screen,
                "todo_list": todo_list,
            },
        )
        resp.raise_for_status()
        return resp.json()


# =============================================================================
# HID helpers
# =============================================================================

HID_STATUS_URL = "http://localhost:3015/hid/status"


async def _check_hid_health() -> dict:
    """
    Returns {"ok": True} if the HID server AND device are reachable,
    or {"ok": False, "reason": "<msg>"} if not.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(HID_STATUS_URL)
            data = resp.json()
            if not data.get("connected"):
                return {
                    "ok": False,
                    "reason": (
                        "HID device not connected. "
                        "Please plug in your ESP32-S3 HID device via USB and ensure "
                        "the correct COM port is available."
                    ),
                }
            return {"ok": True}
        except Exception as exc:
            return {
                "ok": False,
                "reason": (
                    f"HID API server is not running on port 3015 ({exc}). "
                    "Start it with: cd hid/api-server && node dist/server.js"
                ),
            }


# =============================================================================
# HID execution
# =============================================================================

async def _execute_hid_commands(commands: List[dict]) -> dict:
    """
    Execute a sequence of HID commands with small human-paced delays between
    each command.

    The LLM generates mouse_move with dx/dy as ABSOLUTE screen pixel coordinates
    (e.g. dx=323, dy=247 means "click at screen position (323, 247)").  The HID
    device, however, only understands *relative* movement reports.  We reconcile
    this by:
      1. Sending a large negative move to push the cursor to the screen's top-left
         corner (0, 0).
      2. Tracking a virtual cursor position starting at (0, 0).
      3. For every mouse_move command, computing the relative delta from the
         tracked position before forwarding to the HID API.

    Returns {"status": "success"} or {"status": "failed", ...}.
    """
    RESET_MOVE = {"type": "mouse_move", "payload": {"dx": -32767, "dy": -32767}}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Push cursor to screen top-left so our virtual tracker starts at (0, 0).
        try:
            reset_resp = await client.post(HID_API_URL, json=RESET_MOVE)
            if reset_resp.status_code == 503:
                body = reset_resp.json()
                msg = body.get("message") or body.get("error") or "Device offline"
                logger.error("HID cursor-reset: device offline — %s", msg)
                return {"status": "failed", "error": f"HID device offline: {msg}", "failed_at": -1}
            await asyncio.sleep(0.08)
        except Exception as exc:
            logger.error("HID cursor-reset failed: %s", exc)
            return {"status": "failed", "error": str(exc), "failed_at": -1}

        cursor_x: int = 0
        cursor_y: int = 0

        for idx, cmd in enumerate(commands):
            cmd_type = cmd.get("cmd")

            if cmd_type == "mouse_move":
                # LLM provides absolute screen coords — convert to relative delta.
                target_x = int(cmd.get("dx", 0))
                target_y = int(cmd.get("dy", 0))

                # Break large moves into smaller steps to improve accuracy on HID devices.
                max_step = 80  # pixels per HID move chunk
                rel_dx = target_x - cursor_x
                rel_dy = target_y - cursor_y

                # If move is small, send single command
                if abs(rel_dx) <= max_step and abs(rel_dy) <= max_step:
                    payloads = [
                        {"type": "mouse_move", "payload": {"dx": rel_dx, "dy": rel_dy, "smooth": bool(cmd.get("smooth", False))}}
                    ]
                else:
                    # Chunk the movement
                    steps = max(1, int(max(abs(rel_dx), abs(rel_dy)) / float(max_step)) )
                    payloads = []
                    for s in range(1, steps + 1):
                        step_dx = int(round(rel_dx * (s / steps))) - int(round(rel_dx * ((s - 1) / steps)))
                        step_dy = int(round(rel_dy * (s / steps))) - int(round(rel_dy * ((s - 1) / steps)))
                        payloads.append({"type": "mouse_move", "payload": {"dx": step_dx, "dy": step_dy, "smooth": bool(cmd.get("smooth", False))}})

                # Send each payload sequentially and update virtual cursor
                for p in payloads:
                    try:
                        resp = await client.post(HID_API_URL, json=p)
                        if resp.status_code == 503:
                            body = resp.json()
                            msg = body.get("message") or body.get("error") or "Device offline"
                            logger.error("HID command device offline: %s", msg)
                            return {"status": "failed", "error": f"HID device offline: {msg}", "failed_at": idx}
                        resp.raise_for_status()
                        logger.info("HID [%d/%d] mouse_move chunk → %d", idx + 1, len(commands), resp.status_code)
                    except Exception as exc:
                        logger.error("HID mouse_move chunk failed: %s", exc)
                        return {"status": "failed", "error": str(exc), "failed_at": idx}
                    # Update virtual cursor by the chunk
                    cursor_x += int(p["payload"].get("dx", 0))
                    cursor_y += int(p["payload"].get("dy", 0))
                    await asyncio.sleep(0.04)
                # Done handling mouse_move, skip default send below
                continue
            else:
                payload = {
                    "type": cmd_type,
                    "payload": {k: v for k, v in cmd.items() if k not in ("cmd", "meta")},
                }

            try:
                resp = await client.post(HID_API_URL, json=payload)
                if resp.status_code == 503:
                    body = resp.json()
                    msg = body.get("message") or body.get("error") or "Device offline"
                    logger.error("HID command %d device offline: %s", idx + 1, msg)
                    return {"status": "failed", "error": f"HID device offline: {msg}", "failed_at": idx}
                resp.raise_for_status()
                logger.info(
                    "HID [%d/%d] %s → %d", idx + 1, len(commands), cmd_type, resp.status_code
                )
            except Exception as exc:
                logger.error("HID command %d failed: %s", idx + 1, exc)
                return {"status": "failed", "error": str(exc), "failed_at": idx}
            await asyncio.sleep(0.2)

    return {"status": "success", "total": len(commands)}


async def _execute_hid_commands_v2(commands: List[dict]) -> dict:
    """
    Corrected HID executor that uses the real cursor position as the anchor
    and does not force the pointer to the top-left corner.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        cursor_x, cursor_y = _get_cursor_position()

        for idx, cmd in enumerate(commands):
            cmd_type = cmd.get("cmd")

            if cmd_type == "mouse_move":
                target_x = int(cmd.get("dx", 0))
                target_y = int(cmd.get("dy", 0))

                max_step = 80
                rel_dx = target_x - cursor_x
                rel_dy = target_y - cursor_y

                if abs(rel_dx) <= max_step and abs(rel_dy) <= max_step:
                    payloads = [
                        {"type": "mouse_move", "payload": {"dx": rel_dx, "dy": rel_dy, "smooth": bool(cmd.get("smooth", False))}}
                    ]
                else:
                    steps = max(1, int(max(abs(rel_dx), abs(rel_dy)) / float(max_step)))
                    payloads = []
                    for s in range(1, steps + 1):
                        step_dx = int(round(rel_dx * (s / steps))) - int(round(rel_dx * ((s - 1) / steps)))
                        step_dy = int(round(rel_dy * (s / steps))) - int(round(rel_dy * ((s - 1) / steps)))
                        payloads.append(
                            {
                                "type": "mouse_move",
                                "payload": {
                                    "dx": step_dx,
                                    "dy": step_dy,
                                    "smooth": bool(cmd.get("smooth", False)),
                                },
                            }
                        )

                for p in payloads:
                    try:
                        resp = await client.post(HID_API_URL, json=p)
                        if resp.status_code == 503:
                            body = resp.json()
                            msg = body.get("message") or body.get("error") or "Device offline"
                            logger.error("HID command device offline: %s", msg)
                            return {"status": "failed", "error": f"HID device offline: {msg}", "failed_at": idx}
                        resp.raise_for_status()
                    except Exception as exc:
                        logger.error("HID mouse_move chunk failed: %s", exc)
                        return {"status": "failed", "error": str(exc), "failed_at": idx}
                    cursor_x += int(p["payload"].get("dx", 0))
                    cursor_y += int(p["payload"].get("dy", 0))
                    await asyncio.sleep(0.04)
                continue

            payload = {
                "type": cmd_type,
                "payload": {k: v for k, v in cmd.items() if k not in ("cmd", "meta")},
            }

            try:
                resp = await client.post(HID_API_URL, json=payload)
                if resp.status_code == 503:
                    body = resp.json()
                    msg = body.get("message") or body.get("error") or "Device offline"
                    logger.error("HID command %d device offline: %s", idx + 1, msg)
                    return {"status": "failed", "error": f"HID device offline: {msg}", "failed_at": idx}
                resp.raise_for_status()
            except Exception as exc:
                logger.error("HID command %d failed: %s", idx + 1, exc)
                return {"status": "failed", "error": str(exc), "failed_at": idx}
            await asyncio.sleep(0.2)

    return {"status": "success", "total": len(commands)}


def _extract_point_from_element(element: Dict[str, Any]) -> Optional[tuple[int, int]]:
    """Return the best click point for a detected element, if available."""
    if not isinstance(element, dict):
        return None

    for x_key, y_key in (("dx", "dy"), ("x", "y"), ("cx", "cy")):
        x = element.get(x_key)
        y = element.get(y_key)
        if x is not None and y is not None:
            try:
                return int(round(float(x))), int(round(float(y)))
            except Exception:
                pass

    bbox = element.get("bbox")
    if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
        try:
            x1, y1, x2, y2 = (float(v) for v in bbox)
            return int(round((x1 + x2) * 0.5)), int(round((y1 + y2) * 0.5))
        except Exception:
            return None

    return None


def _get_candidate_elements(screen_data: dict) -> List[Dict[str, Any]]:
    """Return the most relevant visible elements for click-based fallback."""
    if not isinstance(screen_data, dict):
        return []

    for key in ("current_elements", "resolved_elements", "elements"):
        value = screen_data.get(key)
        if isinstance(value, list) and value:
            return [item for item in value if isinstance(item, dict)]
    return []


def _build_click_candidate_targets(
    screen_data: dict,
    step: dict,
    hid_commands: List[dict],
    user_task: str,
    max_candidates: int = 3,
) -> List[Dict[str, Any]]:
    """
    Build an ordered list of possible click targets for a HID step.

    The first candidate is always the planner's chosen coordinate. Other
    plausible interactive elements from the current screen are then added so
    the executor can try multiple targets when the UI exposes more than one
    likely input.
    """
    candidates: List[Dict[str, Any]] = []
    seen_points: set[tuple[int, int]] = set()

    def add_candidate(x: int, y: int, label: str, source: str, score: float) -> None:
        point = (int(x), int(y))
        if point in seen_points:
            return
        seen_points.add(point)
        candidates.append(
            {
                "x": point[0],
                "y": point[1],
                "label": label,
                "source": source,
                "score": float(score),
            }
        )

    primary_move = next(
        (
            cmd
            for cmd in hid_commands
            if isinstance(cmd, dict) and cmd.get("cmd") == "mouse_move"
        ),
        None,
    )
    primary_point: Optional[tuple[int, int]] = None
    if isinstance(primary_move, dict):
        try:
            primary_point = (
                int(round(float(primary_move.get("dx", 0)))),
                int(round(float(primary_move.get("dy", 0)))),
            )
            add_candidate(primary_point[0], primary_point[1], "planned target", "hid_plan", 1000.0)
        except Exception:
            primary_point = None

    elements = _get_candidate_elements(screen_data)
    if not elements:
        return candidates

    step_text = " ".join(
        str(part or "")
        for part in (
            step.get("action"),
            step.get("target"),
            step.get("expected_result"),
            user_task,
        )
    ).lower()
    typing_intent = any(token in step_text for token in ("type", "search", "input", "text", "query"))
    click_intent = any(token in step_text for token in ("click", "press", "focus", "open"))
    keywords = [token for token in re.findall(r"[a-z0-9]+", step_text) if len(token) > 2]

    for element in elements:
        point = _extract_point_from_element(element)
        if point is None:
            continue

        element_type = str(element.get("type") or "").strip().lower()
        label = str(element.get("label") or element.get("text") or "").strip()
        description = str(element.get("description") or "").strip()
        combined = f"{element_type} {label} {description}".lower()

        interactive_types = {
            "input",
            "textbox",
            "text_field",
            "search",
            "button",
            "link",
            "tab",
        }
        if element_type and element_type not in interactive_types:
            continue

        confidence = float(element.get("confidence", 0.0) or 0.0)
        score = confidence

        if typing_intent and element_type in {"input", "textbox", "search", "text_field"}:
            score += 3.0
        if click_intent and element_type in {"button", "link", "tab"}:
            score += 1.5

        for keyword in keywords:
            if keyword in combined:
                score += 0.4

        if primary_point is not None and point == primary_point:
            score += 5.0

        add_candidate(point[0], point[1], label or element_type or "element", element_type or "screen", score)

    candidates.sort(key=lambda item: (-item["score"], item["x"], item["y"]))
    return candidates[:max_candidates]


def _inject_click_target(hid_commands: List[dict], x: int, y: int) -> List[dict]:
    """Return a copy of hid_commands with the first mouse_move replaced."""
    updated: List[dict] = []
    replaced = False

    for cmd in hid_commands:
        if not replaced and isinstance(cmd, dict) and cmd.get("cmd") == "mouse_move":
            new_cmd = dict(cmd)
            new_cmd["dx"] = int(x)
            new_cmd["dy"] = int(y)
            updated.append(new_cmd)
            replaced = True
        else:
            updated.append(dict(cmd) if isinstance(cmd, dict) else cmd)

    return updated


# =============================================================================
# Main V2 loop
# =============================================================================

async def run_agentic_loop_v2(
    user_task: str,
    run_id: str,
    event_queue: asyncio.Queue,
    input_event: asyncio.Event,
    input_data_store: Dict[str, Any],
) -> None:
    """
    Full V2 agentic loop.

    Emits JSON-serialised event dicts to ``event_queue``.
    Suspends on ``input_event`` when the LLM requests user data; the
    caller's HTTP endpoint must set the event and populate
    ``input_data_store["value"]`` to resume execution.

    Parameters
    ----------
    user_task:        Natural-language task description from the user.
    run_id:           Unique identifier for this run (for input routing).
    event_queue:      asyncio.Queue – events are consumed and streamed as SSE.
    input_event:      asyncio.Event – set externally when user supplies data.
    input_data_store: dict – populated externally with {"value": "..."}.
    """

    async def emit(event: dict) -> None:
        await event_queue.put(json.dumps(event))

    recorder = AgentRunRecorder(user_task, run_id)

    async def _attempt_coordinate_fix_and_recheck(evaluation: dict, step: dict) -> dict:
        """If evaluation suggests coordinate updates, parse and try a direct click once.

        Returns the new evaluation dict after performing the click and re-evaluating,
        or the original evaluation if no coord fix was performed.
        """
        # Avoid repeated coord-fix attempts for the same step
        if step.get("_coord_fix_tried"):
            return evaluation

        # Search in recommendations or reason for a coordinate pair like (79, 54)
        candidates = []
        if isinstance(evaluation.get("recommendations"), list):
            candidates.extend(evaluation.get("recommendations"))
        if evaluation.get("reason"):
            candidates.append(evaluation.get("reason"))

        import re
        for text in candidates:
            if not text:
                continue
            m = re.search(r"\(\s*(\d{1,5})\s*,\s*(\d{1,5})\s*\)", str(text))
            if m:
                x = int(m.group(1))
                y = int(m.group(2))
                logger.info("Parsed recommended coordinates (%d, %d) from evaluation", x, y)

                # Build HID click commands and execute them
                click_cmds = [
                    {"cmd": "mouse_move", "meta": {"commandId": "coord_fix"}, "dx": x, "dy": y, "smooth": True},
                    {"cmd": "mouse_click", "meta": {"commandId": "coord_fix"}, "button": "left"},
                ]

                step["_coord_fix_tried"] = True
                exec_result = await _execute_hid_commands_v2(click_cmds)
                if exec_result.get("status") == "failed":
                    logger.warning("Coordinate-fix click failed: %s", exec_result.get("error"))
                    return evaluation

                # Wait briefly for UI reaction, capture and re-evaluate
                await asyncio.sleep(UI_SETTLE_DELAY)
                new_screen = await _capture_screen()
                new_screen = recorder.record_screen(new_screen)

                try:
                    new_eval = await _evaluate_step(new_screen, step, user_task, todo_list)
                    logger.info("Re-evaluation after coord-fix: %s", new_eval.get("status"))
                    return new_eval
                except Exception as exc:
                    logger.error("Re-evaluation after coord-fix failed: %s", exc)
                    return evaluation

        return evaluation

    async def _execute_with_candidate_targets(
        current_screen: dict,
        step: dict,
        hid_commands: List[dict],
        step_index: int,
        attempt: int,
    ) -> dict:
        """
        Try a multi-target HID execution pass when the current screen exposes
        more than one plausible click target.

        Returns a small control dict:
            {
              "handled": bool,
              "step_success": bool,
              "increment_attempt": bool,
              "abort": bool,
            }
        """
        nonlocal user_task

        candidate_targets = _build_click_candidate_targets(
            current_screen, step, hid_commands, user_task
        )
        if len(candidate_targets) <= 1:
            return {"handled": False}

        for candidate_index, candidate in enumerate(candidate_targets):
            if candidate_index > 0:
                await emit(
                    {
                        "type": "alternate_target",
                        "step_index": step_index,
                        "attempt": attempt + 1,
                        "candidate_index": candidate_index + 1,
                        "candidate_total": len(candidate_targets),
                        "label": candidate.get("label", "element"),
                        "x": candidate["x"],
                        "y": candidate["y"],
                        "source": candidate.get("source", "screen"),
                    }
                )
                await emit(
                    {
                        "type": "log",
                        "message": (
                            f"↩️ Trying alternate target {candidate_index + 1}/"
                            f"{len(candidate_targets)}: {candidate.get('label', 'element')} "
                            f"at ({candidate['x']}, {candidate['y']})"
                        ),
                    }
                )
                await asyncio.sleep(0.35)

            candidate_hid_commands = _inject_click_target(
                hid_commands, candidate["x"], candidate["y"]
            )
            exec_result = await _execute_hid_commands_v2(candidate_hid_commands)
            if exec_result.get("status") == "failed":
                if candidate_index < len(candidate_targets) - 1:
                    logger.info(
                        "Candidate target (%d, %d) failed; trying next target: %s",
                        candidate["x"],
                        candidate["y"],
                        exec_result.get("error"),
                    )
                    continue

                await emit(
                    {
                        "type": "step_error",
                        "step_index": step_index,
                        "error": exec_result.get("error", "HID execution failed"),
                        "attempt": attempt + 1,
                    }
                )
                return {"handled": True, "increment_attempt": True}

            await asyncio.sleep(UI_SETTLE_DELAY)

            await emit({"type": "log", "message": f"🔍 Validating step {step_index + 1}..."})
            new_screen = await _capture_screen()
            new_screen = recorder.record_screen(new_screen)

            try:
                evaluation = await _evaluate_step(
                    _remap_to_absolute_coords(new_screen), step, user_task, todo_list
                )
            except Exception as exc:
                logger.error("Step evaluation error: %s", exc)
                evaluation = {
                    "status": "retry",
                    "confidence": 0.0,
                    "reason": f"Evaluation service error: {exc}",
                }

            status = evaluation.get("status", "retry")
            confidence = evaluation.get("confidence", 0.0)
            reason = evaluation.get("reason", "")
            recorder.record_step_result(step, exec_result, evaluation, attempt + 1)

            if status == "done":
                step["status"] = "done"
                await emit(
                    {
                        "type": "step_done",
                        "step_index": step_index,
                        "confidence": confidence,
                        "reason": reason,
                    }
                )
                return {"handled": True, "step_success": True}

            if status == "needs_input":
                question = evaluation.get("question") or "Please provide the required information"
                field = evaluation.get("field") or "input"
                step["status"] = "waiting_input"

                input_event.clear()
                input_data_store.clear()

                await emit(
                    {
                        "type": "needs_input",
                        "step_index": step_index,
                        "question": question,
                        "field": field,
                    }
                )

                try:
                    await asyncio.wait_for(input_event.wait(), timeout=INPUT_TIMEOUT)
                except asyncio.TimeoutError:
                    await emit(
                        {
                            "type": "error",
                            "message": "Timed out waiting for user input (5-minute limit).",
                        }
                    )
                    return {"handled": True, "abort": True}

                user_input = input_data_store.get("value", "")
                step["user_input"] = user_input
                user_task = f"{user_task}\n[User provided '{field}']: {user_input}"
                step["status"] = "executing"

                await emit({"type": "input_received", "step_index": step_index, "field": field})
                return {"handled": True, "increment_attempt": True}

            if status == "fatal_error":
                step["status"] = "failed"
                await emit(
                    {
                        "type": "fatal_error",
                        "step_index": step_index,
                        "message": f"Fatal error at step {step_index + 1}: {reason}",
                    }
                )
                return {"handled": True, "abort": True}

            if candidate_index < len(candidate_targets) - 1:
                await emit(
                    {
                        "type": "log",
                        "message": (
                            f"Candidate target ({candidate['x']}, {candidate['y']}) did not "
                            "validate; trying next target."
                        ),
                    }
                )
                continue

            await emit(
                {
                    "type": "step_error",
                    "step_index": step_index,
                    "error": reason or "Step did not succeed",
                    "attempt": attempt + 1,
                }
            )

            try:
                new_eval = await _attempt_coordinate_fix_and_recheck(evaluation, step)
                if new_eval is not None and new_eval.get("status") != evaluation.get("status"):
                    evaluation = new_eval
                    status = evaluation.get("status", "retry")
                    confidence = evaluation.get("confidence", 0.0)
                    reason = evaluation.get("reason", "")
                    recorder.record_step_result(step, exec_result, evaluation, attempt + 1)
                    if status == "done":
                        step["status"] = "done"
                        await emit(
                            {
                                "type": "step_done",
                                "step_index": step_index,
                                "confidence": confidence,
                                "reason": reason,
                            }
                        )
                        return {"handled": True, "step_success": True}
            except Exception as exc:
                logger.error("Coord-fix attempt failed: %s", exc)

            return {"handled": True, "increment_attempt": True}

        return {"handled": True, "increment_attempt": True}

    try:
        # ── Phase 0: Pre-flight HID health check ────────────────────────────
        hid_health = await _check_hid_health()
        if not hid_health["ok"]:
            await emit({"type": "fatal_error", "message": hid_health["reason"]})
            return

        # ── Phase 1: Capture initial screen ─────────────────────────────────
        await emit({"type": "log", "message": "📸 Capturing initial screen…"})
        initial_screen = await _capture_screen()
        initial_screen = recorder.record_initial_screen(initial_screen)
        await emit({"type": "screen_captured", "phase": "initial"})

        # ── Phase 2: Generate todo list ──────────────────────────────────────
        await emit({"type": "log", "message": "🧠 Planning steps for your task…"})
        try:
            todo_result = await _plan_todo_list(_remap_to_absolute_coords(initial_screen), user_task)
        except Exception as exc:
            await emit({"type": "error", "message": f"Planning failed: {exc}"})
            return

        todo_list: List[dict] = todo_result.get("steps", [])
        notes: str = todo_result.get("notes", "")

        if not todo_list:
            await emit(
                {"type": "error", "message": "Could not generate a plan. Try rephrasing the task."}
            )
            return

        for step in todo_list:
            step["status"] = "pending"

        recorder.record_todo(todo_result)

        await emit(
            {
                "type": "todo_created",
                "todo": todo_list,
                "notes": notes,
                "estimated_complexity": todo_result.get("estimated_complexity", "unknown"),
            }
        )

        # ── Phase 3: Execute each step ───────────────────────────────────────
        for step_index, step in enumerate(todo_list):
            step["status"] = "executing"
            await emit(
                {
                    "type": "step_start",
                    "step_index": step_index,
                    "step": step,
                    "total": len(todo_list),
                }
            )

            attempt = 0
            step_success = False

            while attempt < MAX_STEP_RETRIES and not step_success:

                # Announce retry (skip on first attempt)
                if attempt > 0:
                    await emit(
                        {
                            "type": "retrying",
                            "step_index": step_index,
                            "attempt": attempt + 1,
                            "max": MAX_STEP_RETRIES,
                        }
                    )
                    await asyncio.sleep(1.5)

                # ── 3a. Capture fresh screen for this step ───────────────────
                await emit(
                    {"type": "log", "message": f"📸 Screen snapshot for step {step_index + 1}…"}
                )
                current_screen = await _capture_screen()
                current_screen = recorder.record_screen(current_screen)

                # ── 3b. Generate HID commands ────────────────────────────────
                await emit(
                    {
                        "type": "log",
                        "message": f"🎯 Generating commands for: {step['action']}",
                    }
                )
                try:
                    hid_result = await _plan_step_hid(
                        _remap_to_absolute_coords(current_screen), todo_list, step, user_task
                    )
                    hid_commands = hid_result.get("hid_commands", [])
                    reasoning = hid_result.get("reasoning", "")
                    # If LLM failed to produce hid_commands but returned action_steps,
                    # attempt to convert them locally to avoid blocking the loop.
                    if not hid_commands and hid_result.get("action_steps"):
                        try:
                            from llm.hid_step_generator import HIDStepGenerator

                            logger.info("LLM returned no hid_commands — converting action_steps locally")
                            converter = HIDStepGenerator()
                            hid_commands = converter.convert_actions_to_hid(hid_result.get("action_steps", []))
                            reasoning += " | Converted action_steps -> hid_commands locally"
                        except Exception as exc:
                            logger.warning("Local conversion of action_steps failed: %s", exc)

                    recorder.record_step_plan(step, hid_commands, reasoning)
                except Exception as exc:
                    await emit(
                        {
                            "type": "step_error",
                            "step_index": step_index,
                            "error": f"HID planning failed: {exc}",
                            "attempt": attempt + 1,
                        }
                    )
                    attempt += 1
                    continue

                if not hid_commands:
                    await emit(
                        {
                            "type": "step_error",
                            "step_index": step_index,
                            "error": "LLM returned no HID commands for this step",
                            "attempt": attempt + 1,
                        }
                    )
                    attempt += 1
                    continue

                await emit(
                    {
                        "type": "step_executing",
                        "step_index": step_index,
                        "hid_count": len(hid_commands),
                        "reasoning": reasoning,
                    }
                )

                # ── 3c. Execute HID commands ─────────────────────────────────
                candidate_result = await _execute_with_candidate_targets(
                    current_screen, step, hid_commands, step_index, attempt
                )
                if candidate_result.get("abort"):
                    return
                if candidate_result.get("handled"):
                    if candidate_result.get("step_success"):
                        step_success = True
                    if candidate_result.get("increment_attempt"):
                        attempt += 1
                    continue

                exec_result = await _execute_hid_commands_v2(hid_commands)
                if exec_result.get("status") == "failed":
                    await emit(
                        {
                            "type": "step_error",
                            "step_index": step_index,
                            "error": exec_result.get("error", "HID execution failed"),
                            "attempt": attempt + 1,
                        }
                    )
                    attempt += 1
                    continue

                # ── 3d. Wait for UI to settle ────────────────────────────────
                await asyncio.sleep(UI_SETTLE_DELAY)

                # ── 3e. Capture screen after execution ───────────────────────
                await emit(
                    {"type": "log", "message": f"🔍 Validating step {step_index + 1}…"}
                )
                new_screen = await _capture_screen()
                new_screen = recorder.record_screen(new_screen)

                # ── 3f. Evaluate result ──────────────────────────────────────
                try:
                    evaluation = await _evaluate_step(
                        _remap_to_absolute_coords(new_screen), step, user_task, todo_list
                    )
                except Exception as exc:
                    logger.error("Step evaluation error: %s", exc)
                    evaluation = {
                        "status": "retry",
                        "confidence": 0.0,
                        "reason": f"Evaluation service error: {exc}",
                    }

                status = evaluation.get("status", "retry")
                confidence = evaluation.get("confidence", 0.0)
                reason = evaluation.get("reason", "")

                # Record outcome regardless of branch taken
                recorder.record_step_result(step, exec_result, evaluation, attempt + 1)

                # ── Branch ───────────────────────────────────────────────────
                if status == "done":
                    step["status"] = "done"
                    step_success = True
                    await emit(
                        {
                            "type": "step_done",
                            "step_index": step_index,
                            "confidence": confidence,
                            "reason": reason,
                        }
                    )

                elif status == "needs_input":
                    question = evaluation.get("question") or "Please provide the required information"
                    field = evaluation.get("field") or "input"
                    step["status"] = "waiting_input"

                    # Reset the shared event so we can await it cleanly
                    input_event.clear()
                    input_data_store.clear()

                    await emit(
                        {
                            "type": "needs_input",
                            "step_index": step_index,
                            "question": question,
                            "field": field,
                        }
                    )

                    try:
                        await asyncio.wait_for(input_event.wait(), timeout=INPUT_TIMEOUT)
                    except asyncio.TimeoutError:
                        await emit(
                            {
                                "type": "error",
                                "message": "Timed out waiting for user input (5-minute limit).",
                            }
                        )
                        return

                    user_input = input_data_store.get("value", "")
                    step["user_input"] = user_input
                    # Enrich the task context so subsequent LLM calls are aware
                    user_task = f"{user_task}\n[User provided '{field}']: {user_input}"
                    step["status"] = "executing"

                    await emit(
                        {"type": "input_received", "step_index": step_index, "field": field}
                    )
                    # Increment attempt so needs_input cannot loop indefinitely
                    attempt += 1

                elif status == "fatal_error":
                    step["status"] = "failed"
                    await emit(
                        {
                            "type": "fatal_error",
                            "step_index": step_index,
                            "message": f"Fatal error at step {step_index + 1}: {reason}",
                        }
                    )
                    # Abort the entire loop
                    return

                else:  # "retry" or unrecognised
                    await emit(
                        {
                            "type": "step_error",
                            "step_index": step_index,
                            "error": reason or "Step did not succeed",
                            "attempt": attempt + 1,
                        }
                    )

                    # If evaluation suggests coordinate adjustments, attempt a one-time coord-fix
                    try:
                        new_eval = await _attempt_coordinate_fix_and_recheck(evaluation, step)
                        # If re-evaluation returned a different status, use it
                        if new_eval is not None and new_eval.get("status") != evaluation.get("status"):
                            evaluation = new_eval
                            status = evaluation.get("status", "retry")
                            confidence = evaluation.get("confidence", 0.0)
                            reason = evaluation.get("reason", "")
                            # Record updated evaluation outcome
                            recorder.record_step_result(step, exec_result, evaluation, attempt + 1)
                            if status == "done":
                                step["status"] = "done"
                                step_success = True
                                await emit({"type": "step_done", "step_index": step_index, "confidence": confidence, "reason": reason})
                                break
                    except Exception as exc:
                        logger.error("Coord-fix attempt failed: %s", exc)

                    # Still retrying — increment attempt
                    attempt += 1

            # Exhausted retries without success
            if not step_success and step.get("status") not in ("done",):
                step["status"] = "failed"
                await emit(
                    {
                        "type": "step_permanently_failed",
                        "step_index": step_index,
                        "step": step,
                        "message": (
                            f"⚠️ Step {step_index + 1} failed after {MAX_STEP_RETRIES} "
                            "attempts — continuing with remaining steps."
                        ),
                    }
                )

        # ── Phase 4: Final report ────────────────────────────────────────────
        await emit({"type": "log", "message": "📊 Generating final report…"})
        final_screen = await _capture_screen()
        final_screen = recorder.record_screen(final_screen)
        await emit({"type": "screen_captured", "phase": "final"})

        try:
            report = await _generate_final_report(final_screen, user_task, todo_list)
        except Exception as exc:
            logger.error("Final report generation failed: %s", exc)
            done_count = sum(1 for s in todo_list if s.get("status") == "done")
            report = {
                "success": done_count == len(todo_list),
                "summary": f"Completed {done_count}/{len(todo_list)} steps",
                "message": f"Task finished with {done_count}/{len(todo_list)} steps completed.",
                "steps_completed": done_count,
                "steps_failed": len(todo_list) - done_count,
                "issues": [],
                "recommendations": [],
            }

        recorder.record_final_report(report)

        completed = sum(1 for s in todo_list if s.get("status") == "done")
        failed_count = sum(1 for s in todo_list if s.get("status") == "failed")

        await emit(
            {
                "type": "final_report",
                "report": report.get("message", "Task complete."),
                "success": report.get("success", completed == len(todo_list)),
                "summary": report.get("summary", ""),
                "steps_completed": completed,
                "steps_failed": failed_count,
                "issues": report.get("issues", []),
                "recommendations": report.get("recommendations", []),
                "todo": todo_list,
            }
        )

        await emit({"type": "done"})

    except Exception as exc:
        logger.exception("V2 agentic loop crashed")
        await emit({"type": "error", "message": f"Agent crashed: {exc}"})

    finally:
        # Flush whatever was collected even on crash
        recorder._flush_action_result()
        recorder._flush_full_cycle()
