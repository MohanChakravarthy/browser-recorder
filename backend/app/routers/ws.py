import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.models.actions import RawAction, ElementContext
from app.models.ws_messages import InputMessage, OutputMessage
from app.services.action_recorder import ActionRecorder
from app.services.browser_manager import BrowserManager
from app.services.cdp_injector import CDPInjector

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for browser interaction.

    - Streams JPEG screenshot frames as binary messages.
    - Receives JSON commands for mouse, keyboard, scroll, navigation, and control.
    - Sends JSON messages for URL changes, recording state, and captured actions.
    """
    await websocket.accept()

    app = websocket.app
    browser_manager: BrowserManager = app.state.browser_manager
    action_recorder: ActionRecorder = app.state.action_recorder
    cdp_injector = CDPInjector()

    last_url: str = ""

    async def on_screencast_frame(frame_data: bytes) -> None:
        """Callback for screencast frames - sends binary JPEG data to client."""
        try:
            await websocket.send_bytes(frame_data)
        except Exception:
            pass

    async def on_action_captured(action_data: dict) -> None:
        """Callback for CDP-captured user actions."""
        try:
            element_data = action_data.pop("element", None)
            element = ElementContext(**element_data) if element_data else None
            raw_action = RawAction(
                action_type=action_data.get("action_type", "click"),
                timestamp=action_data.get("timestamp", time.time()),
                x=action_data.get("x"),
                y=action_data.get("y"),
                key=action_data.get("key"),
                text=action_data.get("text"),
                url=action_data.get("url"),
                element=element,
            )
            action_recorder.record_action(raw_action)

            # Notify client that an action was recorded
            msg = OutputMessage(
                type="action_recorded",
                action=raw_action.model_dump(),
            )
            await websocket.send_text(msg.model_dump_json())
        except Exception as e:
            logger.error(f"Error processing captured action: {e}")

    try:
        # Start screencast
        await browser_manager.start_screencast(on_screencast_frame)

        # Inject CDP script for action capturing
        cdp_session = await browser_manager.get_cdp_session()
        page = browser_manager.page
        if page:
            await cdp_injector.inject(cdp_session, page, on_action_captured)

        # Send initial URL
        current_url = browser_manager.get_current_url()
        last_url = current_url
        await websocket.send_text(
            OutputMessage(type="nav_update", url=current_url).model_dump_json()
        )

        # URL change polling task
        async def poll_url_changes() -> None:
            nonlocal last_url
            while True:
                await asyncio.sleep(0.5)
                try:
                    current = browser_manager.get_current_url()
                    if current != last_url:
                        last_url = current
                        msg = OutputMessage(type="nav_update", url=current)
                        await websocket.send_text(msg.model_dump_json())
                except Exception:
                    break

        url_task = asyncio.create_task(poll_url_changes())

        # Main receive loop
        try:
            while True:
                data = await websocket.receive()

                if "text" in data:
                    text = data["text"]
                    try:
                        msg_data = json.loads(text)
                        input_msg = InputMessage(**msg_data)
                        await _handle_input_message(
                            input_msg, browser_manager, action_recorder, websocket
                        )
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON received: {text}")
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        error_msg = OutputMessage(type="error", message=str(e))
                        await websocket.send_text(error_msg.model_dump_json())

                elif "bytes" in data:
                    # Ignore binary messages from client
                    pass

        except WebSocketDisconnect:
            logger.info("WebSocket disconnected.")
        finally:
            url_task.cancel()
            try:
                await url_task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected during setup.")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Only stop screencast if our callback is still the active one.
        # If a new WebSocket already reconnected and started a new screencast,
        # we must NOT kill it (race condition on page reload).
        if browser_manager._screencast_callback is on_screencast_frame:
            try:
                await browser_manager.stop_screencast()
            except Exception:
                pass


async def _handle_input_message(
    msg: InputMessage,
    browser_manager: BrowserManager,
    action_recorder: ActionRecorder,
    websocket: WebSocket,
) -> None:
    """Handle an input message from the WebSocket client."""

    if msg.type == "mouse":
        x = msg.x or 0
        y = msg.y or 0
        button = msg.button or "left"
        event_type = msg.event or "click"
        click_count = msg.click_count or 1

        # Map frontend event types to CDP event types
        if event_type == "mousedown":
            await browser_manager.dispatch_mouse_event(
                "mousePressed", x, y, button, click_count
            )
        elif event_type == "mouseup":
            await browser_manager.dispatch_mouse_event(
                "mouseReleased", x, y, button, click_count
            )
        elif event_type == "mousemove":
            await browser_manager.dispatch_mouse_event(
                "mouseMoved", x, y, "none", 0
            )
        elif event_type == "click":
            await browser_manager.dispatch_mouse_event(
                "mousePressed", x, y, button, click_count
            )
            await browser_manager.dispatch_mouse_event(
                "mouseReleased", x, y, button, click_count
            )
        elif event_type == "dblclick":
            await browser_manager.dispatch_mouse_event(
                "mousePressed", x, y, button, 2
            )
            await browser_manager.dispatch_mouse_event(
                "mouseReleased", x, y, button, 2
            )

    elif msg.type == "keyboard":
        key = msg.key or ""
        text = msg.text
        modifiers = msg.get_modifiers()
        event_type = msg.event or "keyDown"

        if event_type in ("keydown", "keyDown"):
            # dispatch_key_event handles keyDown + char for printable chars
            await browser_manager.dispatch_key_event("keyDown", key, text, modifiers)
        elif event_type in ("keyup", "keyUp"):
            await browser_manager.dispatch_key_event("keyUp", key, None, modifiers)

    elif msg.type == "scroll":
        x = msg.x or 0
        y = msg.y or 0
        delta_x = msg.deltaX or 0
        delta_y = msg.deltaY or 0
        await browser_manager.dispatch_scroll(x, y, delta_x, delta_y)

    elif msg.type == "navigate":
        url = msg.url or ""
        if url:
            try:
                await browser_manager.navigate(url)
            except Exception as e:
                logger.error(f"Navigation failed: {e}")
                error_msg = OutputMessage(type="error", message=f"Navigation failed: {e}")
                await websocket.send_text(error_msg.model_dump_json())
                return
            # Record navigation action
            action_recorder.record_action(
                RawAction(
                    action_type="navigate",
                    timestamp=time.time(),
                    url=url,
                )
            )
            # Send URL update
            current_url = browser_manager.get_current_url()
            nav_msg = OutputMessage(type="nav_update", url=current_url)
            await websocket.send_text(nav_msg.model_dump_json())

    elif msg.type == "control":
        command = msg.command or ""
        if command == "start_recording":
            current_url = browser_manager.get_current_url()
            action_recorder.start_recording(url=current_url)
            state_msg = OutputMessage(type="recording_state", state="recording")
            await websocket.send_text(state_msg.model_dump_json())
        elif command == "stop_recording":
            action_recorder.stop_recording()
            state_msg = OutputMessage(type="recording_state", state="stopped")
            await websocket.send_text(state_msg.model_dump_json())
        elif command == "get_status":
            # Send current state to the client (used on connect/reconnect)
            current_url = browser_manager.get_current_url()
            await websocket.send_text(
                OutputMessage(type="nav_update", url=current_url).model_dump_json()
            )
            rec_state = "recording" if action_recorder.is_recording else "idle"
            await websocket.send_text(
                OutputMessage(type="recording_state", state=rec_state).model_dump_json()
            )
