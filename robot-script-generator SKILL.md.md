# robot-script-generator SKILL.md

Save the block below as `skills/robot-script-generator/SKILL.md` in the QA automation repo. It uses the knowledge files from the three builders and the status from knowledge-reviewer.

````markdown
---
name: robot-script-generator
description: Generates production-quality Robot Framework test scripts from AIDLC test cases (or a plain-language user request) by reusing existing keywords and locators from the knowledge base, exploring only missing UI parts live through Playwright MCP, following the repository's own conventions for Browser (Playwright) or SeleniumLibrary, validating by dry run, live locator checks, execution and step traceability, marking all generated code, and handing over on a separate branch only after user approval. Can also produce a standalone Playwright script when explicitly asked. Use when asked to generate, create, write or automate a test script.
version: 1.0.0
---

# Robot Script Generator

## 1. Purpose and non-negotiable rules
Turn a test case into a script a senior automation engineer would approve without rework.

1. **Never modify, reformat, rename or delete existing tests, keywords or locators.** Only add new ones.
2. **Reuse before create.** Use an existing keyword or locator whenever one fits; create new ones only for real gaps.
3. **Follow the repo, not your preferences.** Library, file layout, naming, argument style, documentation, waits and assertions must match the conventions recorded in the knowledge files.
4. **No hard-coded secrets, environments or personal data.** Credentials and URLs come only from existing variables, variable files or environment variables.
5. **Test environments only.** Never run against production. If the target URL looks like production or is unknown, stop and ask.
6. **No `Sleep`** unless the repo has no other wait mechanism; use explicit waits.
7. **Mark everything generated** (section 7).
8. **No commit, push or pull request without explicit user approval.**
9. **Never claim success without evidence:** a passed run plus a complete traceability table.

## 2. Inputs
- **Test case:** an AIDLC test case `.md` (preferred), a qTest case, or a plain-language request (e.g. "check cross reference type ABCD is available"). For a plain request, first write the steps and expected results back to the user and get confirmation.
- **Knowledge:** `knowledge/app-knowledge.md` + `app/`, `knowledge/keyword-knowledge.md` + `keywords/`, `knowledge/locator-knowledge.md` + `locators/`, `knowledge/knowledge-status.md`.
- **Config (optional):** `knowledge/config.yaml`, e.g. `test_env_url_variable`, `run_command`, `default_output_dir`, `max_fix_attempts` (default 3).
- **Output type:** Robot Framework (default). Standalone Playwright (TypeScript or Python, matching any existing Playwright project in the workspace) only if the user explicitly asks.

## 3. Pre-flight checks (stop and report if any fails)
1. Git: capture branch and commit; create and switch to `ai-scriptgen/<test-case-id or short-name>-<YYYYMMDD>`. Never work on main, master, develop or release branches.
2. Knowledge present for all three types. If missing, tell the user which builder to run.
3. Knowledge freshness: if knowledge `last_commit` is older than changes to the relevant suites or resources, warn and offer an incremental refresh first.
4. Knowledge status for the target module: PASS = continue; WARN = warn and continue; FAIL or needs-human-review = require explicit user confirmation.
5. Playwright MCP availability (needed only if gaps exist). If unavailable, continue only for fully known flows; otherwise stop and explain.
6. Environment: resolve the test environment URL and credential variables from repo conventions; confirm they are non-production.

## 4. Procedure

### Step 1: Understand the test case
Extract: ID, title, priority, preconditions, test data, ordered steps, and expected results per step. Number every step and every expected result; these numbers drive traceability.

### Step 2: Resolve each step against knowledge
For each step, in order:
1. Find the matching **flow** and step in app knowledge (by business meaning, screen and entity).
2. Use the keyword knowledge **flow step mapping** to get the keyword; otherwise search keywords by screen ID and purpose. Prefer: `preferred` duplicates, then `flow` level over chains of `step` level, then higher usage.
3. For element-level actions, find the locator on that screen. Prefer High, then Medium stability; use Low only with no alternative, and flag it.
4. Mark the step **RESOLVED** (keyword found), **PARTIAL** (screen known, element or keyword missing) or **GAP** (screen or action unknown).

Show the user a resolution plan table before writing code:
`| Step | Action | Resolution | Keyword ID / Locator ID | Notes |`

### Step 3: Explore gaps with Playwright MCP (only for PARTIAL or GAP steps)
1. Open the browser on the test environment. Reach the gap by replaying the RESOLVED steps (login, navigation) the same way the existing keywords do.
2. Perform only the gap steps described in the test case. Do not click destructive actions (delete, submit payments, approve) unless the test case requires them; ask first if unsure.
3. For each new element, capture a locator using this priority: `data-testid` / `data-qa` > unique stable `id` > ARIA role + accessible name > label-anchored CSS or short relative XPath > visible text. Never absolute XPath, index-based or generated IDs or classes.
4. Verify each new locator matches exactly one visible element. For dropdowns, capture the dropdown and the option pattern (dynamic locator with placeholder).
5. Note required waits (element states, network idle, spinners), frames and shadow DOM.
6. Close the browser. Never save cookies, tokens or screenshots containing personal data into the repo.

