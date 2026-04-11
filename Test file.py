"""
AI Service — Supports Azure OpenAI and Google Gemini
Provider is selected via AI_PROVIDER env variable.
"""

import os
import json
import re
import httpx
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

# ─── Prompts ──────────────────────────────────────────────────────

STEP_BREAKDOWN_PROMPT = """You are a QA automation expert. Break down the user's natural language test description into precise, sequential browser actions.

RULES:
- Each step must be a single atomic browser action
- Include assertions/verifications as separate steps
- Use clear, specific descriptions
- Include expected values for assertions
- First step should always be navigation if a URL context is given
- Think about what a manual tester would do step by step

IMPORTANT — CUSTOM DROPDOWNS:
Modern UI frameworks (MUI, Bootstrap, Angular Material, Ant Design) do NOT use native <select> elements. Their dropdowns require TWO steps:
1. Click the dropdown trigger to open it
2. Click the option from the opened list

When the test involves selecting from a dropdown:
  WRONG: {"action": "select", "target": "category", "value": "Electronics"}
  RIGHT:
    {"step": N, "action": "click", "description": "Click Category dropdown to open it", "target": "Category dropdown"}
    {"step": N+1, "action": "click", "description": "Select Electronics from dropdown list", "target": "Electronics option"}

IMPORTANT — MODALS AND DIALOGS:
After clicking a button that opens a modal/dialog, add a wait step before interacting with modal contents:
    {"step": N, "action": "click", "description": "Click Create New button", "target": "Create New button"}
    {"step": N+1, "action": "wait", "description": "Wait for dialog to appear", "value": "1"}
    {"step": N+2, "action": "fill", "description": "Fill name in dialog", "target": "Name field", "value": "Test"}

IMPORTANT — AFTER FORM SUBMISSIONS:
After clicking submit/save/create/delete buttons, add a wait step for the response:
    {"step": N, "action": "click", "description": "Click Submit", "target": "Submit button"}
    {"step": N+1, "action": "wait", "description": "Wait for response", "value": "2"}
    {"step": N+2, "action": "assert_visible", "description": "Verify success message", "target": "success message"}

OUTPUT FORMAT - respond ONLY with a JSON array, no markdown, no explanation:
[
  {"step": 1, "action": "navigate", "description": "Navigate to login page", "target": "/login"},
  {"step": 2, "action": "fill", "description": "Enter email address", "target": "email field", "value": "test@example.com"},
  {"step": 3, "action": "click", "description": "Click the login button", "target": "login button"},
  {"step": 4, "action": "wait", "description": "Wait for page to load", "value": "2"},
  {"step": 5, "action": "assert_url", "description": "Verify redirected to dashboard", "expected": "/dashboard"}
]

Valid actions: navigate, click, fill, select, check, uncheck, hover, press_key, upload, assert_text, assert_visible, assert_url, assert_element_count, wait
"""

PICK_ELEMENT_PROMPT = """You are a browser automation expert. Given a YAML snapshot of a web page and a step description, identify the correct element ref to interact with.

RULES:
- Pick the SINGLE best matching element ref from the snapshot
- Consider the step description, element roles, names, labels, and surrounding context
- If the step says "first" or mentions order, pick the first matching element
- If multiple similar elements exist (like multiple "Add to Cart" buttons), pick based on context
- If the step is an assertion, identify the element to assert against
- If no matching element exists, respond with ref: null

OUTPUT FORMAT - respond ONLY with JSON, no markdown:
{"ref": "e15", "confidence": "high", "reasoning": "Short explanation of why this element matches"}
"""

ASSERTION_PROMPT = """You are a QA automation expert generating Robot Framework Browser library assertions.

Given a YAML snapshot and an assertion step, generate the correct RF Browser assertion keyword.

AVAILABLE ASSERTION KEYWORDS:
- Get Text    <locator>    ==    <expected>        (exact text match)
- Get Text    <locator>    *=    <expected>        (contains text)
- Get Url    ==    <expected>                       (exact URL)
- Get Url    *=    <expected>                       (URL contains)
- Get Element States    <locator>    contains    visible
- Get Element States    <locator>    contains    enabled
- Get Element States    <locator>    contains    checked
- Get Element Count    <locator>    ==    <count>
- Get Title    ==    <expected>

LOCATOR SELECTION — use this priority from the snapshot element attributes:
1. [data-testid="value"]     — always prefer if exists
2. id=value                   — if meaningful, not auto-generated (skip mat-input-7, :r1:, css-1abc)
3. role=type[name="value"]    — accessible and stable
4. text=visible text          — for buttons/links
5. [placeholder="value"]     — for inputs
6. [aria-label="value"]      — when no visible text
7. css=semantic-selector      — stable classes/attributes only

OUTPUT FORMAT - respond ONLY with JSON, no markdown:
{"rf_keyword": "Get Text", "locator": "[data-testid=\\"welcome-msg\\"]", "operator": "*=", "expected_value": "Welcome", "full_line": "    Get Text    [data-testid=\\"welcome-msg\\"]    *=    Welcome"}
"""


# ─── Provider Interface ──────────────────────────────────────────

class AIProvider:
    """Base class for AI providers."""

    async def call(self, system_prompt: str, user_message: str) -> str:
        raise NotImplementedError


class AzureOpenAIProvider(AIProvider):
    """Azure OpenAI GPT-4o provider."""

    def __init__(self):
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

        if not self.api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is not set in .env")
        if not self.endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is not set in .env")

        self.url = (
            f"{self.endpoint}/openai/deployments/{self.deployment}"
            f"/chat/completions?api-version={self.api_version}"
        )

    async def call(self, system_prompt: str, user_message: str) -> str:
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


class GeminiProvider(AIProvider):
    """Google Gemini provider."""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in .env")

        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models"
            f"/{self.model}:generateContent?key={self.api_key}"
        )

    async def call(self, system_prompt: str, user_message: str) -> str:
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\n---\n\n{user_message}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


# ─── AI Service (uses configured provider) ───────────────────────

class AIService:
    def __init__(self):
        provider_name = os.getenv("AI_PROVIDER", "azure_openai").lower()

        if provider_name == "azure_openai":
            self.provider = AzureOpenAIProvider()
            self.provider_display = "Azure OpenAI"
        elif provider_name == "gemini":
            self.provider = GeminiProvider()
            self.provider_display = "Gemini"
        else:
            raise ValueError(
                f"Unknown AI_PROVIDER: '{provider_name}'. "
                f"Use 'azure_openai' or 'gemini'"
            )

        print(f"[AI Service] Using provider: {self.provider_display}")

    async def _call(self, system_prompt: str, user_message: str) -> str:
        """Make an AI call and clean the response."""
        content = await self.provider.call(system_prompt, user_message)

        # Strip markdown fences if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    async def break_into_steps(self, nlp_input: str, start_url: str) -> list[dict]:
        """Break NLP test description into sequential steps."""
        user_msg = f'Test description: "{nlp_input}"\nStarting URL: {start_url}\n\nBreak this into precise sequential browser actions.'

        result = await self._call(STEP_BREAKDOWN_PROMPT, user_msg)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Failed to parse AI response: {result[:300]}")

    async def pick_element(self, snapshot_content: str, step: dict) -> dict:
        """Pick the correct element ref from a snapshot for a given step."""
        user_msg = f"STEP: {json.dumps(step)}\n\nPAGE SNAPSHOT:\n{snapshot_content}"

        result = await self._call(PICK_ELEMENT_PROMPT, user_msg)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"ref": None, "confidence": "low", "reasoning": "Failed to parse response"}

    async def generate_assertion(self, snapshot_content: str, step: dict) -> dict:
        """Generate RF Browser assertion for a verification step."""
        user_msg = f"ASSERTION STEP: {json.dumps(step)}\n\nPAGE SNAPSHOT:\n{snapshot_content}"

        result = await self._call(ASSERTION_PROMPT, user_msg)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "rf_keyword": "Log",
                "full_line": f'    Log    Assertion could not be generated for: {step.get("description", "unknown")}',
            }





-------app.py--------------


"""
NLP Test Generator — Standalone FastAPI Server
Run: uvicorn app:app --reload --host 0.0.0.0 --port 8000

Prerequisites:
  npm install -g @playwright/cli@latest
  playwright-cli install
  pip install fastapi uvicorn httpx python-dotenv websockets
"""

import asyncio
import base64
import glob
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from ai_service import AIService
from playwright_parser import assemble_robot_file, playwright_to_rf

load_dotenv()

# ─── App Setup ────────────────────────────────────────────────────

