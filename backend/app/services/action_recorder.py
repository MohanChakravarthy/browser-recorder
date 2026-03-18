import logging
from typing import List, Optional

from app.models.actions import RawAction

logger = logging.getLogger(__name__)


class ActionRecorder:
    """Records raw browser actions captured during a recording session."""

    def __init__(self) -> None:
        self._actions: List[RawAction] = []
        self._is_recording: bool = False
        self._start_url: Optional[str] = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def start_url(self) -> Optional[str]:
        return self._start_url

    def start_recording(self, url: str = "") -> None:
        """Start a new recording session, clearing any previous actions."""
        self._actions.clear()
        self._is_recording = True
        self._start_url = url
        logger.info(f"Recording started. Start URL: {url}")

    def stop_recording(self) -> None:
        """Stop the current recording session."""
        self._is_recording = False
        logger.info(f"Recording stopped. {len(self._actions)} actions recorded.")

    def record_action(self, action: RawAction) -> None:
        """Record an action if currently recording."""
        if self._is_recording:
            self._actions.append(action)
            logger.info(f"Action recorded: {action.action_type} (total: {len(self._actions)})")

    def get_actions(self) -> List[RawAction]:
        """Return a copy of all recorded actions."""
        return list(self._actions)
