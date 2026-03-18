import asyncio
import json
import logging
import os
import re
import tempfile
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class ScriptExecutor:
    """Executes generated automation scripts and streams output as SSE events."""

    async def execute(
        self,
        script_type: str,
        script_content: str,
        cdp_endpoint: str = "",
    ) -> AsyncGenerator[str, None]:
        """
        Execute a script and yield SSE-formatted output lines.

        Args:
            script_type: One of 'playwright_python', 'robot_framework', 'robot_selenium'.
            script_content: The script source code to execute.
            cdp_endpoint: CDP WebSocket endpoint for Playwright scripts to connect to.

        Yields:
            SSE-formatted strings: data: {"type": "stdout|stderr|exit", "data": "..."}
        """
        tmp_file = None
        try:
            # Determine file extension and command
            if script_type == "playwright_python":
                suffix = ".py"
                script_content = self._patch_playwright_script(
                    script_content, cdp_endpoint
                )
            elif script_type in ("robot_framework", "robot_selenium"):
                suffix = ".robot"
            else:
                yield self._sse_event("stderr", f"Unknown script type: {script_type}")
                yield self._sse_event("exit", "1")
                return

            # Write script to temp file
            tmp_file = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=suffix,
                delete=False,
                encoding="utf-8",
            )
            tmp_file.write(script_content)
            tmp_file.flush()
            tmp_file.close()

            # Build command
            if script_type == "playwright_python":
                cmd = ["python", tmp_file.name]
            else:
                cmd = ["python", "-m", "robot", "--outputdir", tempfile.gettempdir(), tmp_file.name]

            logger.info(f"Executing script: {' '.join(cmd)}")
            yield self._sse_event("stdout", f"Executing {script_type} script...")

            # Run as subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Stream stdout and stderr concurrently
            async def stream_output(
                stream: asyncio.StreamReader, stream_type: str
            ) -> None:
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").rstrip()
                    if decoded:
                        output_lines.append(self._sse_event(stream_type, decoded))

            output_lines: list[str] = []

            if process.stdout and process.stderr:
                await asyncio.gather(
                    stream_output(process.stdout, "stdout"),
                    stream_output(process.stderr, "stderr"),
                )

            await process.wait()

            for line in output_lines:
                yield line

            exit_code = process.returncode or 0
            yield self._sse_event("exit", str(exit_code))

        except Exception as e:
            logger.error(f"Script execution error: {e}")
            yield self._sse_event("stderr", f"Execution error: {str(e)}")
            yield self._sse_event("exit", "1")
        finally:
            # Clean up temp file
            if tmp_file and os.path.exists(tmp_file.name):
                try:
                    os.unlink(tmp_file.name)
                except OSError:
                    pass

    @staticmethod
    def _patch_playwright_script(script: str, cdp_endpoint: str) -> str:
        """
        Patch a Playwright script to connect via CDP instead of launching a new browser.

        Replaces launch() with connect_over_cdp() and new_page() with grabbing
        the existing page from the browser context.
        """
        if not cdp_endpoint:
            return script

        # Replace browser launch with CDP connection
        script = re.sub(
            r'browser\s*=\s*p\.chromium\.launch\([^)]*\)',
            f'browser = p.chromium.connect_over_cdp("{cdp_endpoint}")',
            script,
        )
        script = re.sub(
            r'browser\s*=\s*playwright\.chromium\.launch\([^)]*\)',
            f'browser = playwright.chromium.connect_over_cdp("{cdp_endpoint}")',
            script,
        )

        # Replace new_page() with grabbing existing page from CDP context
        script = re.sub(
            r'page\s*=\s*browser\.new_page\([^)]*\)',
            'page = browser.contexts[0].pages[0]',
            script,
        )

        # Remove browser.close() — we don't own the browser in CDP mode
        script = re.sub(
            r'^\s*browser\.close\(\)\s*$',
            '        pass  # browser managed externally',
            script,
            flags=re.MULTILINE,
        )

        return script

    @staticmethod
    def _sse_event(event_type: str, data: str) -> str:
        """Format an SSE event line."""
        payload = json.dumps({"type": event_type, "data": data})
        return f"data: {payload}\n\n"
