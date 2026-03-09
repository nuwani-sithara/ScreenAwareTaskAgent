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
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

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
        self.todo_result: dict = {}
        # per-step records: keyed by step id
        self.step_plans: Dict[int, dict] = {}      # hid commands + reasoning
        self.step_results: Dict[int, dict] = {}    # evaluation outcomes
        self.final_report: dict = {}

        logger.info("AgentRunRecorder: run dir → %s", self.run_dir)

    # ------------------------------------------------------------------
    def _write(self, filename: str, data: Any) -> None:
        path = self.run_dir / filename
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("AgentRunRecorder: failed to write %s — %s", filename, exc)

    # ------------------------------------------------------------------
    def record_initial_screen(self, screen_data: dict) -> None:
        self.initial_screen = screen_data
        self.latest_screen = screen_data
        self._write("perception.json", screen_data)
        self._write("latest_perception.json", screen_data)

    def record_screen(self, screen_data: dict) -> None:
        self.latest_screen = screen_data
        self._write("latest_perception.json", screen_data)

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
        }
        self._write("full_cycle.json", data)
        # Also keep latest_perception up-to-date
        self._write("latest_perception.json", self.latest_screen)


# ---------------------------------------------------------------------------
# Service endpoints (match existing microservice ports)
# ---------------------------------------------------------------------------
VISION_BASE_URL = "http://localhost:8001"
LLM_BASE_URL = "http://localhost:8002"
HID_API_URL = "http://localhost:3015/hid/command"

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
                rel_dx = target_x - cursor_x
                rel_dy = target_y - cursor_y
                payload = {
                    "type": "mouse_move",
                    "payload": {"dx": rel_dx, "dy": rel_dy},
                }
                cursor_x = target_x
                cursor_y = target_y
                logger.debug(
                    "HID mouse_move: abs(%d,%d) → rel(%d,%d)",
                    target_x, target_y, rel_dx, rel_dy,
                )
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

    try:
        # ── Phase 0: Pre-flight HID health check ────────────────────────────
        hid_health = await _check_hid_health()
        if not hid_health["ok"]:
            await emit({"type": "fatal_error", "message": hid_health["reason"]})
            return

        # ── Phase 1: Capture initial screen ─────────────────────────────────
        await emit({"type": "log", "message": "📸 Capturing initial screen…"})
        initial_screen = await _capture_screen()
        recorder.record_initial_screen(initial_screen)
        await emit({"type": "screen_captured", "phase": "initial"})

        # ── Phase 2: Generate todo list ──────────────────────────────────────
        await emit({"type": "log", "message": "🧠 Planning steps for your task…"})
        try:
            todo_result = await _plan_todo_list(initial_screen, user_task)
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
                recorder.record_screen(current_screen)

                # ── 3b. Generate HID commands ────────────────────────────────
                await emit(
                    {
                        "type": "log",
                        "message": f"🎯 Generating commands for: {step['action']}",
                    }
                )
                try:
                    hid_result = await _plan_step_hid(
                        current_screen, todo_list, step, user_task
                    )
                    hid_commands = hid_result.get("hid_commands", [])
                    reasoning = hid_result.get("reasoning", "")
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
                exec_result = await _execute_hid_commands(hid_commands)
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
                recorder.record_screen(new_screen)

                # ── 3f. Evaluate result ──────────────────────────────────────
                try:
                    evaluation = await _evaluate_step(
                        new_screen, step, user_task, todo_list
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
                    # Do NOT increment attempt — retry with the enriched context

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
        recorder.record_screen(final_screen)
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
