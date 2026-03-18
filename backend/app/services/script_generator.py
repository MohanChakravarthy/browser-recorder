import asyncio
import json
import logging
from typing import List

from google import genai
from google.genai import types

from app.models.actions import ProcessedAction
from app.models.scripts import ScriptOutput
from app.prompts.system_prompt import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

MODELS = ["gemini-2.0-flash", "gemini-1.5-flash"]


class ScriptGenerator:
    """Generates automation scripts from processed actions using Gemini."""

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    async def generate(
        self, actions: List[ProcessedAction], url: str
    ) -> ScriptOutput:
        actions_text = self._format_actions(actions, url)
        logger.info(f"Generating scripts for {len(actions)} actions at {url}")

        last_error = None
        for model in MODELS:
            for attempt in range(3):
                try:
                    response = await self._client.aio.models.generate_content(
                        model=model,
                        contents=actions_text,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            response_mime_type="application/json",
                            temperature=0.1,
                        ),
                    )
                    content = response.text
                    if not content:
                        raise ValueError("Empty response")
                    result = json.loads(content)
                    return ScriptOutput(
                        playwright_python=result.get("playwright_python", ""),
                        robot_framework=result.get("robot_framework", ""),
                        robot_selenium=result.get("robot_selenium", ""),
                    )
                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                        wait = (attempt + 1) * 6
                        logger.warning(f"{model} rate limited, retry in {wait}s (attempt {attempt+1})")
                        await asyncio.sleep(wait)
                    else:
                        logger.error(f"{model} failed: {e}")
                        break  # non-retryable, try next model
            logger.warning(f"Model {model} exhausted, trying next")

        raise ValueError(f"All models failed. Last error: {last_error}")

    @staticmethod
    def _format_actions(actions: List[ProcessedAction], url: str) -> str:
        """Format processed actions into a structured text representation."""
        lines = [
            f"Starting URL: {url}",
            f"Total actions: {len(actions)}",
            "",
            "Recorded Actions:",
            "=" * 50,
        ]

        for i, action in enumerate(actions, 1):
            lines.append(f"\nStep {i}: {action.description}")
            lines.append(f"  Action Type: {action.action_type}")

            if action.value:
                lines.append(f"  Value: {action.value}")
            if action.url:
                lines.append(f"  URL: {action.url}")
            if action.wait_time:
                lines.append(f"  Wait Time: {action.wait_time:.1f}s")

            if action.element:
                el = action.element
                lines.append("  Element:")
                if el.tag:
                    lines.append(f"    Tag: {el.tag}")
                if el.data_testid:
                    lines.append(f"    data-testid: {el.data_testid}")
                if el.data_cy:
                    lines.append(f"    data-cy: {el.data_cy}")
                if el.data_qa:
                    lines.append(f"    data-qa: {el.data_qa}")
                if el.data_id:
                    lines.append(f"    data-id: {el.data_id}")
                if el.aria_label:
                    lines.append(f"    aria-label: {el.aria_label}")
                if el.aria_labelledby:
                    lines.append(f"    aria-labelledby: {el.aria_labelledby}")
                if el.role:
                    lines.append(f"    role: {el.role}")
                if el.text_content:
                    lines.append(f"    text: {el.text_content}")
                if el.id:
                    lines.append(f"    id: {el.id}")
                if el.name:
                    lines.append(f"    name: {el.name}")
                if el.placeholder:
                    lines.append(f"    placeholder: {el.placeholder}")
                if el.title:
                    lines.append(f"    title: {el.title}")
                if el.href:
                    lines.append(f"    href: {el.href}")
                if el.input_type:
                    lines.append(f"    type: {el.input_type}")
                if el.locator_strategy:
                    lines.append(f"    best-locator: {el.locator_strategy}")
                if el.css_selector:
                    lines.append(f"    CSS: {el.css_selector}")
                if el.xpath:
                    lines.append(f"    XPath: {el.xpath}")

        return "\n".join(lines)
