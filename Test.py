"""
AI Agent Service — Adaptive, page-aware automation agent.
Decides ONE action at a time based on current page state.
"""
import os, json, re
from dotenv import load_dotenv
load_dotenv()

AGENT_PROMPT = """You are an expert QA automation agent controlling a real web browser. You see the current page snapshot and decide the SINGLE next action.

## Response (STRICT valid JSON, no markdown):
{{"status":"action","action":"click","ref":"e15","value":"","description":"Click Sign In","reasoning":"Submit button for login","locator_hint":"role=button[name=\\"Sign In\\"]"}}

status: "action" | "goal_achieved" | "stuck"
action: click | fill | press_key | wait | assert_text | assert_visible | assert_url

## RULES:
- ref MUST be a real element ref from the snapshot (e15, e42, s1e5). NEVER "null" or made up.
- If you cannot find the element → status:"stuck". Do NOT guess refs.
- fill requires non-empty "value"
- assert_text: "value" = expected text, "ref" = element to check
- assert_url: "value" = expected URL fragment, ref ignored
- wait: "value" = seconds, ref ignored
- locator_hint: RF Browser locator for the element (data-testid > id > role+name > text > placeholder > aria-label)

## LOGIN INTELLIGENCE:
Handle ANY login flow:
- **Simple**: email + password on same page → fill both → click submit
- **SSO/OAuth**: "Continue with SSO"/"Sign in with Microsoft" → click it → handle provider page
- **Multi-step**: email first → click Next/Continue → WAIT → password appears → fill → click Sign In
- **Failed login**: error message or same form reappears → status:"stuck" with error details
- After clicking any login/submit button, the page WILL change. The next snapshot shows the new page.

## NAVIGATION INTELLIGENCE:
- Examine sidebars, nav bars, menus, breadcrumbs for links
- Nested menus: click parent → wait → click child
- "+", "Create New", "Add" buttons open forms/modals
- After clicking something that opens a modal, new elements appear in next snapshot

## GOAL TRACKING:
- Check action history — don't repeat successful actions
- When ALL parts of the goal are done → status:"goal_achieved"
- If stuck after 2+ attempts on same thing → status:"stuck"

{credential_section}"""

CRED_WITH = """
## CREDENTIALS (use these EXACT values for login):
- Username/Email: {username}
- Password: {password}"""

CRED_WITHOUT = """
## CREDENTIALS: None provided."""

class AzureOpenAIProvider:
    def __init__(self):
        from openai import OpenAI
        self._c = OpenAI(api_key=os.getenv("AZURE_OPENAI_API_KEY",""), base_url=os.getenv("AZURE_OPENAI_BASE_URL",""))
        self._m = os.getenv("AZURE_OPENAI_MODEL","gpt-4o")
    def call(self,s,u):
        r=self._c.chat.completions.create(model=self._m,messages=[{"role":"system","content":s},{"role":"user","content":u}],temperature=0.1,max_tokens=1024)
        return r.choices[0].message.content

class GeminiProvider:
    def __init__(self):
        from google import genai
        self._c=genai.Client(api_key=os.getenv("GEMINI_API_KEY",""))
        self._m=os.getenv("GEMINI_MODEL","gemini-2.0-flash")
    def call(self,s,u):
        from google.genai import types
        r=self._c.models.generate_content(model=self._m,contents=u,config=types.GenerateContentConfig(system_instruction=s,temperature=0.1,max_output_tokens=1024))
        return r.text

class AIService:
    def __init__(self):
        p=os.getenv("AI_PROVIDER","azure_openai").lower()
        if p=="azure_openai": self.provider=AzureOpenAIProvider(); self.provider_display="Azure OpenAI"
        elif p=="gemini": self.provider=GeminiProvider(); self.provider_display="Gemini"
        else: raise ValueError(f"Unknown AI_PROVIDER: {p}")
        print(f"[AI] {self.provider_display}")

    def _parse(self,text):
        text=text.strip()
        for p in ["```json","```"]:
            if text.startswith(p): text=text[len(p):]
        if text.endswith("```"): text=text[:-3]
        text=text.strip()
        try: return json.loads(text)
        except:
            m=re.search(r'\{.*"status".*\}',text,re.DOTALL)
            if m:
                try: return json.loads(m.group())
                except: pass
        return None

    async def decide_next_action(self, goal, snapshot, history, username="", password=""):
        cred = CRED_WITH.format(username=username,password=password) if (username or password) else CRED_WITHOUT
        system = AGENT_PROMPT.format(credential_section=cred)

        hist_text = ""
        if history:
            lines=[]
            for i,h in enumerate(history[-15:]):
                icon = "✓" if h.get("status")=="success" else "✗ FAILED"
                line = f"{i+1}. {icon} [{h.get('action','')}] {h.get('description','')}"
                if h.get("error"): line += f" — Error: {h['error'][:80]}"
                lines.append(line)
            hist_text = "\n".join(lines)

        snap = snapshot[:6000] + "\n...[truncated]" if len(snapshot)>6000 else snapshot

        user_msg = f"GOAL: {goal}\n\nACTION HISTORY:\n{hist_text or '(first action)'}\n\nCURRENT PAGE:\n{snap}\n\nNext action? JSON only."

        result = self.provider.call(system, user_msg)
        parsed = self._parse(result)

        if not parsed:
            return {"status":"stuck","reasoning":f"Unparseable AI response: {result[:200]}","description":"AI error"}

        if parsed.get("status") not in ("action","goal_achieved","stuck"):
            parsed["status"] = "action"

        if parsed["status"]=="action":
            ref = parsed.get("ref")
            if not ref or str(ref).strip().lower() in ("null","none","","undefined"):
                return {"status":"stuck","reasoning":parsed.get("reasoning","Element not found"),"description":parsed.get("description","")}

        return parsed
