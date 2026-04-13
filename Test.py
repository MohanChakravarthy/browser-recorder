"""
NLP Test Generator — Production Server
Run: python app.py
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

app = FastAPI(title="NLP Test Generator", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

PLAYWRIGHT_CLI = os.getenv("PLAYWRIGHT_CLI_PATH", "playwright-cli")
WORKSPACE_DIR = Path(os.getenv("NLP_WORKSPACE", os.path.join(tempfile.gettempdir(), "nlp-test-workspaces")))
GENERATED_TESTS_DIR = Path("./generated_tests")
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_TESTS_DIR.mkdir(parents=True, exist_ok=True)

ai_service = AIService()
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

SKIP_SCREENSHOT_ACTIONS = {"check", "uncheck", "hover", "press_key", "wait"}
PAGE_CHANGE_WORDS = ["submit", "save", "create", "delete", "send", "login", "sign", "confirm", "add", "remove", "update", "navigate", "go to", "open"]

# ─── Credential Manager ──────────────────────────────────────────

class CredentialManager:
    """Ensures credentials never leak into AI responses, RF scripts, or logs."""

    def __init__(self, username: str = "", password: str = "", start_url: str = ""):
        self.username = username
        self.password = password
        self.start_url = start_url

    def mask(self, text: str) -> str:
        """Replace real credentials with ${VAR} for output/logging."""
        result = text
        if self.password and self.password in result:
            result = result.replace(self.password, "${PASSWORD}")
        if self.username and self.username in result:
            result = result.replace(self.username, "${USERNAME}")
        return result

    def unmask(self, text: str) -> str:
        """Replace ${VAR} with real values for playwright-cli execution."""
        result = text
        if "${USERNAME}" in result and self.username:
            result = result.replace("${USERNAME}", self.username)
        if "${PASSWORD}" in result and self.password:
            result = result.replace("${PASSWORD}", self.password)
        return result

    def get_real_value(self, step: dict) -> str:
        """Get the real value for a fill action, resolving credential placeholders."""
        value = step.get("value", "")
        if not value:
            return ""
        return self.unmask(str(value))

    def mask_rf_line(self, rf_line: str) -> str:
        """Mask any credential leaks in generated RF lines."""
        return self.mask(rf_line)

    def get_rf_variables(self) -> dict:
        variables = {}
        if self.username:
            variables["USERNAME"] = "SET_AT_RUNTIME"
        if self.password:
            variables["PASSWORD"] = "SET_AT_RUNTIME"
        return variables


# ─── Subprocess ───────────────────────────────────────────────────

async def run_cli(command: str, session: str = "default", cwd: str = "", timeout: float = 30.0) -> dict:
    full_cmd = f"{PLAYWRIGHT_CLI} -s={session} {command}"
    work_dir = cwd or str(WORKSPACE_DIR)
    print(f"  [CLI] {full_cmd}")

    def _run():
        try:
            result = subprocess.run(
                full_cmd, shell=True, capture_output=True,
                cwd=work_dir, timeout=timeout, encoding="utf-8", errors="replace",
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Command timed out", -1
        except Exception as e:
            return "", str(e), -1

    loop = asyncio.get_event_loop()
    stdout_str, stderr_str, returncode = await loop.run_in_executor(_executor, _run)

    print(f"  [CLI return={returncode}] stdout={stdout_str[:300]}")
    if stderr_str.strip():
        print(f"  [CLI stderr] {stderr_str[:200]}")

    snapshot_file = None
    for line in stdout_str.split("\n"):
        m = re.search(r"(\.playwright-cli[/\\][^\s\)\]]+\.yml)", line)
        if m:
            snapshot_file = os.path.join(work_dir, m.group(1))

    screenshot_file = None
    for line in stdout_str.split("\n"):
        m = re.search(r"(\.playwright-cli[/\\][^\s\)\]]+\.png)", line)
        if m:
            screenshot_file = os.path.join(work_dir, m.group(1))

    return {
        "stdout": stdout_str, "stderr": stderr_str, "returncode": returncode,
        "snapshot_file": snapshot_file, "screenshot_file": screenshot_file,
    }


def read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (FileNotFoundError, IOError):
        return ""

def find_latest(directory: str, pattern: str) -> Optional[str]:
    files = sorted(glob.glob(os.path.join(directory, pattern)), key=os.path.getmtime, reverse=True)
    return files[0] if files else None

def to_base64(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except (FileNotFoundError, IOError):
        return None

def extract_pw_code(stdout: str) -> Optional[str]:
    for line in stdout.strip().split("\n"):
        line = line.strip()
        if line.startswith("await page.") or line.startswith("page."):
            return line
    return None

def is_valid_ref(ref) -> bool:
    """Check if a ref from AI is actually valid — not null, None, empty, or literal 'null'."""
    if ref is None:
        return False
    ref_str = str(ref).strip().lower()
    if ref_str in ("null", "none", "", "undefined"):
        return False
    return True


# ─── Orchestrator ─────────────────────────────────────────────────

class Orchestrator:
    def __init__(self, session_id: str, ws: WebSocket, creds: CredentialManager):
        self.session_id = session_id
        self.ws = ws
        self.creds = creds
        self.workspace = str(WORKSPACE_DIR / session_id)
        self.cli_dir = os.path.join(self.workspace, ".playwright-cli")
        self.paused = False
        self.stopped = False
        self.rf_lines: list[str] = []
        self.steps: list[dict] = []
        self._cached_snapshot: str = ""
        self._cached_screenshot: Optional[str] = None

        os.makedirs(self.workspace, exist_ok=True)

    async def send(self, msg: dict):
        try:
            await self.ws.send_json(msg)
        except Exception:
            pass

    async def wait_if_paused(self):
        while self.paused and not self.stopped:
            await asyncio.sleep(0.3)

    async def take_screenshot(self) -> Optional[str]:
        result = await run_cli("screenshot", self.session_id, self.workspace)
        path = result.get("screenshot_file") or find_latest(self.cli_dir, "*.png")
        b64 = to_base64(path) if path else None
        if b64:
            self._cached_screenshot = b64
        return b64

    async def take_snapshot(self, force: bool = False) -> str:
        if not force and self._cached_snapshot:
            return self._cached_snapshot
        result = await run_cli("snapshot", self.session_id, self.workspace)
        path = result.get("snapshot_file") or find_latest(self.cli_dir, "*.yml")
        content = read_file(path) if path else ""
        if content:
            self._cached_snapshot = content
        return content

    def invalidate_cache(self):
        self._cached_snapshot = ""

    async def execute_step(self, step: dict, index: int) -> dict:
        action = step.get("action", "")
        description = step.get("description", "")
        pw_code = ""
        rf_line = ""

        await self.send({"type": "step_start", "index": index, "description": description, "action": action})

        try:
            # ── Navigate ──────────────────────────────
            if action == "navigate":
                target = step.get("target", "")
                real_target = self.creds.unmask(target)
                result = await run_cli(f"goto {real_target}", self.session_id, self.workspace)

                if result["returncode"] not in (0, None):
                    raise Exception(f"Navigation failed: {result['stderr'][:200]}")

                await asyncio.sleep(1.0)
                self.invalidate_cache()
                pw_code = f"page.goto('{self.creds.mask(target)}')"
                rf_line = f"    Go To    {self.creds.mask(target)}"

            # ── Wait ──────────────────────────────────
            elif action == "wait":
                duration = step.get("value", "2")
                await asyncio.sleep(float(duration))
                self.invalidate_cache()
                rf_line = f"    Sleep    {duration}s"
                pw_code = f"page.waitForTimeout({int(float(duration) * 1000)})"

            # ── Assertions ────────────────────────────
            elif action.startswith("assert"):
                snapshot = await self.take_snapshot(force=True)
                if not snapshot.strip():
                    raise Exception("Cannot take page snapshot for assertion — page may not be loaded")
                masked_snapshot = self.creds.mask(snapshot)
                assertion = await ai_service.generate_assertion(masked_snapshot, step)
                rf_line = assertion.get("full_line", f"    Log    MANUAL: {description}")
                pw_code = f"// Assertion: {description}"

            # ── Interactive (click, fill, etc.) ───────
            else:
                # Step 1: Get snapshot
                snapshot = await self.take_snapshot()
                if not snapshot.strip():
                    # Force a fresh snapshot
                    snapshot = await self.take_snapshot(force=True)
                if not snapshot.strip():
                    raise Exception("Cannot get page snapshot — page may not be loaded or browser may have crashed")

                masked_snapshot = self.creds.mask(snapshot)

                # Step 2: AI picks element ref
                element_info = await ai_service.pick_element(masked_snapshot, step)
                ref = element_info.get("ref")

                # Validate ref is real
                if not is_valid_ref(ref):
                    # Retry with forced fresh snapshot
                    print(f"  [RETRY] ref={ref} invalid, taking fresh snapshot...")
                    self.invalidate_cache()
                    snapshot = await self.take_snapshot(force=True)
                    if not snapshot.strip():
                        raise Exception(f"Page snapshot is empty — cannot find element for: {description}")
                    masked_snapshot = self.creds.mask(snapshot)
                    element_info = await ai_service.pick_element(masked_snapshot, step)
                    ref = element_info.get("ref")

                if not is_valid_ref(ref):
                    raise Exception(
                        f"Element not found for: {description}. "
                        f"AI said: {element_info.get('reasoning', 'no reasoning')}. "
                        f"Page may not have loaded the expected content yet."
                    )

                # Step 3: Build CLI command with REAL credentials
                if action == "fill":
                    real_value = self.creds.get_real_value(step)
                    if not real_value:
                        real_value = step.get("value", "")
                    cli_cmd = f'fill {ref} "{real_value}"'
                elif action == "select":
                    real_value = self.creds.get_real_value(step)
                    cli_cmd = f'select {ref} "{real_value}"'
                elif action == "check":
                    cli_cmd = f"check {ref}"
                elif action == "uncheck":
                    cli_cmd = f"uncheck {ref}"
                elif action == "hover":
                    cli_cmd = f"hover {ref}"
                elif action == "press_key":
                    key = step.get("value", "Enter")
                    cli_cmd = f"press {key}"
                else:
                    cli_cmd = f"click {ref}"

                # Step 4: Execute
                result = await run_cli(cli_cmd, self.session_id, self.workspace)
                self.invalidate_cache()

                # Step 5: Validate execution
                if result["returncode"] not in (0, None):
                    error = result["stderr"].strip() or result["stdout"].strip()
                    raise Exception(f"Action failed ({cli_cmd}): {error[:200]}")

                # Check if stdout indicates an error
                stdout_lower = result["stdout"].lower()
                if "error" in stdout_lower and "element not found" in stdout_lower:
                    raise Exception(f"Element {ref} not found on page")

                # Step 6: Smart wait for page-changing actions
                if action == "click" and any(w in description.lower() for w in PAGE_CHANGE_WORDS):
                    await asyncio.sleep(1.5)
                elif action == "fill":
                    await asyncio.sleep(0.2)  # tiny pause for reactivity

                # Step 7: Extract playwright_code and convert to RF
                pw_code = extract_pw_code(result["stdout"])

                if pw_code:
                    clean = pw_code.lstrip("await ")
                    if clean.startswith("await "):
                        clean = clean[6:]
                    rf_line = playwright_to_rf(clean)
                else:
                    # Fallback: build RF line from what we know
                    if action == "click":
                        rf_line = f"    Click    ref={ref}"
                    elif action == "fill":
                        masked_val = self.creds.mask(step.get("value", ""))
                        rf_line = f"    Fill Text    ref={ref}    {masked_val}"
                    else:
                        rf_line = f"    # Action: {action} on ref={ref}"

                # Mask credentials in output
                pw_code = self.creds.mask(pw_code or "")
                rf_line = self.creds.mask_rf_line(rf_line)

            # ── Screenshot (conditional) ──────────────
            if action in SKIP_SCREENSHOT_ACTIONS:
                screenshot_b64 = self._cached_screenshot
            else:
                screenshot_b64 = await self.take_screenshot()

            self.rf_lines.append(rf_line)

            return {
                "status": "success",
                "rf_line": rf_line,
                "playwright_code": pw_code,
                "screenshot_b64": screenshot_b64,
                "error": None,
            }

        except Exception as e:
            screenshot_b64 = await self.take_screenshot()
            error_msg = self.creds.mask(str(e))
            print(f"  [STEP FAILED] {error_msg}")
            self.rf_lines.append(f"    # FAILED: {description}")

            return {
                "status": "failed",
                "rf_line": f"    # FAILED: {description}",
                "playwright_code": "",
                "screenshot_b64": screenshot_b64,
                "error": error_msg,
            }

    async def run(self, nlp_input: str, start_url: str):
        try:
            # ── 1. Plan steps ─────────────────────────
            await self.send({"type": "status", "message": f"Planning steps with {ai_service.provider_display}..."})

            # Pass credentials to AI so it generates correct fill values
            # AI sees the real credentials ONLY for step planning — they get masked everywhere else
            self.steps = await ai_service.break_into_steps(
                nlp_input, start_url,
                username=self.creds.username,
                password=self.creds.password,
            )

            if not self.steps:
                await self.send({"type": "error", "message": "AI returned no steps. Try a more specific test description."})
                return

            await self.send({"type": "steps_planned", "steps": self.steps, "total": len(self.steps)})

            print(f"\n[Plan] {len(self.steps)} steps:")
            for s in self.steps:
                safe_desc = self.creds.mask(s.get('description', ''))
                safe_val = self.creds.mask(str(s.get('value', '')))
                print(f"  {s['step']}. [{s['action']}] {safe_desc} {f'({safe_val})' if safe_val else ''}")

            # ── 2. Open browser ───────────────────────
            await self.send({"type": "status", "message": "Opening browser..."})
            result = await run_cli(f"open {start_url}", self.session_id, self.workspace)

            if result["returncode"] not in (0, None):
                await self.send({"type": "error", "message": f"Browser failed: {result['stderr'][:300]}"})
                return

            # Verify browser actually opened
            await asyncio.sleep(2.0)
            snapshot = await self.take_snapshot(force=True)
            if not snapshot.strip():
                await self.send({"type": "error", "message": "Browser opened but page failed to load. Check the URL."})
                return

            screenshot_b64 = await self.take_screenshot()
            if screenshot_b64:
                await self.send({
                    "type": "step_complete", "index": -1, "status": "success",
                    "screenshot_b64": screenshot_b64,
                    "rf_line": "    New Page    ${BASE_URL}",
                    "playwright_code": "page.goto(url)",
                })

            # ── 3. Execute steps ──────────────────────
            passed = 0
            failed = 0

            for i, step in enumerate(self.steps):
                if self.stopped:
                    await self.send({"type": "status", "message": "Stopped by user."})
                    break

                await self.wait_if_paused()

                # Skip initial navigate if it matches start URL
                if i == 0 and step.get("action") == "navigate":
                    target = step.get("target", "")
                    if not target or target == "/" or target == start_url or start_url.endswith(target):
                        self.rf_lines.append("    # Initial navigation — handled by New Page")
                        await self.send({
                            "type": "step_complete", "index": i, "status": "skipped",
                            "screenshot_b64": screenshot_b64,
                            "rf_line": "    # Initial navigation — handled by New Page",
                            "playwright_code": "",
                        })
                        passed += 1
                        continue

                safe_desc = self.creds.mask(step.get('description', ''))
                print(f"\n[Step {i+1}/{len(self.steps)}] {step['action']}: {safe_desc}")

                step_result = await self.execute_step(step, i)

                if step_result["status"] == "success":
                    passed += 1
                    await self.send({
                        "type": "step_complete", "index": i, "status": "success",
                        "screenshot_b64": step_result["screenshot_b64"],
                        "rf_line": step_result["rf_line"],
                        "playwright_code": step_result["playwright_code"],
                    })
                    print(f"  ✓ {step_result['rf_line'].strip()}")
                else:
                    failed += 1
                    await self.send({
                        "type": "step_failed", "index": i,
                        "error": step_result["error"],
                        screenshot_b64": step_result["screenshot_b64"],
                    })
                    print(f"  ✗ {step_result['error']}")

                await asyncio.sleep(0.3)

            # ── 4. Generate .robot file ───────────────
            test_name = re.sub(r"[^\w\s]", "", nlp_input)[:60].strip().title()
            robot_script = assemble_robot_file(
                test_name=test_name,
                test_description=self.creds.mask(nlp_input),
                base_url=start_url,
                rf_lines=self.rf_lines,
                variables=self.creds.get_rf_variables(),
            )
            # Final mask pass on entire script
            robot_script = self.creds.mask(robot_script)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_{timestamp}.robot"
            filepath = GENERATED_TESTS_DIR / filename
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(robot_script)

            await self.send({"type": "rf_script_complete", "script": robot_script, "filename": filename})
            await self.send({"type": "execution_complete", "total_steps": len(self.steps), "passed": passed, "failed": failed})
            print(f"\n[Done] {passed}✓ {failed}✗ → {filename}")
            await run_cli("close", self.session_id, self.workspace)

        except Exception as e:
            print(f"\n[Error]\n{traceback.format_exc()}")
            await self.send({"type": "error", "message": self.creds.mask(str(e)) or traceback.format_exc()[-500:]})


# ─── WebSocket ────────────────────────────────────────────────────

@app.websocket("/nlp-test/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())[:8]
    orchestrator: Optional[Orchestrator] = None
    task: Optional[asyncio.Task] = None
    await websocket.send_json({"type": "connected", "session_id": session_id})
    print(f"\n[WS] Connected: {session_id}")

    try:
        while True:
            data = await websocket.receive_json()
            t = data.get("type")

            if t == "start":
                nlp = data.get("nlp_input", "").strip()
                url = data.get("start_url", "").strip()
                user = data.get("username", "").strip()
                pwd = data.get("password", "").strip()

                if not nlp or not url:
                    await websocket.send_json({"type": "error", "message": "URL and test description required."})
                    continue

                print(f"\n[Start] URL: {url}")
                print(f"[Start] NLP: {nlp}")
                print(f"[Start] Creds: {'provided' if user else 'none'}")

                creds = CredentialManager(user, pwd, url)
                orchestrator = Orchestrator(session_id, websocket, creds)
                task = asyncio.create_task(orchestrator.run(nlp, url))

            elif t == "pause" and orchestrator:
                orchestrator.paused = True
                await websocket.send_json({"type": "status", "message": "Paused."})
            elif t == "resume" and orchestrator:
                orchestrator.paused = False
                await websocket.send_json({"type": "status", "message": "Resumed."})
            elif t == "stop" and orchestrator:
                orchestrator.stopped = True
                if task: task.cancel()
                await websocket.send_json({"type": "status", "message": "Stopped."})
            elif t == "retry_step" and orchestrator and orchestrator.steps:
                idx = data.get("step_index", 0)
                if 0 <= idx < len(orchestrator.steps):
                    r = await orchestrator.execute_step(orchestrator.steps[idx], idx)
                    k = "step_complete" if r["status"] == "success" else "step_failed"
                    await websocket.send_json({"type": k, "index": idx, **r})

    except WebSocketDisconnect:
        print(f"[WS] Disconnected: {session_id}")
        if orchestrator:
            orchestrator.stopped = True
            await run_cli("close", session_id, str(WORKSPACE_DIR / session_id))
    except Exception:
        print(f"[WS Error] {traceback.format_exc()}")


# ─── REST ─────────────────────────────────────────────────────────

@app.get("/api/generated-tests")
async def list_tests():
    files = sorted(GENERATED_TESTS_DIR.glob("*.robot"), key=os.path.getmtime, reverse=True)
    return [{"filename": f.name, "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(), "size_bytes": f.stat().st_size} for f in files]

@app.get("/api/generated-tests/{filename}")
async def download_test(filename: str):
    fp = GENERATED_TESTS_DIR / filename
    return FileResponse(fp, filename=filename) if fp.exists() else {"error": "Not found"}

@app.get("/api/health")
async def health():
    ok, ver = False, "not found"
    try:
        r = subprocess.run(f"{PLAYWRIGHT_CLI} --version", shell=True, capture_output=True, encoding="utf-8", timeout=10)
        ok = r.returncode == 0
        ver = r.stdout.strip() if ok else "not found"
    except Exception:
        pass
    return {"status": "ok" if ok else "degraded", "playwright_cli": {"installed": ok, "version": ver}, "ai_provider": ai_service.provider_display}

@app.get("/")
async def serve_ui():
    p = Path(__file__).parent / "index.html"
    return HTMLResponse(p.read_text(encoding="utf-8")) if p.exists() else HTMLResponse("<h2>index.html not found</h2>")

if __name__ == "__main__":
    import uvicorn
    host, port = os.getenv("HOST", "0.0.0.0"), int(os.getenv("PORT", "8000"))
    print(f"\n{'='*50}\n  NLP Test Generator v2\n  AI: {ai_service.provider_display}\n  http://{host}:{port}\n{'='*50}\n")
    uvicorn.run("app:app", host=host, port=port, reload=True)



         
