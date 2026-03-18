import logging

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class BrowserStatus(BaseModel):
    current_url: str
    is_recording: bool


class NavigateRequest(BaseModel):
    url: str


@router.get("/api/browser/status", response_model=BrowserStatus)
async def browser_status(request: Request) -> BrowserStatus:
    """Return the current browser URL and recording state."""
    browser_manager = request.app.state.browser_manager
    action_recorder = request.app.state.action_recorder

    return BrowserStatus(
        current_url=browser_manager.get_current_url(),
        is_recording=action_recorder.is_recording,
    )


@router.post("/api/browser/navigate")
async def navigate(request: Request, body: NavigateRequest) -> dict:
    """Navigate the browser to the specified URL."""
    browser_manager = request.app.state.browser_manager

    try:
        await browser_manager.navigate(body.url)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Navigation failed: {str(e)}",
        )

    return {
        "status": "ok",
        "url": browser_manager.get_current_url(),
    }
