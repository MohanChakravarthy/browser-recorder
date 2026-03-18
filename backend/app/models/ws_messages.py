from typing import Optional, Literal, Any
from pydantic import BaseModel, Field


class InputMessage(BaseModel):
    type: Literal["mouse", "keyboard", "scroll", "navigate", "control"]
    # Mouse fields
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None
    event: Optional[str] = None  # mousedown, mouseup, mousemove, click, dblclick, keydown, keyup
    click_count: Optional[int] = None
    # Keyboard fields
    key: Optional[str] = None
    code: Optional[str] = None
    text: Optional[str] = None
    shift: Optional[bool] = None
    ctrl: Optional[bool] = None
    alt: Optional[bool] = None
    meta: Optional[bool] = None
    # Scroll fields
    deltaX: Optional[float] = Field(None, alias="deltaX")
    deltaY: Optional[float] = Field(None, alias="deltaY")
    # Navigate fields
    url: Optional[str] = None
    # Control fields
    command: Optional[str] = None

    model_config = {"populate_by_name": True}

    def get_modifiers(self) -> int:
        """Convert boolean modifier flags to CDP modifier bitmask."""
        mods = 0
        if self.alt:
            mods |= 1
        if self.ctrl:
            mods |= 2
        if self.meta:
            mods |= 4
        if self.shift:
            mods |= 8
        return mods


class OutputMessage(BaseModel):
    type: Literal["nav_update", "recording_state", "action_recorded", "error"]
    url: Optional[str] = None
    state: Optional[str] = None  # RecordingState string for frontend
    action: Optional[Any] = None
    message: Optional[str] = None