### Step 4: Design the code
- **Test placement:** follow the recorded test organisation. One-test-per-file: create a new `.robot` file in the module's folder, named in the repo's style. Many-tests-per-suite: append the new test case at the end of the matching suite's `*** Test Cases ***` section. Never insert between or inside existing tests.
- **New locators:** add to the file and section named under "Where new locators for this screen go", following naming conventions. Reuse an existing variable if the selector already exists.
- **New keywords:** add to the module's resource file recorded in keyword conventions, at the end of `*** Keywords ***`. Create a keyword only when the action is reusable or the repo's style requires it; otherwise compose existing keywords in the test.
- **Library syntax:** use only keywords of the detected library (Browser: `Click`, `Fill Text`, `Select Options By`, `Wait For Elements State`, `Get Text`; SeleniumLibrary: `Click Element`, `Input Text`, `Select From List By Label`, `Wait Until Element Is Visible`, `Element Text Should Be`), matching what the repo already uses.
- **Test data:** use variables or existing data files; add new data to the existing data or variable file for that module, never as literals scattered in steps.

### Step 5: Write the code (coding standards)
- Sections in standard order: `*** Settings ***`, `*** Variables ***`, `*** Test Cases ***`, `*** Keywords ***`.
- Spacing and indentation exactly as the surrounding file (typically 4 spaces between tokens). No tabs unless the repo uses them.
- Every test has `[Documentation]` (test case ID, title, one-line purpose) and `[Tags]` (repo's standard tags + test case ID + `ai-generated`).
- Every new keyword has `[Documentation]`, `[Arguments]` if any, and `RETURN` (or `[Return]` if the repo's Robot version requires it).
- One business action per keyword; descriptive Title Case names in the repo's verb style; no duplicates of existing keywords.
- Explicit assertions for every expected result, with clear failure messages.
- Use existing setup and teardown; add `[Teardown]` cleanup if the test creates data and the repo does this elsewhere.
- No commented-out code, no debug logging, no `Sleep`, no hard-coded URLs or credentials.
- If the repo uses robotidy or robocop configs, follow them and run them on new code only.

### Step 6: Validate (all four must pass)
1. **Dry run:** `robot --dryrun` on the new or changed suite. Fix syntax and missing-keyword errors.
2. **Live locator check:** with Playwright MCP, confirm every new locator and every Low-stability reused locator resolves to exactly one element on the right screen.
3. **Execution:** run only the new test (e.g. `robot --test "<name>" --outputdir <default_output_dir>/ai-scriptgen <suite>`) against the test environment. On failure, classify (locator, timing, data, environment, logic), fix, rerun, up to `max_fix_attempts`. Never fix a failure by weakening or removing an assertion. If an expected result genuinely fails, report it as a possible application defect, not a script problem.
4. **Traceability:** every test case step and expected result maps to script line(s). Any unmapped item = not done.

### Step 7: Update knowledge
Append new locators and keywords to the locator and keyword knowledge files using their templates and ID rules, link them to screen and flow IDs, mark them `Source: ai-generated`, and add the new test as a source test of its flow. Do not touch unrelated entries.

### Step 8: Hand over and wait for approval
Show the user:
- Files changed and a diff summary.
- Reused vs new keywords and locators (with IDs).
- Traceability table: `| TC step / expected result | Script line(s) | Status |`
- Validation results (dry run, locator check, run result, log and report paths, fix attempts).
- Warnings: Low-stability locators, possible defects, knowledge status WARN or FAIL.
Then ask: approve commit / request changes / discard. Only on approval: commit with message `test(<module>): add <test case ID> <title> [ai-generated]`, push the branch, and open a pull request if the user asks. Never merge.

## 6. Optional: Playwright script output
Only when explicitly requested. Use the same resolution and exploration results; write a test in the existing Playwright project's language and structure (or ask where to create one); prefer `getByRole`, `getByTestId`, `getByLabel`; web-first assertions; credentials from environment variables; same marking, validation and approval rules.

## 7. Marking generated code
Above every new test case, keyword and locator block, add:
```
# Generated by AI Robot Script Generator | <YYYY-MM-DD> | Source: <test case ID or request summary>
```
Every generated test also gets the tag `ai-generated`. In Playwright output use the equivalent `//` comment and an `@ai-generated` annotation or tag.

## 8. Error handling
- Ambiguous step: ask the user; do not guess.
- Multiple candidate keywords: choose by the preference rules and list the alternatives in the handover.
- Element not found during exploration: report the step and what is visible on screen; ask whether the feature is deployed to this environment.
- Login or environment failure: stop; do not retry repeatedly or lock accounts.
- Max fix attempts reached: hand over with status FAILED, the last error, and the diagnosis.

## 9. Example requests
- "@robot-script-generator generate a Robot script for test case TC-1234 from the AIDLC test cases."
- "@robot-script-generator create a script to check cross reference type ABCD is available in the portal."
- "@robot-script-generator generate the script for TC-1234 as a Playwright test."
````
