# save_session.py
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://your-portal-url.com"  # CHANGE THIS
SESSION_FILE = "auth_state.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"\n>>> Opening {PORTAL_URL}")
        print(">>> Steps to complete in the browser:")
        print("    1. Click 'Continue to SSO Login'")
        print("    2. Complete Microsoft login (email, password, MFA)")
        print("    3. Wait until you land on the portal dashboard")
        print(">>> Then come back here and press ENTER\n")

        page.goto(PORTAL_URL)

        input("Press ENTER after you've fully logged in and see the portal dashboard...")

        context.storage_state(path=SESSION_FILE)
        print(f"\n✓ Session saved to {SESSION_FILE}")

        browser.close()

if __name__ == "__main__":
    main()




# crawl_page.py
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSION_FILE = "auth_state.json"
OUTPUT_DIR = Path("snapshot_store")
OUTPUT_DIR.mkdir(exist_ok=True)

# CHANGE these two for each page you want to capture
PAGE_URL = "https://your-portal-url.com/some-page"
PAGE_NAME = "SomePage"

EXTRACT_SCRIPT = """
() => {
  const fields = document.querySelectorAll('input, select, textarea');
  const buttons = document.querySelectorAll('button, input[type=submit], input[type=button]');

  const fieldData = Array.from(fields)
    .filter(el => el.type !== 'hidden')
    .map(el => ({
      name: el.name || el.id || '',
      label: el.labels && el.labels[0] ? el.labels[0].innerText : '',
      type: el.type || el.tagName.toLowerCase(),
      required: el.required || false,
      max_length: el.maxLength > 0 ? el.maxLength : null,
      placeholder: el.placeholder || '',
      pattern: el.pattern || null,
      options: el.tagName === 'SELECT'
        ? Array.from(el.options).map(o => o.value)
        : null
    }));

  const buttonData = Array.from(buttons).map(el => ({
    label: el.innerText || el.value || '',
    type: el.type || 'button'
  }));

  return {
    url: window.location.href,
    title: document.title,
    fields: fieldData,
    buttons: buttonData
  };
}
"""

