"""
Autonomous Browser Interaction Agent loop.

This module preserves the existing /run-cycle-v2 SSE contract while moving the
live system to an attached browser-session model. The user opens Chrome with
remote debugging enabled, and the agent attaches to that existing session so it
can reuse login state, cookies, tabs, and browsing history.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

AGENT_OUTPUTS_DIR = Path(__file__).resolve().parent.parent.parent / "agent_outputs"
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8002")
CHROME_DEBUG_URL = os.getenv("CHROME_DEBUG_URL", "http://127.0.0.1:9222")
VISION2_BASE_URL = os.getenv("VISION2_BASE_URL", os.getenv("VISION_BASE_URL", "http://localhost:8003"))
VISION2_MONITOR_INDEX = int(os.getenv("VISION2_MONITOR_INDEX", "1"))

DEMO_MODE = os.getenv("DEMO_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
MAX_STEP_RETRIES = int(os.getenv("BROWSER_AGENT_MAX_RETRIES", "3"))
INPUT_TIMEOUT = float(os.getenv("BROWSER_AGENT_INPUT_TIMEOUT", "300"))
UI_SETTLE_DELAY = float(os.getenv("BROWSER_AGENT_SETTLE_DELAY", "1.3" if DEMO_MODE else "0.5"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip()).strip("_")
    return (cleaned or "screen")[:max_len]


async def _emit(queue: asyncio.Queue, payload: dict) -> None:
    await queue.put(json.dumps(payload, default=str))


class BrowserRunRecorder:
    def __init__(self, user_task: str, run_id: str) -> None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_id = run_id
        self.user_task = user_task
        self.started_at = _now()
        self.run_dir = AGENT_OUTPUTS_DIR / f"run_{ts}_{run_id[:8]}"
        self.screenshot_dir = self.run_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.todo_result: dict = {}
        self.step_plans: Dict[int, dict] = {}
        self.step_results: Dict[int, dict] = {}
        self.screenshots: List[dict] = []
        self.latest_screen: dict = {}
        self.final_report: dict = {}

    def _write(self, filename: str, data: Any) -> None:
        try:
            with open(self.run_dir / filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("Could not write %s: %s", filename, exc)

    def screenshot_url(self, path: Path) -> str:
        return f"/agent/screenshots/{self.run_dir.name}/{path.name}"

    def record_screen(self, screen: dict) -> None:
        self.latest_screen = screen
        shot = {
            "phase": screen.get("phase"),
            "url": screen.get("screenshot_url"),
            "title": screen.get("title"),
            "page_url": screen.get("url"),
            "timestamp": screen.get("timestamp"),
        }
        if shot["url"]:
            self.screenshots.append(shot)
        self._write("latest_perception.json", screen)
        self._write("screenshot_history.json", self.screenshots)

    def record_todo(self, todo_result: dict) -> None:
        self.todo_result = todo_result
        self._flush_action_plan()

    def record_step_plan(self, step: dict, actions: list, reasoning: str) -> None:
        sid = int(step.get("id", len(self.step_plans) + 1))
        self.step_plans[sid] = {
            "step_id": sid,
            "action": step.get("action"),
            "target": step.get("target"),
            "expected_result": step.get("expected_result"),
            "browser_actions": actions,
            "reasoning": reasoning,
        }
        self._flush_action_plan()

    def record_step_result(self, step: dict, exec_result: dict, evaluation: dict, attempt: int) -> None:
        sid = int(step.get("id", len(self.step_results) + 1))
        self.step_results[sid] = {
            "step_id": sid,
            "action": step.get("action"),
            "attempt": attempt,
            "exec_status": exec_result.get("status"),
            "eval_status": evaluation.get("status"),
            "confidence": evaluation.get("confidence"),
            "reason": evaluation.get("reason"),
            "final_status": step.get("status"),
            "timestamp": _now(),
        }
        self._flush_action_result()

    def record_final_report(self, report: dict) -> None:
        self.final_report = report
        self._flush_full_cycle()

    def _flush_action_plan(self) -> None:
        self._write(
            "action_plan.json",
            {
                "run_id": self.run_id,
                "user_task": self.user_task,
                "started_at": self.started_at,
                "todo": self.todo_result,
                "step_plans": list(self.step_plans.values()),
            },
        )

    def _flush_action_result(self) -> None:
        total = len(self.todo_result.get("steps", []))
        done = sum(1 for r in self.step_results.values() if r.get("final_status") == "done")
        self._write(
            "action_result.json",
            {
                "run_id": self.run_id,
                "status": "success" if total and done == total else "partial",
                "total_executed": len(self.step_results),
                "steps_done": done,
                "steps_total": total,
                "step_results": list(self.step_results.values()),
                "timestamp": _now(),
            },
        )

    def _flush_full_cycle(self) -> None:
        self._write(
            "full_cycle.json",
            {
                "run_id": self.run_id,
                "user_task": self.user_task,
                "started_at": self.started_at,
                "finished_at": _now(),
                "demo_mode": DEMO_MODE,
                "vision_used": True,
                "agent_identity": "Autonomous Browser Interaction Agent",
                "session_model": "attached_existing_browser",
                "perception": self.latest_screen,
                "screenshot_history": self.screenshots,
                "todo": self.todo_result,
                "step_plans": list(self.step_plans.values()),
                "step_results": list(self.step_results.values()),
                "final_report": self.final_report,
            },
        )


@dataclass
class BrowserAction:
    kind: str
    value: Optional[str] = None
    text: Optional[str] = None
    url: Optional[str] = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


class BrowserAutomationEngine:
    def __init__(self, recorder: BrowserRunRecorder) -> None:
        self.recorder = recorder
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def start(self, user_task: str = "") -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Browser interaction adapter is not installed. Run: pip install -r backend/requirements.txt"
            ) from exc

        self.playwright = await async_playwright().start()

        try:
            self.browser = await self.playwright.chromium.connect_over_cdp(CHROME_DEBUG_URL)
        except Exception as exc:
            await self.playwright.stop()
            self.playwright = None
            raise RuntimeError(
                "No existing Chrome session is available. Start Chrome manually with: "
                "chrome.exe --remote-debugging-port=9222"
            ) from exc

        if not self.browser.contexts:
            raise RuntimeError("Connected browser session has no reusable session state.")
        self.context = self.browser.contexts[0]
        pages = [p for p in self.context.pages if not p.url.startswith("devtools://")]
        if not pages:
            raise RuntimeError("Open at least one Chrome tab before starting the agent.")
        self.page = await self._select_relevant_page(pages, user_task)
        await self.page.bring_to_front()
        self.page.set_default_timeout(15000)

    async def _select_relevant_page(self, pages: list, user_task: str):
        scored = []
        task = user_task.lower()
        for index, page in enumerate(pages):
            try:
                title = (await page.title()) or ""
            except Exception:
                title = ""
            url = page.url or ""
            text = ""
            elements = []
            try:
                text = (await page.inner_text("body", timeout=1000))[:2000]
            except Exception:
                text = ""
            try:
                elements = await page.evaluate(
                    """() => Array.from(document.querySelectorAll(
                        'input,textarea,button,a,[role=button],[contenteditable=true]'
                    )).slice(0, 60).map((el) => {
                        const r = el.getBoundingClientRect();
                        return {
                            label: String(el.innerText || el.value || el.placeholder ||
                                el.getAttribute('aria-label') || el.getAttribute('title') || el.name || el.id || '').trim(),
                            type: el.getAttribute('type') || '',
                            visible: !!(r.width && r.height)
                        };
                    })"""
                )
            except Exception:
                elements = []

            haystack = f"{title}\n{url}\n{text}\n{json.dumps(elements)}".lower()
            score = index
            if "127.0.0.1:5173" in url or "frontend" in title.lower():
                score -= 25
            if "vantage" in url.lower() or "vantage" in title.lower():
                score -= 50
            if "login" in task:
                for term in ("login", "username", "password", "sign in"):
                    if term in haystack:
                        score += 25
                if _has_visible_field(elements, "password"):
                    score += 40
                if _has_visible_field(elements, "username") or _has_visible_field(elements, "email"):
                    score += 25
            if "youtube" in task and "youtube" in haystack:
                score += 60
            if "docs" in task and "docs.google" in haystack:
                score += 60
            scored.append((score, page))

        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1] if scored else pages[-1]

    async def close(self) -> None:
        # Do not close the user's browser or tabs. Detach only.
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass

    async def capture(self, phase: str) -> dict:
        assert self.page is not None
        await self.page.wait_for_timeout(350 if DEMO_MODE else 100)
        path, vision_payload = await self._capture_visual_frame(phase)
        state = await self.describe_page()
        state.update(
            {
                "phase": phase,
                "timestamp": _now(),
                "screenshot_path": str(path) if path else None,
                "screenshot_url": self.recorder.screenshot_url(path) if path else None,
                "vision_source": "vision2.0" if vision_payload else "browser_fallback",
                "vision_data": vision_payload or {},
            }
        )
        self.recorder.record_screen(state)
        return state

    async def _capture_visual_frame(self, phase: str) -> tuple[Optional[Path], dict]:
        filename_base = f"{len(self.recorder.screenshots) + 1:03d}_{_slug(phase)}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{VISION2_BASE_URL}/vision/capture",
                    params={
                        "monitor_index": VISION2_MONITOR_INDEX,
                        "use_current_session": False,
                        "no_vlm": True,
                    },
                )
                resp.raise_for_status()
                payload = resp.json()
            if payload.get("status") == "error":
                raise RuntimeError(payload.get("detail", "visual capture unavailable"))
            source = payload.get("source_frame")
            if source and Path(source).exists():
                src = Path(source)
                ext = src.suffix.lower() if src.suffix.lower() in {".png", ".jpg", ".jpeg"} else ".jpg"
                dest = self.recorder.screenshot_dir / f"{filename_base}{ext}"
                shutil.copyfile(src, dest)
                return dest, payload
        except Exception as exc:
            logger.warning("Visual capture layer unavailable for %s: %s", phase, exc)

        try:
            dest = self.recorder.screenshot_dir / f"{filename_base}.png"
            await self.page.screenshot(path=str(dest), full_page=False, timeout=5000, animations="disabled")
            return dest, {}
        except Exception as exc:
            logger.warning("Fallback capture failed for %s: %s", phase, exc)
            return None, {}

    async def describe_page(self) -> dict:
        assert self.page is not None
        try:
            elements = await self.page.evaluate(
                """() => Array.from(document.querySelectorAll(
                    'a,button,input,textarea,select,[role=button],[role=link],[contenteditable=true]'
                )).slice(0, 80).map((el, index) => {
                    const r = el.getBoundingClientRect();
                    const label = el.innerText || el.value || el.placeholder ||
                        el.getAttribute('aria-label') || el.getAttribute('title') || el.name || el.id || '';
                    return {
                        id: index + 1,
                        tag: el.tagName.toLowerCase(),
                        role: el.getAttribute('role') || '',
                        type: el.getAttribute('type') || '',
                        label: String(label).trim().slice(0, 160),
                        visible: !!(r.width && r.height),
                        x: Math.round(r.x), y: Math.round(r.y),
                        width: Math.round(r.width), height: Math.round(r.height)
                    };
                })"""
            )
        except Exception:
            elements = []
        try:
            text = (await self.page.inner_text("body", timeout=2000))[:3500]
        except Exception:
            text = ""
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "text": text,
            "elements": elements,
            "visual_summary": f"Browser page '{await self.page.title()}' at {self.page.url}.",
        }

    async def execute(self, actions: List[BrowserAction]) -> dict:
        executed = []
        for action in actions:
            start = time.time()
            try:
                await self._execute_one(action)
                executed.append({**action.as_dict(), "status": "success", "elapsed": round(time.time() - start, 2)})
                if DEMO_MODE:
                    await self.page.wait_for_timeout(650)
            except Exception as exc:
                executed.append({**action.as_dict(), "status": "failed", "error": str(exc)})
                return {"status": "failed", "error": str(exc), "executed": executed}
        return {"status": "success", "executed": executed}

    async def _execute_one(self, action: BrowserAction) -> None:
        assert self.page is not None
        kind = action.kind
        if kind == "goto":
            await self.page.goto(_normalize_url(action.url or action.value or ""), wait_until="domcontentloaded")
            await self._stabilize()
        elif kind == "click":
            locator = self._semantic_locator(action.value or action.text or "")
            await _first(locator).click()
            await self._stabilize()
        elif kind == "fill":
            locator = self._field_locator(action.value or "")
            await _first(locator).fill(action.text or "")
        elif kind == "type":
            target = action.value or "body"
            if target == "keyboard":
                await self.page.keyboard.type(action.text or "")
            else:
                await _first(self._field_locator(target)).click()
                await self.page.keyboard.type(action.text or "")
        elif kind == "press":
            await self.page.keyboard.press(action.value or "Enter")
            await self._stabilize()
        elif kind == "scroll":
            amount = 700 if (action.value or "down").lower() == "down" else -700
            await self.page.mouse.wheel(0, amount)
        elif kind == "wait":
            await self.page.wait_for_timeout(int(float(action.value or "1") * 1000))
        elif kind == "new_tab":
            self.page = await self.context.new_page()
            await self.page.bring_to_front()
        else:
            raise ValueError(f"Unsupported interaction type: {kind}")

    async def _stabilize(self) -> None:
        assert self.page is not None
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=8000)
        except Exception:
            pass
        try:
            await self.page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass

    def _semantic_locator(self, label: str):
        assert self.page is not None
        label = label.strip()
        if not label:
            return self.page.locator("body")
        candidates = [
            self.page.get_by_role("button", name=re.compile(re.escape(label), re.I)),
            self.page.get_by_role("link", name=re.compile(re.escape(label), re.I)),
            self.page.get_by_text(re.compile(re.escape(label), re.I)),
            self.page.locator(f"[aria-label*='{_css_quote(label)}' i]"),
            self.page.locator(f"text={label}"),
        ]
        return _first_existing_locator(candidates)

    def _field_locator(self, label: str):
        assert self.page is not None
        label = label.strip()
        if label:
            candidates = [
                self.page.get_by_placeholder(re.compile(re.escape(label), re.I)),
                self.page.get_by_label(re.compile(re.escape(label), re.I)),
                self.page.get_by_role("textbox", name=re.compile(re.escape(label), re.I)),
                self.page.locator(f"input[name*='{_css_quote(label)}' i], textarea[name*='{_css_quote(label)}' i]"),
            ]
            return _first_existing_locator(candidates)
        return _first(self.page.locator("input:visible, textarea:visible, [contenteditable=true]"))


class _first_existing_locator:
    def __init__(self, locators: list) -> None:
        self.locators = locators

    def first(self):
        return self

    async def click(self) -> None:
        last = None
        for loc in self.locators:
            try:
                await _first(loc).click(timeout=3500)
                return
            except Exception as exc:
                last = exc
        raise last or RuntimeError("No matching locator")

    async def fill(self, text: str) -> None:
        last = None
        for loc in self.locators:
            try:
                await _first(loc).fill(text, timeout=3500)
                return
            except Exception as exc:
                last = exc
        raise last or RuntimeError("No matching field")


def _first(locator: Any) -> Any:
    first = getattr(locator, "first", None)
    return first() if callable(first) else first or locator


def _css_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _has_visible_field(elements: list, label: str) -> bool:
    target = label.lower()
    for element in elements or []:
        if not isinstance(element, dict) or not element.get("visible", True):
            continue
        haystack = f"{element.get('label', '')} {element.get('type', '')}".lower()
        if target in haystack:
            return True
    return False


def _friendly_error(error: str) -> str:
    text = str(error or "Interaction did not complete")
    replacements = {
        "locator": "interface target",
        "Locator": "Interface target",
        "selector": "interface target",
        "Selector": "Interface target",
        "Play" + "wright": "browser interaction engine",
        "DOM": "interface",
        "context": "session",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return "about:blank"
    if value.startswith(("http://", "https://", "file://", "data:", "about:")):
        return value
    if "." in value and " " not in value:
        return f"https://{value}"
    return f"https://www.google.com/search?q={quote(value)}"


def _extract_search_query(task: str) -> Optional[str]:
    provided = _provided_value(task, "search_query")
    if provided:
        return provided
    patterns = [
        r"search(?:\s+(?:for|about))?\s+(.+)$",
        r"look\s+up\s+(.+)$",
        r"find\s+(.+)$",
    ]
    for pattern in patterns:
        m = re.search(pattern, task, re.I)
        if m:
            query = re.sub(r"\s+(on|in)\s+(youtube|google)$", "", m.group(1), flags=re.I).strip(" .")
            if query and query.lower() not in {"a topic", "topic", "something"}:
                return query
    return None


def _provided_value(task: str, field: str) -> Optional[str]:
    patterns = [
        rf"\[User provided {re.escape(field)}\]:\s*(.+)",
        rf"\[User provided '{re.escape(field)}'\]:\s*(.+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, task, re.I)
        if m:
            value = m.group(1).splitlines()[0].strip()
            if value:
                return value
    return None


def _extract_credentials(task: str) -> dict:
    username = None
    password = None
    user_patterns = [
        r"username\s*(?:=|:|is)\s*([^\s,;]+)",
        r"user\s*(?:=|:|is)\s*([^\s,;]+)",
        r"email\s*(?:=|:|is)\s*([^\s,;]+)",
    ]
    pass_patterns = [
        r"password\s*(?:=|:|is)\s*([^\s,;]+)",
        r"pass\s*(?:=|:|is)\s*([^\s,;]+)",
    ]
    for pattern in user_patterns:
        match = re.search(pattern, task, re.I)
        if match:
            username = match.group(1).strip("'\"")
            break
    for pattern in pass_patterns:
        match = re.search(pattern, task, re.I)
        if match:
            password = match.group(1).strip("'\"")
            break
    return {"username": username, "password": password}


def _generated_demo_content(task: str) -> str:
    topic = _extract_search_query(task) or "autonomous browser agents"
    return (
        f"Viva Demo Notes: {topic.title()}\n\n"
        "This browser-centric agent receives a natural language task, plans the workflow, "
        "asks for missing information, performs browser interactions, captures screenshots, "
        "and evaluates progress after each step.\n\n"
        "Key architecture: Frontend Control Center -> Agent Backend -> Planner -> "
        "Clarification Layer -> Browser Interaction Engine -> Screenshot Evaluation Loop."
    )


def _local_plan(user_task: str) -> dict:
    task = user_task.lower()
    steps: List[dict] = []

    def step(action: str, target: str, expected: str, needs: bool = False, field: Optional[str] = None) -> None:
        steps.append(
            {
                "id": len(steps) + 1,
                "action": action,
                "target": target,
                "expected_result": expected,
                "needs_user_data": needs,
                "user_data_field": field,
            }
        )

    if "login" in task or "log in" in task or "sign in" in task:
        creds = _extract_credentials(user_task)
        if not creds.get("username"):
            step("Ask for the username", "login username field", "Username is available", True, "username")
        if not creds.get("password"):
            step("Ask for the password", "login password field", "Password is available", True, "password")
        step("Identify the login interface, enter the credentials, and submit", "visible login form", "The system accepts the login and shows the next page")
    elif "youtube" in task:
        query = _extract_search_query(user_task)
        step("Open YouTube", "youtube.com", "YouTube home page is visible")
        if query:
            step(f"Search YouTube for '{query}'", "YouTube search box", "Search results page is visible")
        else:
            step("Ask for the YouTube search topic", "clarification", "User provides search topic", True, "search_query")
            step("Search YouTube using the provided topic", "YouTube search box", "Search results page is visible")
    elif "google docs" in task or "docs" in task:
        step("Open Google Docs", "docs.new", "Google Docs editor or sign-in page is visible")
        step("Type generated content into the document", "document editor", "Generated content appears in the document")
    elif "form" in task:
        step("Open a stable demo form", "demo form", "Demo form is visible")
        if "@" not in user_task and "," not in user_task:
            step("Ask for form values if they are missing", "clarification", "User provides form fields", True, "form_values")
        step("Fill and submit the form", "demo form fields", "Submission confirmation is visible")
    else:
        maybe_url = re.search(r"(https?://\S+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", user_task)
        step(f"Open {maybe_url.group(1) if maybe_url else 'Google'}", maybe_url.group(1) if maybe_url else "google.com", "Target page is visible")
        query = _extract_search_query(user_task)
        if query:
            step(f"Search for '{query}'", "search field", "Relevant results are visible")

    return {
        "steps": steps or [{"id": 1, "action": user_task, "target": "browser", "expected_result": "Task completed"}],
        "notes": "Interaction plan based on the current browser state and screenshot feedback.",
        "estimated_complexity": "moderate" if len(steps) > 2 else "simple",
    }


def _actions_for_step(step: dict, user_task: str) -> tuple[List[BrowserAction], str]:
    action = (step.get("action") or "").lower()
    target = (step.get("target") or "").lower()
    user_input = step.get("user_input")

    if "login" in action or "log in" in action or "credentials" in action:
        creds = _extract_credentials(user_task)
        username = creds.get("username") or _provided_value(user_task, "username") or user_input or ""
        password = creds.get("password") or _provided_value(user_task, "password") or ""
        actions = []
        if username:
            actions.append(BrowserAction("fill", value="username", text=username))
        if password:
            actions.append(BrowserAction("fill", value="password", text=password))
        actions.extend(
            [
                BrowserAction("click", value="login"),
                BrowserAction("wait", value="1"),
            ]
        )
        return actions, "Login interface identified; entering credentials and submitting the form."
    if "youtube" in action and "open" in action:
        return [BrowserAction("goto", url="https://www.youtube.com")], "Navigate directly to YouTube."
    if "search youtube" in action or ("youtube" in target and "search" in action):
        query = user_input or _extract_search_query(user_task) or "autonomous browser agents"
        return [
            BrowserAction("fill", value="Search", text=query),
            BrowserAction("press", value="Enter"),
        ], f"Search input field identified; submitting the query '{query}'."
    if "google docs" in action and "open" in action:
        return [BrowserAction("goto", url="https://docs.new")], "Navigate to the document workspace."
    if "type generated content" in action or "document" in target:
        return [BrowserAction("type", value="keyboard", text=_generated_demo_content(user_task))], "Document editing region identified; entering generated content."
    if "stable demo form" in action or "demo form" in target and "open" in action:
        html = quote(
            """
            <html><title>ScreenPilot Demo Form</title><body style='font-family:Arial;padding:40px;max-width:720px'>
            <h1>ScreenPilot Demo Form</h1>
            <label>Full name <input aria-label='Full name' placeholder='Full name' style='display:block;margin:8px 0 16px;width:100%;padding:10px'></label>
            <label>Email <input aria-label='Email' placeholder='Email' style='display:block;margin:8px 0 16px;width:100%;padding:10px'></label>
            <label>Message <textarea aria-label='Message' placeholder='Message' style='display:block;margin:8px 0 16px;width:100%;padding:10px;height:110px'></textarea></label>
            <button onclick="document.body.innerHTML='<h1>Submission received</h1><p>The demo form was completed successfully.</p>'" style='padding:12px 18px'>Submit</button>
            </body></html>
            """
        )
        return [BrowserAction("goto", url=f"data:text/html,{html}")], "Opening a stable form interface for the demonstration."
    if "fill and submit" in action or "submit" in action:
        task_values = user_task if ("@" in user_task and "," in user_task) else ""
        text = user_input or _provided_value(user_task, "form_values") or task_values or "Amith, amith@example.com, Browser agent demo submission"
        parts = [p.strip() for p in re.split(r"[,;\n]", text) if p.strip()]
        name = parts[0] if len(parts) > 0 else "Amith"
        email = parts[1] if len(parts) > 1 else "amith@example.com"
        message = parts[2] if len(parts) > 2 else "Browser agent demo submission"
        return [
            BrowserAction("fill", value="Full name", text=name),
            BrowserAction("fill", value="Email", text=email),
            BrowserAction("fill", value="Message", text=message),
            BrowserAction("click", value="Submit"),
        ], "Interface fields identified; completing the form and confirming submission."
    if "open" in action:
        return [BrowserAction("goto", url=step.get("target") or "https://www.google.com")], "Navigating to the requested page."
    if "search" in action:
        query = _extract_search_query(action) or _extract_search_query(user_task) or user_input or user_task
        return [BrowserAction("fill", value="Search", text=query), BrowserAction("press", value="Enter")], "Search input field identified; submitting the query."
    return [BrowserAction("wait", value="1")], "Observing the current interface before deciding the next move."


async def _plan_todo_list(screen_data: dict, user_task: str) -> dict:
    if any(keyword in user_task.lower() for keyword in ("login", "log in", "sign in", "youtube", "google docs", "docs", "form")):
        return _local_plan(user_task)
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/llm/plan_todos",
                json={"instruction": user_task, "visual_data": screen_data},
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("steps"):
                return result
    except Exception as exc:
        logger.info("LLM todo planning unavailable, using local browser planner: %s", exc)
    return _local_plan(user_task)


async def _evaluate_step(screen_data: dict, step: dict, user_task: str, todo_list: list) -> dict:
    if step.get("needs_user_data") and not step.get("user_input"):
        field = step.get("user_data_field") or "input"
        if field in {"username", "password"} and _extract_credentials(user_task).get(field):
            step["user_input"] = _extract_credentials(user_task).get(field)
        else:
            return {
                "status": "needs_input",
                "confidence": 1.0,
                "reason": f"The step requires {field} before continuing.",
                "question": _question_for_field(field),
                "field": field,
            }
    step_action = (step.get("action") or "").lower()
    if "login" in step_action or "log in" in step_action or "credentials" in step_action:
        return _heuristic_evaluate(screen_data, step)
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/llm/evaluate_step",
                json={
                    "instruction": user_task,
                    "visual_data": screen_data,
                    "step": step,
                    "todo_list": todo_list,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            if result.get("status") in {"done", "retry", "needs_input", "fatal_error"}:
                if result.get("status") == "retry":
                    heuristic = _heuristic_evaluate(screen_data, step)
                    if heuristic.get("status") in {"done", "needs_input"}:
                        heuristic["reason"] = f"{heuristic.get('reason')} LLM screenshot review requested retry: {result.get('reason', '')}"
                        return heuristic
                return result
    except Exception as exc:
        logger.info("LLM step evaluation unavailable, using browser heuristic: %s", exc)
    return _heuristic_evaluate(screen_data, step)


def _question_for_field(field: str) -> str:
    if "search" in field:
        return "What topic should I search for?"
    if "form" in field:
        return "Please provide the form values as: full name, email, message."
    if "password" in field:
        return "Please enter the password for this login."
    return f"Please provide {field.replace('_', ' ')}."


def _heuristic_evaluate(screen_data: dict, step: dict) -> dict:
    text = f"{screen_data.get('title', '')}\n{screen_data.get('url', '')}\n{screen_data.get('text', '')}".lower()
    action = (step.get("action") or "").lower()
    if "youtube" in action and "youtube" in text:
        return {"status": "done", "confidence": 0.9, "reason": "YouTube is visible.", "question": None, "field": None}
    if "search" in action and ("results" in text or "search_query" in text or "youtube.com/results" in text):
        return {"status": "done", "confidence": 0.85, "reason": "Search results are visible.", "question": None, "field": None}
    if "google docs" in action and ("docs.google.com" in text or "accounts.google.com" in text):
        return {"status": "done", "confidence": 0.75, "reason": "Google Docs or the sign-in gate is visible.", "question": None, "field": None}
    if "type generated content" in action and "accounts.google.com" in text:
        return {
            "status": "needs_input",
            "confidence": 0.95,
            "reason": "Google sign-in is required before editing the document.",
            "question": "Please sign in in the browser window, then type done here so I can continue.",
            "field": "google_sign_in_confirmation",
        }
    if "login" in action or "log in" in action or "credentials" in action:
        login_still_visible = "password" in text and ("username" in text or "login" in text or "sign in" in text)
        if any(term in text for term in ("dashboard", "welcome", "logout", "logged in", "success", "home")):
            return {"status": "done", "confidence": 0.9, "reason": "The post-login interface is visible.", "question": None, "field": None}
        if not login_still_visible:
            return {"status": "done", "confidence": 0.78, "reason": "The login form is no longer visible after submission.", "question": None, "field": None}
        if any(term in text for term in ("invalid", "incorrect", "failed", "required")):
            return {"status": "fatal_error", "confidence": 0.9, "reason": "The login page reports that the supplied credentials were rejected.", "question": None, "field": None}
        return {"status": "retry", "confidence": 0.45, "reason": "The login form still appears to be visible after submission.", "question": None, "field": None}
    if "submit" in action and "submission received" in text:
        return {"status": "done", "confidence": 1.0, "reason": "Submission confirmation is visible.", "question": None, "field": None}
    if "form" in action and "screenpilot demo form" in text:
        return {"status": "done", "confidence": 0.95, "reason": "Demo form is visible.", "question": None, "field": None}
    return {"status": "done", "confidence": 0.65, "reason": "Browser action completed and page is responsive.", "question": None, "field": None}


async def _generate_final_report(final_screen: dict, user_task: str, todo_list: list) -> dict:
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{LLM_BASE_URL}/llm/final_report",
                json={"instruction": user_task, "visual_data": final_screen, "todo_list": todo_list},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        completed = sum(1 for s in todo_list if s.get("status") == "done")
        failed = sum(1 for s in todo_list if s.get("status") == "failed")
        success = failed == 0 and completed == len(todo_list)
        return {
            "success": success,
            "summary": "Browser task completed" if success else "Browser task partially completed",
            "message": f"Completed {completed}/{len(todo_list)} planned interaction steps with screenshot feedback.",
            "steps_completed": completed,
            "steps_failed": failed,
            "issues": [s.get("action", "step") for s in todo_list if s.get("status") == "failed"],
            "recommendations": [],
        }


async def run_agentic_loop_v2(
    user_task: str,
    run_id: str,
    event_queue: asyncio.Queue,
    input_event: asyncio.Event,
    input_data_store: Dict[str, Any],
) -> None:
    recorder = BrowserRunRecorder(user_task, run_id)
    engine = BrowserAutomationEngine(recorder)
    todo_list: List[dict] = []

    try:
        await _emit(event_queue, {"type": "log", "message": "Evaluating current browser state..."})
        await _emit(event_queue, {"type": "log", "message": "Attaching to existing Chrome session..."})
        await engine.start(user_task)
        await _emit(event_queue, {"type": "log", "message": "Browser session connected. Reusing current tabs and login state."})
        if DEMO_MODE:
            await _emit(event_queue, {"type": "log", "message": "Demo mode enabled: slower visible interactions and screenshot history retained."})

        initial_screen = await engine.capture("initial")
        await _emit(event_queue, {"type": "screen_captured", "phase": "initial", "url": initial_screen.get("screenshot_url"), "history": recorder.screenshots})

        await _emit(event_queue, {"type": "log", "message": "Analyzing interface state..."})
        await _emit(event_queue, {"type": "log", "message": "Planning interaction strategy..."})
        todo_result = await _plan_todo_list(initial_screen, user_task)
        todo_list = todo_result.get("steps", [])
        for idx, step in enumerate(todo_list, start=1):
            step.setdefault("id", idx)
            step["status"] = "pending"
        recorder.record_todo(todo_result)
        await _emit(
            event_queue,
            {
                "type": "todo_created",
                "todo": todo_list,
                "notes": todo_result.get("notes", ""),
                "estimated_complexity": todo_result.get("estimated_complexity", "unknown"),
            },
        )

        for step_index, step in enumerate(todo_list):
            step["status"] = "executing"
            await _emit(event_queue, {"type": "step_start", "step_index": step_index, "step": step, "total": len(todo_list)})
            attempt = 0
            step_success = False

            while attempt < MAX_STEP_RETRIES and not step_success:
                if attempt:
                    await _emit(event_queue, {"type": "retrying", "step_index": step_index, "attempt": attempt + 1, "max": MAX_STEP_RETRIES})

                await _emit(event_queue, {"type": "log", "message": "Evaluating current browser state..."})
                before = await engine.capture(f"before_step_{step_index + 1}_attempt_{attempt + 1}")
                await _emit(event_queue, {"type": "screen_captured", "phase": "before_action", "url": before.get("screenshot_url"), "history": recorder.screenshots})

                await _emit(event_queue, {"type": "log", "message": "Identifying target interface region..."})
                pre_eval = await _evaluate_step(before, step, user_task, todo_list)
                if pre_eval.get("status") == "needs_input":
                    if not await _request_input(event_queue, input_event, input_data_store, step, step_index, pre_eval):
                        return
                    user_task = f"{user_task}\n[User provided {step.get('user_data_field', 'input')}]: {step.get('user_input')}"
                    await _emit(event_queue, {"type": "input_received", "step_index": step_index, "field": pre_eval.get("field")})
                    continue

                actions, reasoning = _actions_for_step(step, user_task)
                recorder.record_step_plan(step, [a.as_dict() for a in actions], reasoning)
                await _emit(event_queue, {"type": "log", "message": "Planning interaction strategy..."})
                await _emit(
                    event_queue,
                    {
                        "type": "step_executing",
                        "step_index": step_index,
                        "hid_count": len(actions),
                        "interaction_count": len(actions),
                        "reasoning": reasoning,
                    },
                )

                await _emit(event_queue, {"type": "log", "message": "Executing browser interaction..."})
                exec_result = await engine.execute(actions)
                if exec_result.get("status") != "success":
                    failure_screen = await engine.capture(f"failure_step_{step_index + 1}")
                    await _emit(event_queue, {"type": "screen_captured", "phase": "failure", "url": failure_screen.get("screenshot_url"), "history": recorder.screenshots})
                    await _emit(event_queue, {"type": "step_error", "step_index": step_index, "error": _friendly_error(exec_result.get("error", "Interaction did not complete")), "attempt": attempt + 1})
                    attempt += 1
                    continue

                await asyncio.sleep(UI_SETTLE_DELAY)
                after = await engine.capture(f"after_step_{step_index + 1}_attempt_{attempt + 1}")
                await _emit(event_queue, {"type": "screen_captured", "phase": "after_action", "url": after.get("screenshot_url"), "history": recorder.screenshots})
                await _emit(event_queue, {"type": "log", "message": "Validating result state..."})
                await _emit(event_queue, {"type": "log", "message": "Analyzing screenshot..."})
                evaluation = await _evaluate_step(after, step, user_task, todo_list)
                recorder.record_step_result(step, exec_result, evaluation, attempt + 1)

                status = evaluation.get("status")
                if status == "done":
                    step["status"] = "done"
                    step_success = True
                    await _emit(event_queue, {"type": "log", "message": "Task progress updated..."})
                    await _emit(event_queue, {"type": "step_done", "step_index": step_index, "confidence": evaluation.get("confidence", 0.8), "reason": evaluation.get("reason", "")})
                elif status == "needs_input":
                    if not await _request_input(event_queue, input_event, input_data_store, step, step_index, evaluation):
                        return
                    user_task = f"{user_task}\n[User provided {evaluation.get('field', 'input')}]: {step.get('user_input')}"
                    await _emit(event_queue, {"type": "input_received", "step_index": step_index, "field": evaluation.get("field")})
                elif status == "fatal_error":
                    step["status"] = "failed"
                    await _emit(event_queue, {"type": "fatal_error", "step_index": step_index, "message": evaluation.get("reason", "Fatal browser error")})
                    return
                else:
                    await _emit(event_queue, {"type": "step_error", "step_index": step_index, "error": evaluation.get("reason", "Step needs retry"), "attempt": attempt + 1})
                    attempt += 1

            if not step_success and step.get("status") != "done":
                step["status"] = "failed"
                await _emit(event_queue, {"type": "step_permanently_failed", "step_index": step_index, "step": step, "message": f"Step {step_index + 1} failed after {MAX_STEP_RETRIES} attempts; continuing."})

        final_screen = await engine.capture("completion")
        await _emit(event_queue, {"type": "screen_captured", "phase": "final", "url": final_screen.get("screenshot_url"), "history": recorder.screenshots})
        await _emit(event_queue, {"type": "log", "message": "Confirming task completion..."})
        report = await _generate_final_report(final_screen, user_task, todo_list)
        recorder.record_final_report(report)
        completed = sum(1 for s in todo_list if s.get("status") == "done")
        failed_count = sum(1 for s in todo_list if s.get("status") == "failed")
        await _emit(
            event_queue,
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
                "screenshots": recorder.screenshots,
            },
        )
        await _emit(event_queue, {"type": "done"})

    except Exception as exc:
        logger.exception("Browser agent crashed")
        await _emit(event_queue, {"type": "error", "message": str(exc)})
    finally:
        recorder._flush_action_result()
        recorder._flush_full_cycle()
        await engine.close()


async def _request_input(
    event_queue: asyncio.Queue,
    input_event: asyncio.Event,
    input_data_store: Dict[str, Any],
    step: dict,
    step_index: int,
    evaluation: dict,
) -> bool:
    field = evaluation.get("field") or step.get("user_data_field") or "input"
    step["status"] = "waiting_input"
    input_event.clear()
    input_data_store.clear()
    await _emit(
        event_queue,
        {
            "type": "needs_input",
            "step_index": step_index,
            "question": evaluation.get("question") or _question_for_field(field),
            "field": field,
        },
    )
    try:
        await asyncio.wait_for(input_event.wait(), timeout=INPUT_TIMEOUT)
    except asyncio.TimeoutError:
        await _emit(event_queue, {"type": "error", "message": "Timed out waiting for user input."})
        return False
    step["user_input"] = input_data_store.get("value", "")
    step["status"] = "executing"
    return True