app = FastAPI(title="NLP Test Generator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Configuration ────────────────────────────────────────────────

PLAYWRIGHT_CLI = os.getenv("PLAYWRIGHT_CLI_PATH", "playwright-cli")
WORKSPACE_DIR = Path(os.getenv("NLP_WORKSPACE", "/tmp/nlp-test-workspaces"))
GENERATED_TESTS_DIR = Path("./generated_tests")
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_TESTS_DIR.mkdir(parents=True, exist_ok=True)

ai_service = AIService()


# ─── Subprocess Helper ────────────────────────────────────────────

async def run_cli(
    command: str,
    session: str = "default",
    cwd: str = "",
    timeout: float = 30.0,
) -> dict:
    """Execute a playwright-cli command and return parsed output."""
    full_cmd = f"{PLAYWRIGHT_CLI} -s={session} {command}"
    work_dir = cwd or str(WORKSPACE_DIR)

    print(f"  [CLI] {full_cmd}")

    try:
        proc = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=work_dir,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        return {"stdout": "", "stderr": "Command timed out", "returncode": -1}

    stdout_str = stdout.decode("utf-8", errors="replace")
    stderr_str = stderr.decode("utf-8", errors="replace")

    # Extract snapshot file path
    snapshot_file = None
    for line in stdout_str.split("\n"):
        match = re.search(r"(\.playwright-cli/[^\s\]]+\.yml)", line)
        if match:
            snapshot_file = os.path.join(work_dir, match.group(1))

    # Extract screenshot file path
    screenshot_file = None
    for line in stdout_str.split("\n"):
        match = re.search(r"(\.playwright-cli/[^\s\]]+\.png)", line)
        if match:
            screenshot_file = os.path.join(work_dir, match.group(1))

    return {
        "stdout": stdout_str,
        "stderr": stderr_str,
        "returncode": proc.returncode,
        "snapshot_file": snapshot_file,
        "screenshot_file": screenshot_file,
    }


def read_file_content(path: str) -> str:
    """Read file content safely."""
    try:
        with open(path, "r") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return ""


def find_latest_file(directory: str, pattern: str) -> Optional[str]:
    """Find most recent file matching glob pattern."""
    files = sorted(glob.glob(os.path.join(directory, pattern)), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def file_to_base64(path: str) -> Optional[str]:
    """Read file and return base64 string."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except (FileNotFoundError, IOError):
        return None


def extract_playwright_code(stdout: str) -> Optional[str]:
    """Extract playwright_code line from CLI output."""
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("await page.") or line.startswith("page."):
            return line
    return None


# ─── Orchestrator ─────────────────────────────────────────────────

class Orchestrator:
    """Manages the NLP → playwright-cli → RF pipeline with WebSocket streaming."""

    def __init__(self, session_id: str, ws: WebSocket):
        self.session_id = session_id
        self.ws = ws
        self.workspace = str(WORKSPACE_DIR / session_id)
        self.cli_dir = os.path.join(self.workspace, ".playwright-cli")
        self.paused = False
        self.stopped = False
        self.rf_lines: list[str] = []
        self.steps: list[dict] = []

        os.makedirs(self.workspace, exist_ok=True)

    async def send(self, msg: dict):
        """Send message to client."""
        try:
            await self.ws.send_json(msg)
        except Exception:
            pass

    async def wait_if_paused(self):
        """Block while paused."""
        while self.paused and not self.stopped:
            await asyncio.sleep(0.3)

    async def screenshot(self) -> Optional[str]:
        """Take screenshot and return base64."""
        result = await run_cli("screenshot", self.session_id, self.workspace)
        path = result.get("screenshot_file") or find_latest_file(self.cli_dir, "*.png")
        return file_to_base64(path) if path else None

    async def snapshot(self) -> str:
        """Take snapshot and return YAML content."""
        result = await run_cli("snapshot", self.session_id, self.workspace)
        path = result.get("snapshot_file") or find_latest_file(self.cli_dir, "*.yml")
        return read_file_content(path) if path else ""

    async def execute_step(self, step: dict, index: int) -> dict:
        """Execute a single test step. Returns result dict."""

        action = step.get("action", "")
        description = step.get("description", "")

        await self.send({
            "type": "step_start",
            "index": index,
            "description": description,
            "action": action,
        })

        try:
            # ── Navigate ──────────────────────────────
            if action == "navigate":
                target = step.get("target", "")
                await run_cli(f"goto {target}", self.session_id, self.workspace)
                await asyncio.sleep(1.5)  # wait for page load
                pw_code = f"page.goto('{target}')"
                rf_line = f"    Go To    {target}"

            # ── Wait ──────────────────────────────────
            elif action == "wait":
                duration = step.get("value", "2")
                await asyncio.sleep(float(duration))
                rf_line = f"    Sleep    {duration}s"
                pw_code = f"page.waitForTimeout({int(float(duration) * 1000)})"

            # ── Assertions ────────────────────────────
            elif action.startswith("assert"):
                snapshot_content = await self.snapshot()
                assertion = await ai_service.generate_assertion(snapshot_content, step)
                rf_line = assertion.get("full_line", f"    # Assertion: {description}")
                pw_code = f"// Assertion: {description}"

            # ── Interactive actions ───────────────────
            else:
                # Get snapshot for element picking
                snapshot_content = await self.snapshot()

                # AI picks the right element ref
                element_info = await ai_service.pick_element(snapshot_content, step)
                ref = element_info.get("ref")

                if not ref:
                    raise Exception(
                        f"Could not find element for: {description}. "
                        f"AI reasoning: {element_info.get('reasoning', 'unknown')}"
                    )

                # Build playwright-cli command
                if action == "fill":
                    value = step.get("value", "")
                    cli_cmd = f'fill {ref} "{value}"'
                elif action == "select":
                    value = step.get("value", "")
                    cli_cmd = f'select {ref} "{value}"'
                elif action == "check":
                    cli_cmd = f"check {ref}"
                elif action == "uncheck":
                    cli_cmd = f"uncheck {ref}"
                elif action == "hover":
                    cli_cmd = f"hover {ref}"
                elif action == "press_key":
                    key = step.get("value", "Enter")
                    cli_cmd = f"press {key}"
                else:  # click is default
                    cli_cmd = f"click {ref}"

                # Execute
                result = await run_cli(cli_cmd, self.session_id, self.workspace)

                if result["returncode"] not in (0, None):
                    error_msg = result["stderr"] or result["stdout"]
                    if error_msg.strip():
                        raise Exception(f"playwright-cli error: {error_msg.strip()[:200]}")

                # Wait for dynamic content after state-changing actions
                if action == "click" and any(
                    word in description.lower()
                    for word in ["submit", "save", "create", "delete", "send", "login", "sign", "confirm", "add", "remove", "update"]
                ):
                    await asyncio.sleep(1.5)

                # Extract playwright_code from output
                pw_code = extract_playwright_code(result["stdout"]) or f"// {cli_cmd}"

                # Convert to RF using deterministic parser
                clean_code = pw_code
                if clean_code.startswith("await "):
                    clean_code = clean_code[6:]
                if clean_code.startswith("//"):
                    rf_line = f"    # Action: {cli_cmd}"
                else:
                    rf_line = playwright_to_rf(clean_code)

            # Capture screenshot
            screenshot_b64 = await self.screenshot()

            # Store RF line
            self.rf_lines.append(rf_line)

            return {
                "status": "success",
                "rf_line": rf_line,
                "playwright_code": pw_code,
                "screenshot_b64": screenshot_b64,
                "error": None,
            }

        except Exception as e:
            screenshot_b64 = await self.screenshot()
            error_msg = str(e)
            self.rf_lines.append(f"    # FAILED: {description} — {error_msg[:100]}")

            return {
                "status": "failed",
                "rf_line": f"    # FAILED: {description}",
                "playwright_code": "",
                "screenshot_b64": screenshot_b64,
                "error": error_msg,
            }

    async def run(self, nlp_input: str, start_url: str):
        """Main execution pipeline."""
        try:
            # ── 1. Break NLP into steps ───────────────
            await self.send({"type": "status", "message": f"Analyzing test description using {ai_service.provider_display}..."})

            self.steps = await ai_service.break_into_steps(nlp_input, start_url)

            await self.send({
                "type": "steps_planned",
                "steps": self.steps,
                "total": len(self.steps),
            })

            print(f"\n[Orchestrator] {len(self.steps)} steps planned:")
            for s in self.steps:
                print(f"  {s['step']}. [{s['action']}] {s['description']}")

            # ── 2. Open browser ───────────────────────
            await self.send({"type": "status", "message": "Opening browser..."})
            await run_cli(f"open {start_url}", self.session_id, self.workspace)
            await asyncio.sleep(2)

            # Initial screenshot
            screenshot_b64 = await self.screenshot()
            if screenshot_b64:
                await self.send({
                    "type": "step_complete",
                    "index": -1,
                    "status": "success",
                    "screenshot_b64": screenshot_b64,
                    "rf_line": f"    New Page    {start_url}",
                    "playwright_code": f"page.goto('{start_url}')",
                })

            # ── 3. Execute each step ──────────────────
            passed = 0
            failed = 0

            for i, step in enumerate(self.steps):
                if self.stopped:
                    await self.send({"type": "status", "message": "Stopped by user."})
                    break

                await self.wait_if_paused()

                # Skip initial navigate if URL matches
                if i == 0 and step.get("action") == "navigate":
                    target = step.get("target", "")
                    if target in (start_url, "/", ""):
                        self.rf_lines.append(f"    # Navigation to {start_url} — handled by New Page")
                        await self.send({
                            "type": "step_complete",
                            "index": i,
                            "status": "skipped",
                            "screenshot_b64": screenshot_b64,
                            "rf_line": "    # Initial navigation — handled by New Page",
                            "playwright_code": "",
                        })
                        passed += 1
                        continue

                print(f"\n[Step {i + 1}/{len(self.steps)}] {step['action']}: {step['description']}")

                result = await self.execute_step(step, i)

                if result["status"] == "success":
                    passed += 1
                    await self.send({
                        "type": "step_complete",
                        "index": i,
                        "status": "success",
                        "screenshot_b64": result["screenshot_b64"],
                        "rf_line": result["rf_line"],
                        "playwright_code": result["playwright_code"],
                    })
                    print(f"  ✓ RF: {result['rf_line'].strip()}")
                else:
                    failed += 1
                    await self.send({
                        "type": "step_failed",
                        "index": i,
                        "error": result["error"],
                        "screenshot_b64": result["screenshot_b64"],
                    })
                    print(f"  ✗ Error: {result['error']}")

                await asyncio.sleep(0.5)

            # ── 4. Assemble .robot file ───────────────
            test_name = re.sub(r"[^\w\s]", "", nlp_input)[:60].strip().title()
            robot_script = assemble_robot_file(
                test_name=test_name,
                test_description=nlp_input,
                base_url=start_url,
                rf_lines=self.rf_lines,
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_{timestamp}.robot"
            filepath = GENERATED_TESTS_DIR / filename
            with open(filepath, "w") as f:
                f.write(robot_script)

            await self.send({
                "type": "rf_script_complete",
                "script": robot_script,
                "filename": filename,
            })

            await self.send({
                "type": "execution_complete",
                "total_steps": len(self.steps),
                "passed": passed,
                "failed": failed,
            })

            print(f"\n[Done] {passed} passed, {failed} failed → {filename}")

            # Cleanup
            await run_cli("close", self.session_id, self.workspace)

        except Exception as e:
            print(f"\n[Error] {e}")
            await self.send({"type": "error", "message": str(e)})


# ─── WebSocket Endpoint ──────────────────────────────────────────

@app.websocket("/nlp-test/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for NLP test generation."""
    await websocket.accept()

    session_id = str(uuid.uuid4())[:8]
    orchestrator: Optional[Orchestrator] = None
    task: Optional[asyncio.Task] = None

    await websocket.send_json({"type": "connected", "session_id": session_id})
    print(f"\n[WS] Client connected: {session_id}")

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start":
                nlp_input = data.get("nlp_input", "").strip()
                start_url = data.get("start_url", "").strip()

                if not nlp_input or not start_url:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Both nlp_input and start_url are required.",
                    })
                    continue

                print(f"\n[Start] URL: {start_url}")
                print(f"[Start] NLP: {nlp_input}")

                orchestrator = Orchestrator(session_id, websocket)
                task = asyncio.create_task(orchestrator.run(nlp_input, start_url))

            elif msg_type == "pause" and orchestrator:
                orchestrator.paused = True
                await websocket.send_json({"type": "status", "message": "Paused."})

            elif msg_type == "resume" and orchestrator:
                orchestrator.paused = False
                await websocket.send_json({"type": "status", "message": "Resumed."})

            elif msg_type == "stop" and orchestrator:
                orchestrator.stopped = True
                if task:
                    task.cancel()
                await websocket.send_json({"type": "status", "message": "Stopped."})

            elif msg_type == "retry_step" and orchestrator and orchestrator.steps:
                idx = data.get("step_index", 0)
                if 0 <= idx < len(orchestrator.steps):
                    result = await orchestrator.execute_step(orchestrator.steps[idx], idx)
                    msg_key = "step_complete" if result["status"] == "success" else "step_failed"
                    await websocket.send_json({"type": msg_key, "index": idx, **result})

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {session_id}")
        if orchestrator:
            orchestrator.stopped = True
            await run_cli("close", session_id, str(WORKSPACE_DIR / session_id))


