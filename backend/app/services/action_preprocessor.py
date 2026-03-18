import logging
from typing import List

from app.models.actions import RawAction, ProcessedAction, ElementContext

logger = logging.getLogger(__name__)


def _same_element(a: ElementContext | None, b: ElementContext | None) -> bool:
    """Check if two elements are the same target (for deduplication)."""
    if a is None or b is None:
        return a is None and b is None
    # Same if they share id, css_selector, or (tag + name)
    if a.id and a.id == b.id:
        return True
    if a.css_selector and a.css_selector == b.css_selector:
        return True
    if a.xpath and a.xpath == b.xpath:
        return True
    return False


class ActionPreprocessor:
    """Preprocesses raw actions into a cleaner list suitable for script generation."""

    @staticmethod
    def process(raw_actions: List[RawAction]) -> List[ProcessedAction]:
        if not raw_actions:
            return []

        processed: List[ProcessedAction] = []

        # ---- Pass 1: Collapse consecutive keydowns into type actions ----
        consolidated: List[RawAction] = []
        i = 0
        while i < len(raw_actions):
            action = raw_actions[i]

            if action.action_type == "keydown" and action.key and len(action.key) == 1:
                chars = [action.key]
                element = action.element
                timestamp = action.timestamp
                j = i + 1
                while j < len(raw_actions):
                    nxt = raw_actions[j]
                    if (
                        nxt.action_type == "keydown"
                        and nxt.key
                        and len(nxt.key) == 1
                        and (nxt.timestamp - timestamp) < 2.0
                    ):
                        chars.append(nxt.key)
                        timestamp = nxt.timestamp
                        j += 1
                    else:
                        break
                if len(chars) > 1:
                    consolidated.append(
                        RawAction(
                            action_type="type",
                            timestamp=action.timestamp,
                            text="".join(chars),
                            element=element,
                        )
                    )
                    i = j
                    continue
                else:
                    consolidated.append(action)
                    i += 1
            else:
                consolidated.append(action)
                i += 1

        # ---- Pass 2: Collapse type + editing-keypress sequences on same element ----
        # When a user types "pa", backspaces, types "Password123", we get:
        #   type "pa" → keydown Backspace → keydown Backspace → type "p" → ... → type "Password123"
        # The LAST type event has the correct final value — collapse everything.
        EDITING_KEYS = {"Backspace", "Delete", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"}
        deduped: List[RawAction] = []
        i = 0
        while i < len(consolidated):
            action = consolidated[i]
            if action.action_type == "type":
                # Start of a typing sequence — look ahead for more type/editing events
                last_type = action
                j = i + 1
                while j < len(consolidated):
                    nxt = consolidated[j]
                    if nxt.action_type == "type" and _same_element(nxt.element, action.element):
                        last_type = nxt
                        j += 1
                    elif (
                        nxt.action_type == "keydown"
                        and nxt.key in EDITING_KEYS
                        and _same_element(nxt.element, action.element)
                    ):
                        # Skip editing keypresses within the same typing sequence
                        j += 1
                    else:
                        break
                # Keep only the last type event (has the final field value)
                deduped.append(last_type)
                i = j
            else:
                deduped.append(action)
                i += 1

        # ---- Pass 3: Remove duplicate clicks and filter ----
        filtered: List[RawAction] = []
        for i, action in enumerate(deduped):
            if action.action_type == "click" and i > 0:
                prev = deduped[i - 1]
                if (
                    prev.action_type == "click"
                    and prev.x == action.x
                    and prev.y == action.y
                    and abs(action.timestamp - prev.timestamp) < 0.1
                ):
                    continue

            # Skip click if the next action is a type on the same element
            # (clicking an input field before typing is implicit)
            if action.action_type == "click" and i + 1 < len(deduped):
                nxt = deduped[i + 1]
                if nxt.action_type == "type" and _same_element(nxt.element, action.element):
                    continue

            filtered.append(action)

        # ---- Pass 4: Convert to ProcessedAction and add waits ----
        for i, action in enumerate(filtered):
            if i > 0:
                gap = action.timestamp - filtered[i - 1].timestamp
                if gap > 2.0:
                    processed.append(
                        ProcessedAction(
                            action_type="wait",
                            description=f"Wait {gap:.1f} seconds",
                            wait_time=gap,
                        )
                    )

            if action.action_type == "click":
                desc = _describe_element("Click on", action.element)
                processed.append(
                    ProcessedAction(
                        action_type="click",
                        description=desc,
                        element=action.element,
                    )
                )

            elif action.action_type == "dblclick":
                desc = _describe_element("Double-click on", action.element)
                processed.append(
                    ProcessedAction(
                        action_type="dblclick",
                        description=desc,
                        element=action.element,
                    )
                )

            elif action.action_type == "type":
                desc = _describe_element(
                    f"Type '{action.text}' into", action.element
                )
                processed.append(
                    ProcessedAction(
                        action_type="type",
                        description=desc,
                        element=action.element,
                        value=action.text,
                    )
                )

            elif action.action_type == "keydown":
                processed.append(
                    ProcessedAction(
                        action_type="keypress",
                        description=f"Press '{action.key}' key",
                        element=action.element,
                        value=action.key,
                    )
                )

            elif action.action_type == "scroll":
                processed.append(
                    ProcessedAction(
                        action_type="scroll",
                        description="Scroll the page",
                    )
                )

            elif action.action_type == "navigate":
                processed.append(
                    ProcessedAction(
                        action_type="navigate",
                        description=f"Navigate to {action.url}",
                        url=action.url,
                    )
                )

        logger.info(
            f"Preprocessed {len(raw_actions)} raw actions into {len(processed)} processed actions."
        )
        return processed


def _describe_element(prefix: str, element: ElementContext | None) -> str:
    """Generate a human-readable description of an element interaction."""
    if element is None:
        return f"{prefix} element"

    if element.aria_label:
        return f"{prefix} '{element.aria_label}'"
    if element.text_content and len(element.text_content) < 50:
        return f"{prefix} '{element.text_content}'"
    if element.placeholder:
        return f"{prefix} '{element.placeholder}' field"
    if element.name:
        return f"{prefix} '{element.name}' field"
    if element.id:
        return f"{prefix} #{element.id}"
    if element.role:
        return f"{prefix} {element.role}"
    if element.tag:
        return f"{prefix} <{element.tag}>"

    return f"{prefix} element"