def main():
    if not Path(SESSION_FILE).exists():
        print(f"✗ {SESSION_FILE} not found. Run save_session.py first.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()

        print(f">>> Navigating to {PAGE_URL}")
        page.goto(PAGE_URL, wait_until="networkidle")

        print(">>> Extracting fields...")
        data = page.evaluate(EXTRACT_SCRIPT)

        snapshot = {
            "page_name": PAGE_NAME,
            "url": data["url"],
            "title": data["title"],
            "fields": data["fields"],
            "buttons": data["buttons"],
            "business_rules": [],      # you fill these manually
            "roles_allowed": []        # you fill these manually
        }

        output_file = OUTPUT_DIR / f"{PAGE_NAME}.json"
        output_file.write_text(json.dumps(snapshot, indent=2))

        print(f"\n✓ Captured {len(data['fields'])} fields, {len(data['buttons'])} buttons")
        print(f"✓ Saved to {output_file}")

        browser.close()

if __name__ == "__main__":
    main()


Build a production-grade Autonomous Web Testing Agent designed for complex enterprise web applications (SPA apps built with React, Next.js, Angular, Vue, Material UI, Tailwind CSS).

The system must aim to achieve near-98% success rate through a combination of:
- deterministic rule-based execution
- self-learning domain knowledge generation
- dependency-aware progressive form handling
- workflow learning and reuse

The system must NOT rely on random exploration.

=====================================================
CORE ARCHITECTURE (MANDATORY)
=====================================================

Perception → Auto Config Generator → Rule Engine → Dependency Engine → Progressive Form Engine → Workflow Engine → State Manager → Decision Engine → Execution → Evaluation → Learning Engine → Memory → Test Generation

=====================================================
1. PERCEPTION LAYER
=====================================================

- Use Playwright CLI snapshot to extract accessibility-based UI tree
- Parse into structured elements:
  {ref, role, label, type, required, disabled, visible, hierarchy}
- Detect sections, forms, modals, tabs, and workflows

=====================================================
2. AUTO DOMAIN CONFIG GENERATOR (CRITICAL)
=====================================================

- Automatically infer field types from labels:
  - email → email
  - phone → numeric
  - date → date
  - name → text
- Generate initial config dynamically (no manual input required)

- Store inferred config:
{
  fields: {
    "Email": { type: "email" },
    "Phone": { type: "number" }
  }
}

=====================================================
3. LEARNING ENGINE (KEY FOR 98%)
=====================================================

- Learn from validation errors dynamically

Example:
Input → "123"
Error → "Must be 10 digits"

Store:
"Phone": { pattern: "10-digit" }

- Continuously refine:
  - field formats
  - valid values
  - workflow paths

- Persist learned knowledge for reuse

=====================================================
4. RULE ENGINE (DETERMINISTIC CORE)
=====================================================

- Always:
  1. Fill required fields
  2. Enable dependent fields
  3. Complete forms before submission

- Never submit incomplete or invalid forms

=====================================================
5. DEPENDENCY ENGINE
=====================================================

- Detect:
  Field A → enables Field B → opens nested Form C

- Implementation:
  - compare snapshot before/after action
  - track:
    - new elements
    - enabled fields
    - new sections/modals

=====================================================
6. PROGRESSIVE FORM ENGINE
=====================================================

- Fill forms iteratively:
  Fill → Observe → Unlock → Fill more

- Support:
  - nested forms (multi-level)
  - modal forms
  - conditional sections

=====================================================
7. WORKFLOW ENGINE
=====================================================

- Learn workflows automatically:
  - sequence of actions leading to success

- Store reusable patterns:
  state → action → next state

- Reuse successful workflows for similar pages

=====================================================
8. STATE MANAGEMENT
=====================================================

- State = hash(URL + visible UI structure)

- Track:
  - visited states
  - actions taken
  - progress level

- Prevent loops and redundant actions

=====================================================
9. DECISION ENGINE
=====================================================

STRICT PRIORITY:

1. Complete current form/workflow
2. Fill required fields using learned config
3. Enable next step via dependencies
4. Execute primary actions (Submit, Next)
5. Use AI ONLY when ambiguous

AI must never override deterministic rules

=====================================================
10. EXECUTION LAYER
=====================================================

- Use Playwright CLI:
  - click(ref)
  - fill(ref, value)
  - select(ref, option)

- Handle:
  - dropdowns
  - tabs
  - modals
  - sliders
  - toggles
  - scrolling

- Use event-based waits (React/MUI safe)

=====================================================
11. EVALUATION ENGINE
=====================================================

After each action:

Detect:
- progress (new elements / navigation)
- failure (validation errors)
- no change

Respond:
- failure → retry with improved input
- no change → try alternative action
- progress → continue

=====================================================
12. MEMORY LAYER
=====================================================

- Store:
  - learned field rules
  - workflows
  - dependency patterns

- Reuse across pages

=====================================================
13. TEST GENERATION
=====================================================

- Generate:
  - human-readable test cases
  - Playwright scripts
  - coverage reports

=====================================================
14. SPA HANDLING
=====================================================

- Support:
  React, Next.js, Angular, Vue, Material UI, Tailwind CSS

- Handle:
  - dynamic rendering
  - re-renders
  - lazy loading
  - conditional UI

=====================================================
15. GOAL
=====================================================

- Achieve near 98% success rate on enterprise applications by:
  - eliminating random behavior
  - learning from errors
  - reusing successful workflows
  - adapting to dynamic UI changes

=====================================================
16. CONSTRAINTS
=====================================================

- No random input generation
- No blind exploration
- Must learn from failures
- Must improve over time





    You are a Principal Software Architect and QA Automation Expert with 30+ years of experience in:

- Large-scale enterprise systems
- Browser automation (Playwright, Selenium)
- AI-based agents and decision systems
- Workflow orchestration engines
- Distributed systems and reliability engineering

Your task is to perform a STRICT, CRITICAL, and REALISTIC review of the Autonomous Web Testing Agent that has been built.

=====================================================
REVIEW OBJECTIVE
=====================================================

Do NOT give generic or positive feedback.

Your goal is to:
- Identify weaknesses
- Find failure points
- Detect architectural gaps
- Evaluate real-world reliability

Assume this system will be used on complex enterprise applications with:
- nested multi-step forms
- dynamic UI (React, MUI, Tailwind)
- dependency-based field enablement
- strict validation rules

=====================================================
REVIEW AREAS (MANDATORY)
=====================================================

1. ARCHITECTURE VALIDATION
- Is the architecture complete and correct?
- Are any critical layers missing?
- Are components loosely coupled and scalable?

2. FORM HANDLING (CRITICAL)
- Can it handle deeply nested forms (2–3 levels)?
- Can it handle dynamic enabling/disabling fields?
- Will it fail on validation-heavy forms?

3. DEPENDENCY HANDLING
- Does it correctly detect:
  Field A → enables Field B → opens nested Form C?
- Are there edge cases where this breaks?

4. STATE MANAGEMENT
- Will it avoid infinite loops?
- Does it correctly identify unique states?
- Any risk of state explosion?

5. DECISION ENGINE
- Are rules sufficient for deterministic execution?
- Is AI used appropriately or overused?
- Where will decision-making fail?

6. SPA & DYNAMIC UI HANDLING
- Will it work reliably on:
  - React
  - Angular
  - MUI components
- Are wait strategies sufficient?

7. DATA & VALIDATION HANDLING
- Will input generation pass real-world validations?
- What types of inputs will fail?
- Is learning from validation robust?

8. ERROR HANDLING & RECOVERY
- Does the system recover from failures?
- Does it retry intelligently?

9. PERFORMANCE & SCALABILITY
- Will it scale for large applications?
- Any bottlenecks?

10. TEST GENERATION QUALITY
- Are generated tests stable and reusable?
- Will they break on UI changes?

=====================================================
FAILURE ANALYSIS (VERY IMPORTANT)
=====================================================

List at least 10 REALISTIC failure scenarios such as:

- validation failure loops
- incorrect dependency detection
- modal handling issues
- dropdown selection failures
- async timing issues

For each:
- explain WHY it fails
- suggest FIX

=====================================================
GAP ANALYSIS
=====================================================

- What is missing to achieve 95–98% success rate?
- What MUST be added for production readiness?

=====================================================
VERDICT
=====================================================

Give a final assessment:

- Current success rate (realistic)
- Maximum achievable success rate with current design
- What is required to reach 98%

=====================================================
IMPORTANT CONSTRAINTS
=====================================================

- Do NOT be optimistic
- Do NOT assume perfect conditions
- Think like a production engineer responsible for reliability
- Be brutally honest


You are a Principal Software Architect and QA Automation Expert with 30+ years of experience in:

- Large-scale enterprise systems
- Browser automation (Playwright, Selenium)
- AI-based agents and decision systems
- Workflow orchestration engines
- Distributed systems and reliability engineering

Your task is to perform a STRICT, CRITICAL, and REALISTIC review of the Autonomous Web Testing Agent that has been built.

=====================================================
REVIEW OBJECTIVE
=====================================================

Do NOT give generic or positive feedback.

Your goal is to:
- Identify weaknesses
- Find failure points
- Detect architectural gaps
- Evaluate real-world reliability

Assume this system will be used on complex enterprise applications with:
- nested multi-step forms
- dynamic UI (React, MUI, Tailwind)
- dependency-based field enablement
- strict validation rules

=====================================================
REVIEW AREAS (MANDATORY)
=====================================================

1. ARCHITECTURE VALIDATION
- Is the architecture complete and correct?
- Are any critical layers missing?
- Are components loosely coupled and scalable?

2. FORM HANDLING (CRITICAL)
- Can it handle deeply nested forms (2–3 levels)?
- Can it handle dynamic enabling/disabling fields?
- Will it fail on validation-heavy forms?

3. DEPENDENCY HANDLING
- Does it correctly detect:
  Field A → enables Field B → opens nested Form C?
- Are there edge cases where this breaks?

4. STATE MANAGEMENT
- Will it avoid infinite loops?
- Does it correctly identify unique states?
- Any risk of state explosion?

5. DECISION ENGINE
- Are rules sufficient for deterministic execution?
- Is AI used appropriately or overused?
- Where will decision-making fail?

6. SPA & DYNAMIC UI HANDLING
- Will it work reliably on:
  - React
  - Angular
  - MUI components
- Are wait strategies sufficient?

7. DATA & VALIDATION HANDLING
- Will input generation pass real-world validations?
- What types of inputs will fail?
- Is learning from validation robust?

8. ERROR HANDLING & RECOVERY
- Does the system recover from failures?
- Does it retry intelligently?

9. PERFORMANCE & SCALABILITY
- Will it scale for large applications?
- Any bottlenecks?

10. TEST GENERATION QUALITY
- Are generated tests stable and reusable?
- Will they break on UI changes?

=====================================================
FAILURE ANALYSIS (VERY IMPORTANT)
=====================================================

List at least 10 REALISTIC failure scenarios such as:

- validation failure loops
- incorrect dependency detection
- modal handling issues
- dropdown selection failures
- async timing issues

For each:
- explain WHY it fails
- suggest FIX

=====================================================
GAP ANALYSIS
=====================================================

- What is missing to achieve 95–98% success rate?
- What MUST be added for production readiness?

=====================================================
VERDICT
=====================================================

Give a final assessment:

- Current success rate (realistic)
- Maximum achievable success rate with current design
- What is required to reach 98%

=====================================================
IMPORTANT CONSTRAINTS
=====================================================

- Do NOT be optimistic
- Do NOT assume perfect conditions
- Think like a production engineer responsible for reliability
- Be brutally honest