# ─── REST Endpoints ───────────────────────────────────────────────

@app.get("/api/generated-tests")
async def list_tests():
    """List generated .robot files."""
    files = sorted(GENERATED_TESTS_DIR.glob("*.robot"), key=os.path.getmtime, reverse=True)
    return [
        {
            "filename": f.name,
            "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "size_bytes": f.stat().st_size,
        }
        for f in files
    ]


@app.get("/api/generated-tests/{filename}")
async def download_test(filename: str):
    """Download a generated .robot file."""
    filepath = GENERATED_TESTS_DIR / filename
    if not filepath.exists():
        return {"error": "File not found"}
    return FileResponse(filepath, filename=filename, media_type="text/plain")


@app.get("/api/health")
async def health():
    """Health check — verifies playwright-cli and AI provider."""
    # Check playwright-cli
    cli_ok = False
    try:
        proc = await asyncio.create_subprocess_shell(
            f"{PLAYWRIGHT_CLI} --version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        cli_ok = proc.returncode == 0
        cli_version = stdout.decode().strip() if cli_ok else "not found"
    except Exception:
        cli_version = "not found"

    return {
        "status": "ok" if cli_ok else "degraded",
        "playwright_cli": {"installed": cli_ok, "version": cli_version},
        "ai_provider": ai_service.provider_display,
    }

# ─── Serve React UI ──────────────────────────────


@app.get("/")
async def serve_ui():
    """Serve the standalone HTML UI."""
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h2>Place index.html in the same directory as app.py</h2>")


# ─── Run ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"\n{'='*50}")
    print(f"  NLP Test Generator")
    print(f"  AI Provider: {ai_service.provider_display}")
    print(f"  Server: http://{host}:{port}")
    print(f"  WebSocket: ws://{host}:{port}/nlp-test/ws")
    print(f"  Health: http://{host}:{port}/api/health")
    print(f"{'='*50}\n")
    uvicorn.run("app:app", host=host, port=port, reload=True)






______________playwright_parser.py______________

"""
Playwright Code → Robot Framework Browser Library Parser

Deterministic translation of playwright_code from YAML snapshots
into RF Browser library keywords. No AI needed for this step.
"""

import re
from typing import Optional


# ─── Unstable Locator Detection ───────────────────────────────────

UNSTABLE_ID_PATTERNS = [
    r"mat-input-\d+",       # Angular Material
    r"mat-select-\d+",
    r"mat-radio-\d+",
    r"mat-checkbox-\d+",
    r"cdk-\w+-\d+",         # Angular CDK
    r"react-select-\d+",    # React Select
    r":r\w+:",              # React auto-generated
    r"ember\d+",            # Ember
    r"ng-\w+-\d+",          # Angular
    r"css-[a-z0-9]{5,}",    # CSS-in-JS (Emotion, styled-components)
    r"sc-[a-zA-Z]+-\d+",    # styled-components
    r"mui-\d+",             # MUI
    r"radix-",              # Radix UI
    r"headlessui-",         # Headless UI
    r"__\w+-\d+",           # BEM auto-generated
]


def is_unstable_locator(locator: str) -> bool:
    """Check if a locator uses auto-generated/dynamic IDs."""
    for pattern in UNSTABLE_ID_PATTERNS:
        if re.search(pattern, locator):
            return True
    return False


# ─── Locator Extractors ──────────────────────────────────────────

LOCATOR_PATTERNS = [
    # getByTestId('value')
    (r"getByTestId\(['\"]([^'\"]+)['\"]\)", lambda m: f'[data-testid="{m.group(1)}"]'),
    # getByRole('role', { name: 'value' })
    (r"getByRole\(['\"](\w+)['\"],\s*\{\s*name:\s*['\"]([^'\"]+)['\"]\s*\}\)", lambda m: f'role={m.group(1)}[name="{m.group(2)}"]'),
    # getByRole('role', { name: /regex/i })
    (r"getByRole\(['\"](\w+)['\"],\s*\{\s*name:\s*/([^/]+)/\w*\s*\}\)", lambda m: f'role={m.group(1)}[name="{m.group(2)}"]'),
    # getByRole('role')
    (r"getByRole\(['\"](\w+)['\"]\)", lambda m: f"role={m.group(1)}"),
    # getByLabel('value')
    (r"getByLabel\(['\"]([^'\"]+)['\"]\)", lambda m: f'[aria-label="{m.group(1)}"]'),
    # getByPlaceholder('value')
    (r"getByPlaceholder\(['\"]([^'\"]+)['\"]\)", lambda m: f'[placeholder="{m.group(1)}"]'),
    # getByText('value')
    (r"getByText\(['\"]([^'\"]+)['\"]\)", lambda m: f"text={m.group(1)}"),
    # getByText(/regex/)
    (r"getByText\(/([^/]+)/\w*\)", lambda m: f"text={m.group(1)}"),
    # getByAltText('value')
    (r"getByAltText\(['\"]([^'\"]+)['\"]\)", lambda m: f'[alt="{m.group(1)}"]'),
    # getByTitle('value')
    (r"getByTitle\(['\"]([^'\"]+)['\"]\)", lambda m: f'[title="{m.group(1)}"]'),
    # locator('css_or_xpath')
    (r"locator\(['\"]([^'\"]+)['\"]\)", lambda m: m.group(1)),
]

# ─── Action Extractors ───────────────────────────────────────────

ACTION_PATTERNS = {
    "click": {
        "pattern": r"\.click\(\s*\)",
        "rf_keyword": "Click",
        "has_value": False,
    },
    "dblclick": {
        "pattern": r"\.dblclick\(\s*\)",
        "rf_keyword": "Click",
        "has_value": False,
        "extra_args": "    clickCount=2",
    },
    "fill": {
        "pattern": r"\.fill\(['\"]([^'\"]*?)['\"]\)",
        "rf_keyword": "Fill Text",
        "has_value": True,
    },
    "type": {
        "pattern": r"\.type\(['\"]([^'\"]*?)['\"]\)",
        "rf_keyword": "Type Text",
        "has_value": True,
    },
    "press": {
        "pattern": r"\.press\(['\"]([^'\"]+)['\"]\)",
        "rf_keyword": "Keyboard Key",
        "has_value": True,
        "locator_needed": False,
    },
    "check": {
        "pattern": r"\.check\(\s*\)",
        "rf_keyword": "Check Checkbox",
        "has_value": False,
    },
    "uncheck": {
        "pattern": r"\.uncheck\(\s*\)",
        "rf_keyword": "Uncheck Checkbox",
        "has_value": False,
    },
    "hover": {
        "pattern": r"\.hover\(\s*\)",
        "rf_keyword": "Hover",
        "has_value": False,
    },
    "selectOption": {
        "pattern": r"\.selectOption\(['\"]([^'\"]+)['\"]\)",
        "rf_keyword": "Select Options By",
        "has_value": True,
        "extra_prefix": "    value",
    },
    "setInputFiles": {
        "pattern": r"\.setInputFiles\(['\"]([^'\"]+)['\"]\)",
        "rf_keyword": "Upload File By Selector",
        "has_value": True,
    },
}

# ─── Navigation Patterns ─────────────────────────────────────────

NAV_PATTERNS = {
    "goto": r"page\.goto\(['\"]([^'\"]+)['\"]\)",
    "goBack": r"page\.goBack\(\)",
    "goForward": r"page\.goForward\(\)",
    "reload": r"page\.reload\(\)",
}

# ─── Assertion Patterns ──────────────────────────────────────────

EXPECT_PATTERNS = [
    (r"toBeVisible\(\)", "Get Element States    {locator}    contains    visible"),
    (r"toBeHidden\(\)", "Get Element States    {locator}    contains    hidden"),
    (r"toBeEnabled\(\)", "Get Element States    {locator}    contains    enabled"),
    (r"toBeDisabled\(\)", "Get Element States    {locator}    contains    disabled"),
    (r"toBeChecked\(\)", "Get Element States    {locator}    contains    checked"),
    (r"toHaveText\(['\"]([^'\"]+)['\"]\)", "Get Text    {locator}    ==    {value}"),
    (r"toContainText\(['\"]([^'\"]+)['\"]\)", "Get Text    {locator}    *=    {value}"),
    (r"toHaveValue\(['\"]([^'\"]+)['\"]\)", "Get Text    {locator}    ==    {value}"),
    (r"toHaveCount\((\d+)\)", "Get Element Count    {locator}    ==    {value}"),
    (r"toHaveURL\(['\"]([^'\"]+)['\"]\)", "Get Url    ==    {value}"),
    (r"toHaveTitle\(['\"]([^'\"]+)['\"]\)", "Get Title    ==    {value}"),
]


# ─── Core Functions ───────────────────────────────────────────────

def extract_locator(code: str) -> Optional[str]:
    """Extract RF Browser locator from Playwright code."""
    locator = None

    for pattern, builder in LOCATOR_PATTERNS:
        match = re.search(pattern, code)
        if match:
            locator = builder(match)
            break

    if not locator:
        return None

    # Handle chained .nth(n)
    nth_match = re.search(r"\.nth\((\d+)\)", code)
    if nth_match:
        locator = f"{locator} >> nth={nth_match.group(1)}"

    # Handle .first()
    if ".first()" in code:
        locator = f"{locator} >> nth=0"

    # Handle .last()
    if ".last()" in code:
        locator = f"{locator} >> nth=-1"

    # Handle .filter({ hasText: 'text' })
    filter_match = re.search(r"\.filter\(\{\s*hasText:\s*['\"]([^'\"]+)['\"]\s*\}\)", code)
    if filter_match:
        locator = f"{locator} >> text={filter_match.group(1)}"

    return locator


def extract_action(code: str) -> Optional[dict]:
    """Extract action details from Playwright code."""
    for action_name, config in ACTION_PATTERNS.items():
        match = re.search(config["pattern"], code)
        if match:
            result = {
                "keyword": config["rf_keyword"],
                "value": match.group(1) if config["has_value"] and match.lastindex else None,
            }
            if "extra_args" in config:
                result["extra_args"] = config["extra_args"]
            if "extra_prefix" in config:
                result["extra_prefix"] = config["extra_prefix"]
            if config.get("locator_needed") is False:
                result["skip_locator"] = True
            return result
    return None


def extract_navigation(code: str) -> Optional[str]:
    """Extract navigation action from Playwright code."""
    for nav_name, pattern in NAV_PATTERNS.items():
        match = re.search(pattern, code)
        if match:
            if nav_name == "goto":
                return f"    Go To    {match.group(1)}"
            elif nav_name == "goBack":
                return "    Go Back"
            elif nav_name == "goForward":
                return "    Go Forward"
            elif nav_name == "reload":
                return "    Reload"
    return None


def extract_assertion(code: str) -> Optional[str]:
    """Extract assertion from Playwright expect() code."""
    locator = extract_locator(code)

    for pattern, rf_template in EXPECT_PATTERNS:
        match = re.search(pattern, code)
        if match:
            value = match.group(1) if match.lastindex else ""
            line = rf_template.format(
                locator=locator or "css=body",
                value=value,
            )
            return f"    {line}"
    return None


def playwright_to_rf(playwright_code: str) -> str:
    """
    Convert a single playwright_code line to RF Browser keyword.
    Returns RF keyword line with 4-space indent.
    """
    code = playwright_code.strip()

    # Handle expect/assertion
    if "expect(" in code:
        result = extract_assertion(code)
        if result:
            return result

    # Handle navigation
    nav = extract_navigation(code)
    if nav:
        return nav

    # Handle page.waitForTimeout
    timeout_match = re.search(r"waitForTimeout\((\d+)\)", code)
    if timeout_match:
        seconds = int(timeout_match.group(1)) / 1000
        return f"    Sleep    {seconds}s"

    # Handle waitForLoadState
    if "waitForLoadState" in code:
        return "    Wait For Load State    networkidle"

    # Handle waitForSelector
    if "waitForSelector" in code:
        locator = extract_locator(code)
        if locator:
            return f"    Wait For Elements State    {locator}    visible"

    # Handle keyboard press without locator
    press_match = re.search(r"page\.keyboard\.press\(['\"]([^'\"]+)['\"]\)", code)
    if press_match:
        return f"    Keyboard Key    {press_match.group(1)}"

    # Handle standard actions
    locator = extract_locator(code)
    action = extract_action(code)

    if action:
        keyword = action["keyword"]

        # Check for unstable locator
        warning = ""
        if locator and is_unstable_locator(locator):
            warning = f"    # WARNING: Unstable dynamic locator — consider adding data-testid\n"

        if action.get("skip_locator"):
            if action["value"]:
                return f"{warning}    {keyword}    {action['value']}"
            return f"{warning}    {keyword}"

        if locator and action["value"]:
            if "extra_prefix" in action:
                return f"{warning}    {keyword}    {locator}{action['extra_prefix']}    {action['value']}"
            return f"{warning}    {keyword}    {locator}    {action['value']}"
        elif locator:
            extra = action.get("extra_args", "")
            return f"{warning}    {keyword}    {locator}{extra}"
        elif action["value"]:
            return f"{warning}    {keyword}    {action['value']}"

    # Fallback: return as comment
    return f"    # MANUAL REVIEW: {code}"


def assemble_robot_file(
    test_name: str,
    test_description: str,
    base_url: str,
    rf_lines: list[str],
    variables: Optional[dict] = None,
) -> str:
    """Assemble a complete .robot file from generated RF lines."""
    sections = []

    sections.append("*** Settings ***")
    sections.append("Library    Browser")
    sections.append("")

    sections.append("*** Variables ***")
    sections.append(f"${{BASE_URL}}    {base_url}")
    if variables:
        for key, value in variables.items():
            sections.append(f"${{{key}}}    {value}")
    sections.append("")

    sections.append("*** Test Cases ***")
    sections.append(test_name)
    sections.append(f"    [Documentation]    {test_description}")
    sections.append("    New Browser    chromium    headless=true")
    sections.append("    New Page    ${BASE_URL}")
    sections.append("")

    for line in rf_lines:
        sections.append(line)

    sections.append("")
    sections.append("    [Teardown]    Close Browser")
    sections.append("")

    return "\n".join(sections)


def convert_action_log(action_log: list[dict]) -> list[str]:
    """
    Convert a list of action log entries (from playwright-cli YAML)
    into RF Browser keyword lines.
    """
    rf_lines = []

    for entry in action_log:
        action = entry.get("action", "")
        pw_code = entry.get("playwright_code", "")

        if action == "snapshot":
            continue

        if not pw_code:
            rf_lines.append(f"    # Step: {entry.get('description', action)} — no playwright_code")
            continue

        code_lines = [line.strip() for line in pw_code.strip().split("\n") if line.strip()]
        for code_line in code_lines:
            if code_line.startswith("await "):
                code_line = code_line[6:]
            rf_line = playwright_to_rf(code_line)
            rf_lines.append(rf_line)

    return rf_lines





____________index.html_________

<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NLP Test Generator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.9/babel.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body, #root { height: 100%; width: 100%; overflow: hidden; }
        body { background: #0f172a; color: #e2e8f0; }

        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        @keyframes slideIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0f172a; }
        ::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #475569; }
    </style>
</head>
<body>
    <div id="root"></div>

    <script type="text/babel">
        const { useState, useRef, useEffect, useCallback } = React;

        const WS_BASE = `ws://${window.location.hostname}:${window.location.port || '8000'}`;

        const ICONS = { pending: "○", running: "◉", success: "✓", failed: "✗", skipped: "⊘" };
        const COLORS = { pending: "#6b7280", running: "#f59e0b", success: "#22c55e", failed: "#ef4444", skipped: "#9ca3af" };

        function App() {
            const [connected, setConnected] = useState(false);
            const [sessionId, setSessionId] = useState("");
            const wsRef = useRef(null);

            const [nlpInput, setNlpInput] = useState("");
            const [startUrl, setStartUrl] = useState("");

            const [isRunning, setIsRunning] = useState(false);
            const [isPaused, setIsPaused] = useState(false);
            const [steps, setSteps] = useState([]);
            const [stepStatuses, setStepStatuses] = useState([]);
            const [currentStep, setCurrentStep] = useState(-1);
            const [statusMsg, setStatusMsg] = useState("");

            const [screenshot, setScreenshot] = useState(null);
            const [rfLines, setRfLines] = useState([]);
            const [finalScript, setFinalScript] = useState("");
            const [result, setResult] = useState(null);
            const [copyLabel, setCopyLabel] = useState("📋 Copy");

            const codeEndRef = useRef(null);

            // ── WebSocket ────────────────────────────
            const connect = useCallback(() => {
                if (wsRef.current?.readyState === WebSocket.OPEN) return;
                const ws = new WebSocket(`${WS_BASE}/nlp-test/ws`);
                wsRef.current = ws;

                ws.onopen = () => setConnected(true);
                ws.onclose = () => { setConnected(false); setIsRunning(false); };
                ws.onerror = () => setConnected(false);
                ws.onmessage = (e) => handleMsg(JSON.parse(e.data));
            }, []);

            const send = useCallback((msg) => {
                if (wsRef.current?.readyState === WebSocket.OPEN)
                    wsRef.current.send(JSON.stringify(msg));
            }, []);

            const handleMsg = useCallback((d) => {
                switch (d.type) {
                    case "connected": setSessionId(d.session_id); break;
                    case "status": setStatusMsg(d.message); break;
                    case "steps_planned":
                        setSteps(d.steps);
                        setStepStatuses(d.steps.map(() => "pending"));
                        break;
                    case "step_start":
                        setCurrentStep(d.index);
                        setStepStatuses(p => { const n=[...p]; if(d.index>=0) n[d.index]="running"; return n; });
                        setStatusMsg(`Step ${d.index+1}: ${d.description}`);
                        break;
                    case "step_complete":
                        if (d.screenshot_b64) setScreenshot(d.screenshot_b64);
                        if (d.rf_line) setRfLines(p => [...p, d.rf_line]);
                        setStepStatuses(p => { const n=[...p]; if(d.index>=0) n[d.index]=d.status==="skipped"?"skipped":"success"; return n; });
                        break;
                    case "step_failed":
                        if (d.screenshot_b64) setScreenshot(d.screenshot_b64);
                        setStepStatuses(p => { const n=[...p]; if(d.index>=0) n[d.index]="failed"; return n; });
                        setStatusMsg(`Step ${d.index+1} failed: ${d.error}`);
                        break;
                    case "rf_script_complete":
                        setFinalScript(d.script);
                        setStatusMsg("✓ Test script generated!");
                        break;
                    case "execution_complete":
                        setIsRunning(false);
                        setResult(d);
                        break;
                    case "error":
                        setStatusMsg(`Error: ${d.message}`);
                        setIsRunning(false);
                        break;
                }
            }, []);

            useEffect(() => { connect(); return () => wsRef.current?.close(); }, [connect]);
            useEffect(() => { codeEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [rfLines]);

            // ── Actions ──────────────────────────────
            const handleStart = () => {
                if (!nlpInput.trim() || !startUrl.trim()) return;
                setSteps([]); setStepStatuses([]); setCurrentStep(-1);
                setRfLines([]); setFinalScript(""); setScreenshot(null);
                setResult(null); setIsRunning(true); setIsPaused(false);
                send({ type: "start", nlp_input: nlpInput.trim(), start_url: startUrl.trim() });
            };

            const handlePause = () => { send({ type: isPaused ? "resume" : "pause" }); setIsPaused(!isPaused); };
            const handleStop = () => { send({ type: "stop" }); setIsRunning(false); setIsPaused(false); };
            const handleRetry = (i) => { send({ type: "retry_step", step_index: i }); setStepStatuses(p => { const n=[...p]; n[i]="running"; return n; }); };

            const handleCopy = () => {
                navigator.clipboard.writeText(finalScript);
                setCopyLabel("✓ Copied!");
                setTimeout(() => setCopyLabel("📋 Copy"), 2000);
            };

            const handleDownload = () => {
                const blob = new Blob([finalScript], { type: "text/plain" });
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = `test_${Date.now()}.robot`;
                a.click();
            };

            const canStart = nlpInput.trim() && startUrl.trim() && connected && !isRunning;

            // ── Render ───────────────────────────────
            return (
                <div style={S.container}>
                    {/* Header */}
                    <div style={S.header}>
                        <div style={S.headerLeft}>
                            <div style={S.logoMark}>⚡</div>
                            <h1 style={S.title}>NLP Test Generator</h1>
                            <span style={{
                                ...S.badge,
                                background: connected ? "#065f46" : "#7f1d1d",
                                color: connected ? "#6ee7b7" : "#fca5a5",
                            }}>
                                {connected ? "● Connected" : "○ Disconnected"}
                            </span>
                        </div>
                        {result && (
                            <div style={S.headerRight}>
                                <span style={{...S.resultBadge, background:"#065f46", color:"#6ee7b7"}}>{result.passed} passed</span>
                                {result.failed > 0 && <span style={{...S.resultBadge, background:"#7f1d1d", color:"#fca5a5"}}>{result.failed} failed</span>}
                            </div>
                        )}
                    </div>

                    {/* Input */}
                    <div style={S.inputSection}>
                        <div style={S.inputGrid}>
                            <div style={S.fieldWrap}>
                                <label style={S.label}>Target URL</label>
                                <input
                                    style={S.input}
                                    placeholder="https://your-app.com"
                                    value={startUrl}
                                    onChange={e => setStartUrl(e.target.value)}
                                    disabled={isRunning}
                                    onKeyDown={e => e.key === "Enter" && document.getElementById("nlp-area")?.focus()}
                                />
                            </div>
                            <div style={{...S.fieldWrap, flex: 2}}>
                                <label style={S.label}>Test Description</label>
                                <input
                                    id="nlp-area"
                                    style={S.input}
                                    placeholder='e.g. "Login with admin@test.com / Pass123, verify dashboard loads, click Orders tab, verify orders table is visible"'
                                    value={nlpInput}
                                    onChange={e => setNlpInput(e.target.value)}
                                    disabled={isRunning}
                                    onKeyDown={e => e.key === "Enter" && canStart && handleStart()}
                                />
                            </div>
                            <div style={S.btnGroup}>
                                {!isRunning ? (
                                    <button style={{...S.btn, ...S.btnPrimary, opacity: canStart ? 1 : 0.4}} onClick={handleStart} disabled={!canStart}>
                                        ▶ Generate
                                    </button>
                                ) : (
                                    <>
                                        <button style={{...S.btn, ...S.btnWarn}} onClick={handlePause}>
                                            {isPaused ? "▶ Resume" : "⏸ Pause"}
                                        </button>
                                        <button style={{...S.btn, ...S.btnDanger}} onClick={handleStop}>■ Stop</button>
                                    </>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Main Split */}
                    <div style={S.split}>
                        {/* Left — 60% */}
                        <div style={S.left}>
                            {/* Screenshot */}
                            <div style={S.screenshotWrap}>
                                {screenshot ? (
                                    <img src={`data:image/png;base64,${screenshot}`} alt="Browser" style={S.screenshotImg}/>
                                ) : (
                                    <div style={S.placeholder}>
                                        <div style={{fontSize:48,opacity:0.2,marginBottom:8}}>🌐</div>
                                        <div style={{fontFamily:"Inter,sans-serif",fontSize:13,color:"#475569"}}>
                                            Browser view appears here during execution
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Status */}
                            {statusMsg && (
                                <div style={S.statusBar}>
                                    {isRunning && <span style={S.spinner}/>}
                                    <span>{statusMsg}</span>
                                </div>
                            )}

                            {/* Steps */}
                            {steps.length > 0 && (
                                <div style={S.stepsWrap}>
                                    <div style={S.stepsHead}>
                                        Steps ({stepStatuses.filter(s => s==="success"||s==="skipped").length}/{steps.length})
                                    </div>
                                    <div style={S.stepsList}>
                                        {steps.map((step, i) => (
                                            <div key={i} style={{
                                                ...S.stepItem,
                                                borderLeftColor: COLORS[stepStatuses[i]] || COLORS.pending,
                                                background: currentStep===i ? "#1e293b" : "transparent",
                                                animation: stepStatuses[i]==="running" ? "pulse 1.5s infinite" : "none",
                                            }}>
                                                <span style={{...S.stepIcon, color: COLORS[stepStatuses[i]]}}>{ICONS[stepStatuses[i]]||ICONS.pending}</span>
                                                <div style={S.stepBody}>
                                                    <span style={S.stepAction}>{step.action}</span>
                                                    <span style={S.stepDesc}>{step.description}</span>
                                                </div>
                                                {stepStatuses[i]==="failed" && (
                                                    <button style={S.retryBtn} onClick={() => handleRetry(i)} title="Retry">↻</button>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Divider */}
                        <div style={S.divider}/>

                        {/* Right — 40% */}
                        <div style={S.right}>
                            <div style={S.codeHead}>
                                <span style={S.codeTitle}>
                                    {finalScript ? "Generated .robot File" : "RF Browser Code"}
                                </span>
                                {finalScript && (
                                    <div style={{display:"flex",gap:6}}>
                                        <button style={S.codeBtn} onClick={handleCopy}>{copyLabel}</button>
                                        <button style={S.codeBtn} onClick={handleDownload}>⬇ Download</button>
                                    </div>
                                )}
                            </div>

                            <div style={S.codeArea}>
                                {finalScript ? (
                                    <pre style={S.code}>{finalScript}</pre>
                                ) : rfLines.length > 0 ? (
                                    <pre style={S.code}>
                                        <span style={S.dim}>*** Settings ***{"\n"}Library    Browser{"\n\n"}*** Test Cases ***{"\n"}NLP Generated Test{"\n"}    New Browser    chromium    headless=true{"\n"}    New Page    {startUrl}{"\n\n"}</span>
                                        {rfLines.map((line, i) => (
                                            <span key={i} style={{
                                                display: "block",
                                                animation: "slideIn 0.3s ease",
                                                color: i===rfLines.length-1 ? "#22c55e" :
                                                       line.includes("# FAILED") || line.includes("# WARNING") ? "#fca5a5" :
                                                       line.includes("# MANUAL") ? "#f59e0b" : "#e2e8f0",
                                                background: i===rfLines.length-1 ? "#052e1680" :
                                                            line.includes("# FAILED") ? "#1c0a0a80" : "transparent",
                                                padding: "1px 4px",
                                                borderRadius: 2,
                                            }}>{line}</span>
                                        ))}
                                        <span ref={codeEndRef}/>
                                    </pre>
                                ) : (
                                    <div style={S.placeholder}>
                                        <div style={{fontSize:36,opacity:0.15,marginBottom:8,fontFamily:"JetBrains Mono"}}>{"{ }"}</div>
                                        <div style={{fontFamily:"Inter,sans-serif",fontSize:13,color:"#475569"}}>
                                            Robot Framework code builds here as steps execute
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            );
        }

        // ── Styles ───────────────────────────────────
        const S = {
            container: { width:"100%", height:"100vh", display:"flex", flexDirection:"column", background:"#0f172a", fontFamily:"'JetBrains Mono','Fira Code',monospace", overflow:"hidden" },

            header: { display:"flex", alignItems:"center", justifyContent:"space-between", padding:"10px 20px", borderBottom:"1px solid #1e293b", flexShrink:0 },
            headerLeft: { display:"flex", alignItems:"center", gap:12 },
            headerRight: { display:"flex", gap:8 },
            logoMark: { fontSize:20, width:32, height:32, display:"flex", alignItems:"center", justifyContent:"center", background:"linear-gradient(135deg,#3b82f6,#8b5cf6)", borderRadius:8 },
            title: { fontSize:15, fontWeight:700, color:"#f1f5f9", letterSpacing:"-0.02em" },
            badge: { fontSize:11, padding:"2px 10px", borderRadius:99, fontWeight:600, letterSpacing:"0.02em" },
            resultBadge: { fontSize:12, padding:"3px 12px", borderRadius:99, fontWeight:600 },

            inputSection: { padding:"12px 20px", borderBottom:"1px solid #1e293b", flexShrink:0 },
            inputGrid: { display:"flex", gap:12, alignItems:"flex-end" },
            fieldWrap: { flex:1, display:"flex", flexDirection:"column" },
            label: { fontSize:10, color:"#64748b", marginBottom:4, fontWeight:700, textTransform:"uppercase", letterSpacing:"0.08em" },
            input: { padding:"9px 12px", fontSize:13, background:"#1e293b", border:"1px solid #334155", borderRadius:6, color:"#e2e8f0", fontFamily:"Inter,sans-serif", outline:"none", width:"100%", transition:"border-color 0.15s" },
            btnGroup: { display:"flex", gap:6, flexShrink:0 },
            btn: { padding:"9px 20px", fontSize:13, fontWeight:600, border:"none", borderRadius:6, cursor:"pointer", fontFamily:"inherit", whiteSpace:"nowrap", transition:"all 0.15s" },
            btnPrimary: { background:"linear-gradient(135deg,#3b82f6,#2563eb)", color:"#fff" },
            btnWarn: { background:"#f59e0b", color:"#000" },
            btnDanger: { background:"#ef4444", color:"#fff" },

            split: { flex:1, display:"flex", overflow:"hidden", minHeight:0 },
            divider: { width:1, background:"#1e293b", flexShrink:0 },

            left: { flex:"0 0 60%", display:"flex", flexDirection:"column", overflow:"hidden" },
            screenshotWrap: { flex:"0 0 44%", padding:12, display:"flex", alignItems:"center", justifyContent:"center", background:"#080d19", borderBottom:"1px solid #1e293b", overflow:"hidden" },
            screenshotImg: { maxWidth:"100%", maxHeight:"100%", objectFit:"contain", borderRadius:4, border:"1px solid #1e293b" },
            placeholder: { textAlign:"center", display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", height:"100%" },

            statusBar: { padding:"7px 16px", fontSize:12, color:"#94a3b8", background:"#1e293b", borderBottom:"1px solid #334155", display:"flex", alignItems:"center", gap:8, flexShrink:0, fontFamily:"Inter,sans-serif" },
            spinner: { display:"inline-block", width:12, height:12, border:"2px solid #475569", borderTopColor:"#3b82f6", borderRadius:"50%", animation:"spin 0.8s linear infinite", flexShrink:0 },

            stepsWrap: { flex:1, display:"flex", flexDirection:"column", overflow:"hidden" },
            stepsHead: { padding:"7px 16px", fontSize:10, fontWeight:700, color:"#64748b", textTransform:"uppercase", letterSpacing:"0.06em", borderBottom:"1px solid #1e293b", flexShrink:0 },
            stepsList: { flex:1, overflowY:"auto", padding:"2px 0" },
            stepItem: { display:"flex", alignItems:"center", gap:10, padding:"5px 16px", borderLeft:"3px solid transparent", transition:"background 0.15s" },
            stepIcon: { fontSize:13, fontWeight:700, width:16, textAlign:"center", flexShrink:0 },
            stepBody: { flex:1, display:"flex", gap:8, alignItems:"baseline", minWidth:0 },
            stepAction: { fontSize:10, fontWeight:700, color:"#3b82f6", textTransform:"uppercase", flexShrink:0, letterSpacing:"0.04em" },
            stepDesc: { fontSize:12, color:"#cbd5e1", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis", fontFamily:"Inter,sans-serif" },
            retryBtn: { background:"none", border:"1px solid #475569", color:"#f59e0b", fontSize:14, cursor:"pointer", borderRadius:4, padding:"2px 7px", flexShrink:0 },

            right: { flex:"0 0 40%", display:"flex", flexDirection:"column", overflow:"hidden" },
            codeHead: { display:"flex", alignItems:"center", justifyContent:"space-between", padding:"7px 16px", borderBottom:"1px solid #1e293b", flexShrink:0 },
            codeTitle: { fontSize:10, fontWeight:700, color:"#64748b", textTransform:"uppercase", letterSpacing:"0.06em" },
            codeBtn: { background:"none", border:"1px solid #334155", color:"#94a3b8", fontSize:11, padding:"3px 10px", borderRadius:4, cursor:"pointer", fontFamily:"inherit", transition:"all 0.15s" },
            codeArea: { flex:1, overflowY:"auto", padding:"12px 16px", background:"#080d19" },
            code: { margin:0, fontSize:12, lineHeight:1.75, whiteSpace:"pre", color:"#e2e8f0" },
            dim: { color:"#334155" },
        };

        ReactDOM.createRoot(document.getElementById("root")).render(<App/>);
    </script>
</body>
</html>




_____________

"""
AI Service — Uses openai SDK for Azure OpenAI, google-genai for Gemini
Provider is selected via AI_PROVIDER env variable.
"""

import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

# ─── Prompts ──────────────────────────────────────────────────────

STEP_BREAKDOWN_PROMPT = """You are a QA automation expert. Break down the user's natural language test description into precise, sequential browser actions.

RULES:
- Each step must be a single atomic browser action
- Include assertions/verifications as separate steps
- Use clear, specific descriptions
- Include expected values for assertions
- First step should always be navigation if a URL context is given
- Think about what a manual tester would do step by step

IMPORTANT — CUSTOM DROPDOWNS:
Modern UI frameworks (MUI, Bootstrap, Angular Material, Ant Design) do NOT use native <select> elements. Their dropdowns require TWO steps:
1. Click the dropdown trigger to open it
2. Click the option from the opened list

When the test involves selecting from a dropdown:
  WRONG: {"action": "select", "target": "category", "value": "Electronics"}
  RIGHT:
    {"step": N, "action": "click", "description": "Click Category dropdown to open it", "target": "Category dropdown"}
    {"step": N+1, "action": "click", "description": "Select Electronics from dropdown list", "target": "Electronics option"}

IMPORTANT — MODALS AND DIALOGS:
After clicking a button that opens a modal/dialog, add a wait step before interacting with modal contents:
    {"step": N, "action": "click", "description": "Click Create New button", "target": "Create New button"}
    {"step": N+1, "action": "wait", "description": "Wait for dialog to appear", "value": "1"}
    {"step": N+2, "action": "fill", "description": "Fill name in dialog", "target": "Name field", "value": "Test"}

IMPORTANT — AFTER FORM SUBMISSIONS:
After clicking submit/save/create/delete buttons, add a wait step for the response:
    {"step": N, "action": "click", "description": "Click Submit", "target": "Submit button"}
    {"step": N+1, "action": "wait", "description": "Wait for response", "value": "2"}
    {"step": N+2, "action": "assert_visible", "description": "Verify success message", "target": "success message"}

OUTPUT FORMAT - respond ONLY with a JSON array, no markdown, no explanation:
[
  {"step": 1, "action": "navigate", "description": "Navigate to login page", "target": "/login"},
  {"step": 2, "action": "fill", "description": "Enter email address", "target": "email field", "value": "test@example.com"},
  {"step": 3, "action": "click", "description": "Click the login button", "target": "login button"},
  {"step": 4, "action": "wait", "description": "Wait for page to load", "value": "2"},
  {"step": 5, "action": "assert_url", "description": "Verify redirected to dashboard", "expected": "/dashboard"}
]

Valid actions: navigate, click, fill, select, check, uncheck, hover, press_key, upload, assert_text, assert_visible, assert_url, assert_element_count, wait
"""

PICK_ELEMENT_PROMPT = """You are a browser automation expert. Given a YAML snapshot of a web page and a step description, identify the correct element ref to interact with.

RULES:
- Pick the SINGLE best matching element ref from the snapshot
- Consider the step description, element roles, names, labels, and surrounding context
- If the step says "first" or mentions order, pick the first matching element
- If multiple similar elements exist (like multiple "Add to Cart" buttons), pick based on context
- If the step is an assertion, identify the element to assert against
- If no matching element exists, respond with ref: null

OUTPUT FORMAT - respond ONLY with JSON, no markdown:
{"ref": "e15", "confidence": "high", "reasoning": "Short explanation of why this element matches"}
"""

ASSERTION_PROMPT = """You are a QA automation expert generating Robot Framework Browser library assertions.

Given a YAML snapshot and an assertion step, generate the correct RF Browser assertion keyword.

AVAILABLE ASSERTION KEYWORDS:
- Get Text    <locator>    ==    <expected>        (exact text match)
- Get Text    <locator>    *=    <expected>        (contains text)
- Get Url    ==    <expected>                       (exact URL)
- Get Url    *=    <expected>                       (URL contains)
- Get Element States    <locator>    contains    visible
- Get Element States    <locator>    contains    enabled
- Get Element States    <locator>    contains    checked
- Get Element Count    <locator>    ==    <count>
- Get Title    ==    <expected>

LOCATOR SELECTION — use this priority from the snapshot element attributes:
1. [data-testid="value"]     — always prefer if exists
2. id=value                   — if meaningful, not auto-generated (skip mat-input-7, :r1:, css-1abc)
3. role=type[name="value"]    — accessible and stable
4. text=visible text          — for buttons/links
5. [placeholder="value"]     — for inputs
6. [aria-label="value"]      — when no visible text
7. css=semantic-selector      — stable classes/attributes only

OUTPUT FORMAT - respond ONLY with JSON, no markdown:
{"rf_keyword": "Get Text", "locator": "[data-testid=\\"welcome-msg\\"]", "operator": "*=", "expected_value": "Welcome", "full_line": "    Get Text    [data-testid=\\"welcome-msg\\"]    *=    Welcome"}
"""


# ─── Provider Interface ──────────────────────────────────────────

class AIProvider:
    """Base class for AI providers."""
    def call(self, system_prompt: str, user_message: str) -> str:
        raise NotImplementedError


class AzureOpenAIProvider(AIProvider):
    """Azure OpenAI using the openai Python SDK."""

    def __init__(self):
        from openai import AzureOpenAI

        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

        if not self.api_key:
            raise ValueError("AZURE_OPENAI_API_KEY is not set in .env")
        if not self.endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT is not set in .env")

        self._client = AzureOpenAI(
            api_key=self.api_key,
            azure_endpoint=self.endpoint,
            api_version=self.api_version,
        )
        self._model = self.deployment

    def call(self, system_prompt: str, user_message: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=4096,
        )
        return response.choices[0].message.content


class GeminiProvider(AIProvider):
    """Google Gemini using the google-genai SDK."""

    def __init__(self):
        from google import genai

        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in .env")

        self._client = genai.Client(api_key=self.api_key)
        self._model = self.model_name

    def call(self, system_prompt: str, user_message: str) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._model,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,
                max_output_tokens=4096,
            ),
        )
        return response.text


# ─── AI Service (uses configured provider) ───────────────────────

class AIService:
    def __init__(self):
        provider_name = os.getenv("AI_PROVIDER", "azure_openai").lower()

        if provider_name == "azure_openai":
            self.provider = AzureOpenAIProvider()
            self.provider_display = "Azure OpenAI"
        elif provider_name == "gemini":
            self.provider = GeminiProvider()
            self.provider_display = "Gemini"
        else:
            raise ValueError(
                f"Unknown AI_PROVIDER: '{provider_name}'. "
                f"Use 'azure_openai' or 'gemini'"
            )

        print(f"[AI Service] Using provider: {self.provider_display}")

    def _clean_response(self, content: str) -> str:
        """Strip markdown fences from AI response."""
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    async def break_into_steps(self, nlp_input: str, start_url: str) -> list[dict]:
        """Break NLP test description into sequential steps."""
        user_msg = f'Test description: "{nlp_input}"\nStarting URL: {start_url}\n\nBreak this into precise sequential browser actions.'

        result = self._clean_response(self.provider.call(STEP_BREAKDOWN_PROMPT, user_msg))
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            match = re.search(r"\[.*\]", result, re.DOTALL)
            if match:
                return json.loads(match.group())
            raise ValueError(f"Failed to parse AI response: {result[:300]}")

    async def pick_element(self, snapshot_content: str, step: dict) -> dict:
        """Pick the correct element ref from a snapshot for a given step."""
        user_msg = f"STEP: {json.dumps(step)}\n\nPAGE SNAPSHOT:\n{snapshot_content}"

        result = self._clean_response(self.provider.call(PICK_ELEMENT_PROMPT, user_msg))
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"ref": None, "confidence": "low", "reasoning": "Failed to parse response"}

    async def generate_assertion(self, snapshot_content: str, step: dict) -> dict:
        """Generate RF Browser assertion for a verification step."""
        user_msg = f"ASSERTION STEP: {json.dumps(step)}\n\nPAGE SNAPSHOT:\n{snapshot_content}"

        result = self._clean_response(self.provider.call(ASSERTION_PROMPT, user_msg))
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "rf_keyword": "Log",
                "full_line": f'    Log    Assertion could not be generated for: {step.get("description", "unknown")}',
            }
            



_______import subprocess
import concurrent.futures

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

async def run_cli(
    command: str,
    session: str = "default",
    cwd: str = "",
    timeout: float = 30.0,
) -> dict:
    """Execute playwright-cli command using thread pool (Windows compatible)."""
    full_cmd = f"{PLAYWRIGHT_CLI} -s={session} {command}"
    work_dir = cwd or str(WORKSPACE_DIR)

    print(f"  [CLI] {full_cmd}")

    def _run():
        try:
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                cwd=work_dir,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", -1

    loop = asyncio.get_event_loop()
    stdout_str, stderr_str, returncode = await loop.run_in_executor(_executor, _run)

    print(f"  [CLI stdout] {stdout_str[:500]}")
    print(f"  [CLI stderr] {stderr_str[:200]}")
    print(f"  [CLI return] {returncode}")

    # Extract snapshot file path
    snapshot_file = None
    for line in stdout_str.split("\n"):
        match = re.search(r"(\.playwright-cli[/\\][^\s\]]+\.yml)", line)
        if match:
            snapshot_file = os.path.join(work_dir, match.group(1))

    # Extract screenshot file path
    screenshot_file = None
    for line in stdout_str.split("\n"):
        match = re.search(r"(\.playwright-cli[/\\][^\s\]]+\.png)", line)
        if match:
            screenshot_file = os.path.join(work_dir, match.group(1))

    return {
        "stdout": stdout_str,
        "stderr": stderr_str,
        "returncode": returncode,
        "snapshot_file": snapshot_file,
        "screenshot_file": screenshot_file,
    }




&____₹₹_____

"""
NLP Test Generator — Standalone FastAPI Server
Run: python app.py

Prerequisites:
  npm install -g @playwright/cli@latest
  playwright-cli install
  pip install fastapi uvicorn python-dotenv websockets openai
"""

import asyncio
import base64
import concurrent.futures
import glob
import json
import os
import re
import subprocess
import tempfile
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

from ai_service import AIService
from playwright_parser import assemble_robot_file, playwright_to_rf

load_dotenv()

# ─── App Setup ────────────────────────────────────────────────────

app = FastAPI(title="NLP Test Generator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Configuration ────────────────────────────────────────────────

PLAYWRIGHT_CLI = os.getenv("PLAYWRIGHT_CLI_PATH", "playwright-cli")
WORKSPACE_DIR = Path(os.getenv("NLP_WORKSPACE", os.path.join(tempfile.gettempdir(), "nlp-test-workspaces")))
GENERATED_TESTS_DIR = Path("./generated_tests")
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_TESTS_DIR.mkdir(parents=True, exist_ok=True)

ai_service = AIService()

# Thread pool for running subprocess on Windows
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


# ─── Subprocess Helper (Windows Compatible) ───────────────────────

async def run_cli(
    command: str,
    session: str = "default",
    cwd: str = "",
    timeout: float = 30.0,
) -> dict:
    """Execute playwright-cli command using thread pool (Windows compatible)."""
    full_cmd = f"{PLAYWRIGHT_CLI} -s={session} {command}"
    work_dir = cwd or str(WORKSPACE_DIR)

    print(f"  [CLI] {full_cmd}")

    def _run():
        try:
            result = subprocess.run(
                full_cmd,
                shell=True,
                capture_output=True,
                cwd=work_dir,
                timeout=timeout,
                encoding="utf-8",
                errors="replace",
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", -1
        except Exception as e:
            return "", str(e), -1

    loop = asyncio.get_event_loop()
    stdout_str, stderr_str, returncode = await loop.run_in_executor(_executor, _run)

    print(f"  [CLI stdout] {stdout_str[:500]}")
    print(f"  [CLI stderr] {stderr_str[:200]}")
    print(f"  [CLI return] {returncode}")

    # Extract snapshot file path (handles both / and \ paths)
    snapshot_file = None
    for line in stdout_str.split("\n"):
        match = re.search(r"(\.playwright-cli[/\\][^\s\)\]]+\.yml)", line)
        if match:
            snapshot_file = os.path.join(work_dir, match.group(1))

    # Extract screenshot file path
    screenshot_file = None
    for line in stdout_str.split("\n"):
        match = re.search(r"(\.playwright-cli[/\\][^\s\)\]]+\.png)", line)
        if match:
            screenshot_file = os.path.join(work_dir, match.group(1))

    return {
        "stdout": stdout_str,
        "stderr": stderr_str,
        "returncode": returncode,
        "snapshot_file": snapshot_file,
        "screenshot_file": screenshot_file,
    }


def read_file_content(path: str) -> str:
    """Read file content safely."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return ""


def find_latest_file(directory: str, pattern: str) -> Optional[str]:
    """Find most recent file matching glob pattern."""
    files = sorted(glob.glob(os.path.join(directory, pattern)), key=os.path.getmtime, reverse=True)
    return files[0] if files else None


def file_to_base64(path: str) -> Optional[str]:
    """Read file and return base64 string."""
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except (FileNotFoundError, IOError):
        return None


def extract_playwright_code(stdout: str) -> Optional[str]:
    """Extract playwright_code line from CLI output."""
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("await page.") or line.startswith("page."):
            return line
    return None


# ─── Orchestrator ─────────────────────────────────────────────────

class Orchestrator:
    """Manages the NLP → playwright-cli → RF pipeline with WebSocket streaming."""

    def __init__(self, session_id: str, ws: WebSocket):
        self.session_id = session_id
        self.ws = ws
        self.workspace = str(WORKSPACE_DIR / session_id)
        self.cli_dir = os.path.join(self.workspace, ".playwright-cli")
        self.paused = False
        self.stopped = False
        self.rf_lines: list[str] = []
        self.steps: list[dict] = []

        os.makedirs(self.workspace, exist_ok=True)

    async def send(self, msg: dict):
        """Send message to client."""
        try:
            await self.ws.send_json(msg)
        except Exception:
            pass

    async def wait_if_paused(self):
        """Block while paused."""
        while self.paused and not self.stopped:
            await asyncio.sleep(0.3)

    async def screenshot(self) -> Optional[str]:
        """Take screenshot and return base64."""
        result = await run_cli("screenshot", self.session_id, self.workspace)
        path = result.get("screenshot_file") or find_latest_file(self.cli_dir, "*.png")
        return file_to_base64(path) if path else None

    async def snapshot(self) -> str:
        """Take snapshot and return YAML content."""
        result = await run_cli("snapshot", self.session_id, self.workspace)
        path = result.get("snapshot_file") or find_latest_file(self.cli_dir, "*.yml")
        return read_file_content(path) if path else ""

    async def execute_step(self, step: dict, index: int) -> dict:
        """Execute a single test step. Returns result dict."""

        action = step.get("action", "")
        description = step.get("description", "")

        await self.send({
            "type": "step_start",
            "index": index,
            "description": description,
            "action": action,
        })

        try:
            # ── Navigate ──────────────────────────────
            if action == "navigate":
                target = step.get("target", "")
                await run_cli(f"goto {target}", self.session_id, self.workspace)
                await asyncio.sleep(1.5)
                pw_code = f"page.goto('{target}')"
                rf_line = f"    Go To    {target}"

            # ── Wait ──────────────────────────────────
            elif action == "wait":
                duration = step.get("value", "2")
                await asyncio.sleep(float(duration))
                rf_line = f"    Sleep    {duration}s"
                pw_code = f"page.waitForTimeout({int(float(duration) * 1000)})"

            # ── Assertions ────────────────────────────
            elif action.startswith("assert"):
                snapshot_content = await self.snapshot()
                assertion = await ai_service.generate_assertion(snapshot_content, step)
                rf_line = assertion.get("full_line", f"    # Assertion: {description}")
                pw_code = f"// Assertion: {description}"

            # ── Interactive actions ───────────────────
            else:
                # Get snapshot for element picking
                snapshot_content = await self.snapshot()

                # AI picks the right element ref
                element_info = await ai_service.pick_element(snapshot_content, step)
                ref = element_info.get("ref")

                if not ref:
                    raise Exception(
                        f"Could not find element for: {description}. "
                        f"AI reasoning: {element_info.get('reasoning', 'unknown')}"
                    )

                # Build playwright-cli command
                if action == "fill":
                    value = step.get("value", "")
                    cli_cmd = f'fill {ref} "{value}"'
                elif action == "select":
                    value = step.get("value", "")
                    cli_cmd = f'select {ref} "{value}"'
                elif action == "check":
                    cli_cmd = f"check {ref}"
                elif action == "uncheck":
                    cli_cmd = f"uncheck {ref}"
                elif action == "hover":
                    cli_cmd = f"hover {ref}"
                elif action == "press_key":
                    key = step.get("value", "Enter")
                    cli_cmd = f"press {key}"
                else:  # click is default
                    cli_cmd = f"click {ref}"

                # Execute
                result = await run_cli(cli_cmd, self.session_id, self.workspace)

                if result["returncode"] not in (0, None):
                    error_msg = result["stderr"] or result["stdout"]
                    if error_msg.strip():
                        raise Exception(f"playwright-cli error: {error_msg.strip()[:200]}")

                # Wait for dynamic content after state-changing actions
                if action == "click" and any(
                    word in description.lower()
                    for word in ["submit", "save", "create", "delete", "send", "login", "sign", "confirm", "add", "remove", "update"]
                ):
                    await asyncio.sleep(1.5)

                # Extract playwright_code from output
                pw_code = extract_playwright_code(result["stdout"]) or f"// {cli_cmd}"

                # Convert to RF using deterministic parser
                clean_code = pw_code
                if clean_code.startswith("await "):
                    clean_code = clean_code[6:]
                if clean_code.startswith("//"):
                    rf_line = f"    # Action: {cli_cmd}"
                else:
                    rf_line = playwright_to_rf(clean_code)

            # Capture screenshot
            screenshot_b64 = await self.screenshot()

            # Store RF line
            self.rf_lines.append(rf_line)

            return {
                "status": "success",
                "rf_line": rf_line,
                "playwright_code": pw_code,
                "screenshot_b64": screenshot_b64,
                "error": None,
            }

        except Exception as e:
            screenshot_b64 = await self.screenshot()
            error_msg = str(e)

            self.rf_lines.append(f"    # FAILED: {description} — {error_msg[:100]}")

            return {
                "status": "failed",
                "rf_line": f"    # FAILED: {description}",
                "playwright_code": "",
                "screenshot_b64": screenshot_b64,
                "error": error_msg,
            }

    async def run(self, nlp_input: str, start_url: str):
        """Main execution pipeline."""
        try:
            # ── 1. Break NLP into steps ───────────────
            await self.send({"type": "status", "message": f"Analyzing test description using {ai_service.provider_display}..."})

            self.steps = await ai_service.break_into_steps(nlp_input, start_url)

            await self.send({
                "type": "steps_planned",
                "steps": self.steps,
                "total": len(self.steps),
            })

            print(f"\n[Orchestrator] {len(self.steps)} steps planned:")
            for s in self.steps:
                print(f"  {s['step']}. [{s['action']}] {s['description']}")

            # ── 2. Open browser ───────────────────────
            await self.send({"type": "status", "message": "Opening browser..."})

            result = await run_cli(f"open {start_url}", self.session_id, self.workspace)

            if result["returncode"] not in (0, None):
                stderr = result["stderr"].strip()
                if stderr:
                    await self.send({"type": "error", "message": f"Failed to open browser: {stderr[:300]}"})
                    return

            # Wait for page to load
            await asyncio.sleep(2)

            # Initial screenshot
            screenshot_b64 = await self.screenshot()
            if screenshot_b64:
                await self.send({
                    "type": "step_complete",
                    "index": -1,
                    "status": "success",
                    "screenshot_b64": screenshot_b64,
                    "rf_line": f"    New Page    {start_url}",
                    "playwright_code": f"page.goto('{start_url}')",
                })

            # ── 3. Execute each step ──────────────────
            passed = 0
            failed = 0

            for i, step in enumerate(self.steps):
                if self.stopped:
                    await self.send({"type": "status", "message": "Stopped by user."})
                    break

                await self.wait_if_paused()

                # Skip initial navigate if URL matches
                if i == 0 and step.get("action") == "navigate":
                    target = step.get("target", "")
                    if target in (start_url, "/", "") or start_url.rstrip("/").endswith(target.rstrip("/")):
                        self.rf_lines.append(f"    # Navigation to {start_url} — handled by New Page")
                        await self.send({
                            "type": "step_complete",
                            "index": i,
                            "status": "skipped",
                            "screenshot_b64": screenshot_b64,
                            "rf_line": "    # Initial navigation — handled by New Page",
                            "playwright_code": "",
                        })
                        passed += 1
                        continue

                print(f"\n[Step {i + 1}/{len(self.steps)}] {step['action']}: {step['description']}")

                step_result = await self.execute_step(step, i)

                if step_result["status"] == "success":
                    passed += 1
                    await self.send({
                        "type": "step_complete",
                        "index": i,
                        "status": "success",
                        "screenshot_b64": step_result["screenshot_b64"],
                        "rf_line": step_result["rf_line"],
                        "playwright_code": step_result["playwright_code"],
                    })
                    print(f"  ✓ RF: {step_result['rf_line'].strip()}")
                else:
                    failed += 1
                    await self.send({
                        "type": "step_failed",
                        "index": i,
                        "error": step_result["error"],
                        "screenshot_b64": step_result["screenshot_b64"],
                    })
                    print(f"  ✗ Error: {step_result['error']}")

                await asyncio.sleep(0.5)

            # ── 4. Assemble .robot file ───────────────
            test_name = re.sub(r"[^\w\s]", "", nlp_input)[:60].strip().title()
            robot_script = assemble_robot_file(
                test_name=test_name,
                test_description=nlp_input,
                base_url=start_url,
                rf_lines=self.rf_lines,
            )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_{timestamp}.robot"
            filepath = GENERATED_TESTS_DIR / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(robot_script)

            await self.send({
                "type": "rf_script_complete",
                "script": robot_script,
                "filename": filename,
            })

            await self.send({
                "type": "execution_complete",
                "total_steps": len(self.steps),
                "passed": passed,
                "failed": failed,
            })

            print(f"\n[Done] {passed} passed, {failed} failed → {filename}")

            # Cleanup
            await run_cli("close", self.session_id, self.workspace)

        except Exception as e:
            error_detail = traceback.format_exc()
            print(f"\n[Error]\n{error_detail}")
            await self.send({"type": "error", "message": str(e) or error_detail[-500:]})


# ─── WebSocket Endpoint ──────────────────────────────────────────

@app.websocket("/nlp-test/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for NLP test generation."""
    await websocket.accept()

    session_id = str(uuid.uuid4())[:8]
    orchestrator: Optional[Orchestrator] = None
    task: Optional[asyncio.Task] = None

    await websocket.send_json({"type": "connected", "session_id": session_id})
    print(f"\n[WS] Client connected: {session_id}")

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start":
                nlp_input = data.get("nlp_input", "").strip()
                start_url = data.get("start_url", "").strip()

                if not nlp_input or not start_url:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Both nlp_input and start_url are required.",
                    })
                    continue

                print(f"\n[Start] URL: {start_url}")
                print(f"[Start] NLP: {nlp_input}")

                orchestrator = Orchestrator(session_id, websocket)
                task = asyncio.create_task(orchestrator.run(nlp_input, start_url))

            elif msg_type == "pause" and orchestrator:
                orchestrator.paused = True
                await websocket.send_json({"type": "status", "message": "Paused."})

            elif msg_type == "resume" and orchestrator:
                orchestrator.paused = False
                await websocket.send_json({"type": "status", "message": "Resumed."})

            elif msg_type == "stop" and orchestrator:
                orchestrator.stopped = True
                if task:
                    task.cancel()
                await websocket.send_json({"type": "status", "message": "Stopped."})

            elif msg_type == "retry_step" and orchestrator and orchestrator.steps:
                idx = data.get("step_index", 0)
                if 0 <= idx < len(orchestrator.steps):
                    step_result = await orchestrator.execute_step(orchestrator.steps[idx], idx)
                    msg_key = "step_complete" if step_result["status"] == "success" else "step_failed"
                    await websocket.send_json({"type": msg_key, "index": idx, **step_result})

    except WebSocketDisconnect:
        print(f"[WS] Client disconnected: {session_id}")
        if orchestrator:
            orchestrator.stopped = True
            await run_cli("close", session_id, str(WORKSPACE_DIR / session_id))
    except Exception as e:
        print(f"[WS Error] {traceback.format_exc()}")


# ─── REST Endpoints ───────────────────────────────────────────────

@app.get("/api/generated-tests")
async def list_tests():
    """List generated .robot files."""
    files = sorted(GENERATED_TESTS_DIR.glob("*.robot"), key=os.path.getmtime, reverse=True)
    return [
        {
            "filename": f.name,
            "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
            "size_bytes": f.stat().st_size,
        }
        for f in files
    ]


@app.get("/api/generated-tests/{filename}")
async def download_test(filename: str):
    """Download a generated .robot file."""
    filepath = GENERATED_TESTS_DIR / filename
    if not filepath.exists():
        return {"error": "File not found"}
    return FileResponse(filepath, filename=filename, media_type="text/plain")


@app.get("/api/health")
async def health():
    """Health check — verifies playwright-cli and AI provider."""
    cli_ok = False
    cli_version = "not found"
    try:
        result = subprocess.run(
            f"{PLAYWRIGHT_CLI} --version",
            shell=True,
            capture_output=True,
            encoding="utf-8",
            timeout=10,
        )
        cli_ok = result.returncode == 0
        cli_version = result.stdout.strip() if cli_ok else "not found"
    except Exception:
        pass

    return {
        "status": "ok" if cli_ok else "degraded",
        "playwright_cli": {"installed": cli_ok, "version": cli_version},
        "ai_provider": ai_service.provider_display,
    }


# ─── Serve React UI ──────────────────────────────────────────────

@app.get("/")
async def serve_ui():
    """Serve the standalone HTML UI."""
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h2>Place index.html in the same directory as app.py</h2>")


# ─── Run ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print(f"\n{'='*50}")
    print(f"  NLP Test Generator")
    print(f"  AI Provider: {ai_service.provider_display}")
    print(f"  Server: http://{host}:{port}")
    print(f"  WebSocket: ws://{host}:{port}/nlp-test/ws")
    print(f"  Health: http://{host}:{port}/api/health")
    print(f"{'='*50}\n")
    uvicorn.run("app:app", host=host, port=port, reload=True)
