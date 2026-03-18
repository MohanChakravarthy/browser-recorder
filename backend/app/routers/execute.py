import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.models.execution import ExecuteRequest
from app.services.script_executor import ScriptExecutor

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/execute")
async def execute_script(request: Request, body: ExecuteRequest) -> StreamingResponse:
    """
    Execute a generated automation script and stream the output as SSE.

    Accepts a script type and content, runs it as a subprocess,
    and streams stdout/stderr/exit events back to the client.
    """
    browser_manager = request.app.state.browser_manager
    cdp_endpoint = browser_manager.get_cdp_endpoint()

    executor = ScriptExecutor()

    return StreamingResponse(
        executor.execute(
            script_type=body.script_type,
            script_content=body.script_content,
            cdp_endpoint=cdp_endpoint,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
