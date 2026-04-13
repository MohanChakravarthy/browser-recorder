"""
AI Service — Production-grade with credential-aware prompts.
Supports Azure OpenAI (via openai SDK) and Google Gemini.
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
- Use clear, specific descriptions that match what the user would see on screen
- First step should always be navigation if a URL context is given
- Think about what a manual tester would do step by step

CREDENTIAL HANDLING:
{credential_section}

CUSTOM DROPDOWNS:
Modern UI frameworks (MUI, Bootstrap, Angular Material) do NOT use native <select> elements. Their dropdowns require TWO steps:
1. Click the dropdown trigger to open it
2. Click the option from the opened list

MODALS AND DIALOGS:
After clicking a button that opens a modal/dialog, add a wait step (1-2 seconds) before interacting with modal contents.

FORM SUBMISSIONS:
After clicking submit/save/create/delete/login buttons, add a wait step (2 seconds) for the response before any assertion.

OUTPUT FORMAT - respond ONLY with a valid JSON array, no markdown fences, no explanation:
[
  {{"step": 1, "action": "navigate", "description": "Navigate to the application", "target": "/login"}},
  {{"step": 2, "action": "fill", "description": "Enter username", "target": "username/email field", "value": "the_username_value"}},
  {{"step": 3, "action": "fill", "description": "Enter password", "target": "password field", "value": "the_password_value"}},
  {{"step": 4, "action": "click", "description": "Click the Login button", "target": "Login button"}},
  {{"step": 5, "action": "wait", "description": "Wait for login to complete", "value": "2"}},
  {{"step": 6, "action": "assert_url", "description": "Verify redirected to dashboard", "expected": "/dashboard"}}
]

Valid actions: navigate, click, fill, select, check, uncheck, hover, press_key, upload, assert_text, assert_visible, assert_url, assert_element_count, wait
"""

CREDENTIAL_WITH = """The user has provided login credentials:
- Username/email: {username}
- Password: {password}
When the test involves login or authentication, use EXACTLY these values in the fill steps.
The "value" field for username fill must be exactly: {username}
The "value" field for password fill must be exactly: {password}
Do NOT skip the credential fill steps. Do NOT use placeholder values."""

CREDENTIAL_WITHOUT = """No credentials were provided. If the test involves login, use descriptive placeholders like "test_user" and "test_password" as values."""

PICK_ELEMENT_PROMPT = """You are a browser automation expert. Given a YAML snapshot of a web page and a step description, identify the SINGLE correct element ref to interact with.

RULES:
- Return the exact ref string (like "e15", "e42") from the snapshot
- Consider the step description, element roles, names, labels, and surrounding context
- If the step says "first" or mentions order, pick the first matching element
- For login forms: textbox/input near "email"/"username" label is the username field, textbox near "password" label is the password field
- For buttons: match by visible text or aria-label
- If ABSOLUTELY no matching element exists, return ref as null — but try hard to find a match first

CRITICAL: The ref MUST be an actual element reference from the snapshot (like "e15"). Never return "null" unless you truly cannot find any matching element.

OUTPUT FORMAT - respond ONLY with valid JSON, no markdown:
{{"ref": "e15", "confidence": "high", "reasoning": "The textbox labeled 'Email' matches the username field"}}
"""

ASSERTION_PROMPT = """You are a QA automation expert generating Robot Framework Browser library assertions.

Given a YAML snapshot and an assertion step, generate the correct RF Browser assertion.

AVAILABLE KEYWORDS:
- Get Text    <locator>    ==    <expected>        (exact match)
- Get Text    <locator>    *=    <expected>        (contains)
- Get Url    ==    <expected>                       (exact URL)
- Get Url    *=    <expected>                       (URL contains)
- Get Element States    <locator>    contains    visible
- Get Element States    <locator>    contains    enabled
- Get Element Count    <locator>    ==    <count>
- Get Title    ==    <expected>
- Get Title    *=    <expected>

LOCATOR PRIORITY (pick the highest available from the snapshot):
1. [data-testid="value"]
2. id=value (skip if auto-generated like mat-input-7, :r1:)
3. role=type[name="value"]
4. text=visible text
5. [placeholder="value"]
6. [aria-label="value"]
7. css=meaningful-selector

OUTPUT FORMAT - respond ONLY with valid JSON, no markdown:
{{"rf_keyword": "Get Text", "locator": "[data-testid=\\"msg\\"]", "operator": "*=", "expected_value": "Welcome", "full_line": "    Get Text    [data-testid=\\"msg\\"]    *=    Welcome"}}
"""


# ─── Providers ────────────────────────────────────────────────────

class AzureOpenAIProvider:
    def __init__(self):
        from openai import OpenAI
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.base_url = os.getenv("AZURE_OPENAI_BASE_URL", "")
        self.model = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o")
        if not self.api_key:
            raise ValueError("AZURE_OPENAI_API_KEY not set")
        if not self.base_url:
            raise ValueError("AZURE_OPENAI_BASE_URL not set")
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self._model = self.model

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


class GeminiProvider:
    def __init__(self):
        from google import genai
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")
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


# ─── AI Service ───────────────────────────────────────────────────

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
            raise ValueError(f"Unknown AI_PROVIDER: '{provider_name}'. Use 'azure_openai' or 'gemini'")
        print(f"[AI Service] Provider: {self.provider_display}")

    def _clean(self, content: str) -> str:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        return content.strip()

    def _parse_json(self, text: str, fallback=None):
        cleaned = self._clean(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from text
            match = re.search(r"[\[{].*[\]}]", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return fallback

    async def break_into_steps(self, nlp_input: str, start_url: str,
                                username: str = "", password: str = "") -> list[dict]:
        """Break NLP into steps. Credentials are passed ONLY to generate correct fill values."""

        if username or password:
            cred_section = CREDENTIAL_WITH.format(
                username=username or "not_provided",
                password=password or "not_provided"
            )
        else:
            cred_section = CREDENTIAL_WITHOUT

        system_prompt = STEP_BREAKDOWN_PROMPT.format(credential_section=cred_section)
        user_msg = f'Test description: "{nlp_input}"\nStarting URL: {start_url}'

        result = self.provider.call(system_prompt, user_msg)
        steps = self._parse_json(result)

        if not steps or not isinstance(steps, list):
            raise ValueError(f"AI returned invalid steps: {result[:300]}")

        return steps

    async def pick_element(self, snapshot_content: str, step: dict) -> dict:
        user_msg = f"STEP: {json.dumps(step)}\n\nPAGE SNAPSHOT:\n{snapshot_content}"
        result = self.provider.call(PICK_ELEMENT_PROMPT, user_msg)
        parsed = self._parse_json(result)

        if not parsed or not isinstance(parsed, dict):
            return {"ref": None, "confidence": "low", "reasoning": "Failed to parse AI response"}
        return parsed

    async def generate_assertion(self, snapshot_content: str, step: dict) -> dict:
        user_msg = f"ASSERTION STEP: {json.dumps(step)}\n\nPAGE SNAPSHOT:\n{snapshot_content}"
        result = self.provider.call(ASSERTION_PROMPT, user_msg)
        parsed = self._parse_json(result)

        if not parsed or not isinstance(parsed, dict):
            return {
                "rf_keyword": "Log",
                "full_line": f'    Log    MANUAL: Verify {step.get("description", "unknown")}',
            }
        return parsed
        
