# robot-script-generator SKILL.md

Save the block below as `skills/robot-script-generator.md (or skills/robot-script-generator/SKILL.md)` in the QA automation repo. It uses the knowledge files from the three builders and the status from knowledge-reviewer.

````markdown
---
name: robot-script-generator
description: Generates production-quality Robot Framework test scripts from AIDLC test cases, a test case ID, or a plain-language request. Reuses existing keywords and locators from the knowledge base, understands plain-language requests through the glossary, plans the real route with every precondition from the application map, explores only missing UI parts live (Robot Framework MCP or Playwright MCP) while verifying the screen after every action, follows the repository's own conventions for Browser (Playwright) or SeleniumLibrary, generates a draft, runs it in a visible browser and fixes it automatically until it passes end to end, then asks before adding it to the repo, branching or committing. Never writes sensitive data into code comments, documentation or tags. Can also produce a Playwright script when explicitly asked. Use when asked to generate, create, write or automate a test script.
version: 1.3.0
---

# Robot Script Generator

## 1. Non-negotiable rules
1. **Ask before changing the repo.** Never add to existing suite files, switch branch, commit or push without the user's explicit answer to that stage's question (section 4). Planning, generating the draft, running it and fixing it are automatic and need no approval.
2. **Never modify, reformat, rename or delete existing tests, keywords or locators.** Only add new ones, and only after approval.
3. **Reuse before create.** Use existing keywords and locators wherever they fit.
4. **Follow the repo's conventions**: library, layout, naming, argument style, documentation, waits, assertions.
5. **No sensitive data in code text** (section 7). Real values live only in variables or data files.
6. **No hard-coded credentials or URLs.** Use existing variables, variable files or environment variables.
7. **Test environments only.** If the target looks like production or is unknown, stop and ask.
8. **Always run headed** so the user can watch (section 5).
9. **PASS means a full end-to-end pass** (section 6). Never report success from a dry run, partial run or unit-level check.
10. **No `Sleep`** unless the repo has no other wait mechanism.
11. **Never weaken or remove an assertion to make a test pass.**

## 2. Short requests (testers should not need long prompts)
Accept any of these and infer the rest from this skill:
- `@robot-script-generator TC-1234`
- `@robot-script-generator check cross reference type ABCD is available`
- `@robot-script-generator TC-1234 playwright`
- `@robot-script-generator path/to/test-cases.md` or `@robot-script-generator path/to/test-cases.md TC-1234`
**Finding the test case:** for a test case ID, search the repo's test case `.md` files (AIDLC output) for that ID and use its title, preconditions, steps, test data and expected results exactly. For an `.md` file, read it; if it holds several test cases and none is named, list their IDs and titles and ask which one. If an ID is not found or appears more than once, say so and ask. The test case is the source of truth: for new features its screen, section and element names are the starting hint for exploration (section 16), and its expected results become the assertions. Never add steps or checks it does not ask for.
If the request has no test case ID and no description of what to check (e.g. only "execute", "run" or "generate"), do nothing else: never run existing suites or the whole repo. Ask: "Which test case ID or check do you want me to automate?" and wait.
If the input is a plain request, restate it as numbered steps and expected results and ask the user to confirm before continuing.

## 2a. Understanding the request (plain words to IDs)
1. Split the request into intents: target screens, elements, actions, data and expected outcomes. Example: "log in, select a client, go to cross reference, tick Settle Account Only" -> logged in; client selected; SCREEN-...-CROSS-REFERENCE-TAB; element "Settle Account Only" checkbox; action check; outcome checkbox checked.
2. Resolve every word through `knowledge/glossary.md`, then screen and flow names, then keyword and locator meanings. Exact term first, then synonyms, then partial match.
3. One match: use it. Several matches (term marked ambiguous): ask the user one short question listing the options. No match: say so plainly, then treat it as unknown and explore it live (Stage 2) starting from the nearest known screen the user mentioned.
4. Unstated prerequisites are never the user's job: the route planner adds them ("go to cross reference" automatically includes logging in and opening a client if the map says so).

## 2b. Route planning (never invent a path)
1. Start state is logged out unless the repo's suite setup says otherwise.
2. For each target screen, read its entry in `knowledge/app-map.md`: preconditions, entry route, proof element.
3. Build the route by satisfying every precondition in order, using the entry routes exactly as copied from their source tests. Reuse the same keywords with the same arguments pattern (data as variables).
4. Never skip a precondition and never take a shortcut that no existing test takes, even if a tab or link looks directly clickable.
5. If two screens in the request need conflicting context, plan them in order and say so in the plan.
6. Show the route in the plan with the source test for each part.
7. **Test data:** list the data the route and actions need (e.g. a client with cross references, a client in a given status). Take it from the data or variable files used by the route's source tests; reuse their variables. Never invent real data or hard-code it. If no suitable data exists, ask the user once for the variable to use. If the test creates or changes data, plan cleanup the way existing tests do.

## 3. Pre-flight (read-only; report problems and stop if blocking)
1. Record current branch and commit. **Do not create or switch branches here.**
2. Knowledge files exist for app, keywords and locators. If not, tell the user: "Run `@qa-knowledge-setup build` first."
3. Freshness: if relevant suites or resources changed after the knowledge `last_commit`, warn and offer `@qa-knowledge-setup refresh`.
4. `knowledge/knowledge-status.md`: PASS continue; WARN warn and continue; FAIL or needs-human-review ask for explicit confirmation.
5. Resolve test environment URL and credential variables from repo conventions; confirm non-production.
6. Exploration tools available if any gap exists (section 14).
7. `knowledge/app-map.md` and `knowledge/glossary.md` exist. If missing (knowledge built by an older version), tell the user to run `@qa-knowledge-setup rebuild <scope>`; never plan routes without the map.

## 4. Staged workflow (questions only before repo changes)

### Stage 1 - Plan
Extract test case ID, title, preconditions, test data (as variable names), numbered steps and numbered expected results. Resolve each step against knowledge (flow, flow step mapping, keyword, locator; prefer preferred duplicates, flow-level keywords, High then Medium stability locators). Mark each step RESOLVED, PARTIAL or GAP. Resolve the request (section 2a) and plan the full route (section 2b) first; the plan lists preconditions, the route with its source tests, the proof element for every screen, the expected blocking messages, and the assertion for every expected result.
Show: `| Step | Action | Resolution | Keyword / Locator | Notes |`
Continue to the next stage without asking. Stop and ask only if a step is ambiguous, the test case is unclear, or the module's knowledge status is FAIL or needs-human-review.

### Stage 2 - Explore gaps (only if PARTIAL or GAP steps exist)
Use the exploration tools in section 14. Replay the planned route with the repo's real keywords, applying the step verification protocol (section 12) after every action, then perform only the gap steps, again verifying each one. Never click destructive actions unless the test case requires them; ask if unsure. Capture locators in this priority: `data-testid`/`data-qa` > stable unique `id` > role + accessible name > label-anchored CSS or short relative XPath > visible text. Never absolute XPath, index-based or generated IDs. Verify each matches exactly one visible element. Close the browser; save no cookies, tokens or screenshots with personal data.

### Stage 3 - Generate into a draft file (no existing file is touched)
Write the complete test, any new keywords and new locators into a **draft** file: `ai_generated_tests/<module>/<test_case_id_or_short_name>.robot` at the repo root (create the folders if missing; this staging folder is the standard location for AI-generated tests awaiting approval; it must import the same resources and libraries as the target suite, with resource and variable file paths adjusted relative to the draft's location, so it runs standalone). Follow the coding standards in section 8. Run `robot --dryrun` on the draft and fix errors.
Show the user the full script.
Tell the user the draft path and that you are now running it in a visible browser. Do not ask; go straight to Stage 4. Never present the script as working before Stage 4 proves it.

### Stage 4 - Run headed and report
Runs automatically after Stage 3. Run only the draft test, headed (section 5), with output to `<default_output_dir>/ai-scriptgen/`. Determine the result strictly by section 6.
- **PASS:** report per-step results, duration, log and report paths.
- **FAIL:** report the failing step, the exact error, a diagnosis (locator, timing, data, environment, logic, or possible application defect). Do not ask the user. Automatically fix and rerun, up to `max_fix_attempts` (default 3) rounds. For each round: read the failing step and error from `output.xml` and the log; compare the failing step with how existing keywords and locators in the knowledge files handle the same screen; re-inspect the live page with the exploration tools (section 14) and apply the step verification protocol (section 12) to find the first step whose expected state did not appear; if a blocking message caused it, fix the route or precondition (never just retry); apply the smallest correct fix (locator, wait, data, step order); rerun the full test end to end. Show one progress line per round ("Attempt 2 of 3: fixed dropdown wait, rerunning"). If it still fails after the last round, stop and explain to the user in plain language: which step fails, what the screen shows, what was tried in each round, the most likely cause, and what they can do next. If an expected result genuinely fails, report it as a possible defect; do not change the assertion.
Always show the exact command so the user can rerun it themselves, for example:
`robot --test "<test name>" --variable HEADLESS:false --outputdir results/ai-scriptgen ai_generated_tests/<module>/<file>.robot`
Show the traceability table: `| TC step / expected result | Script line(s) | Run status |`
**Ask (only after PASS):** "The test passed end to end. Please review the log and rerun it yourself with the command above. When you have finalised it, do you want me to add this test to the existing suite `<target suite file>`, or keep it only in `ai_generated_tests/` for now?" If the user wants to rerun first, wait; do not ask again until they say they are done

### Stage 5 - Add to the repository
Only on yes. Following the recorded test organisation:
- one-test-per-file: move the draft to the module's test folder with a name in the repo's style;
- many-tests-per-suite: append the test at the end of the target suite's `*** Test Cases ***` section.
Add new locators and keywords to the files recorded in knowledge conventions, at the end of their sections. Do not insert between or inside existing tests or keywords. Run `robot --dryrun` on the changed suite, then delete the draft. Update the keyword and locator knowledge files with the new entries (`Source: ai-generated`) and add the test as a source of its flow. Show a diff summary.
**Ask:** "The test is added. Do you want me to create a branch and commit these changes?"

### Stage 6 - Branch and commit
Only on yes. Propose branch name `ai-scriptgen/<test-case-id>-<YYYYMMDD>` and commit message `test(<module>): add <test case ID> <title> [ai-generated]`; let the user change them. Create the branch, commit only the files changed in Stage 5. **Ask** before pushing, and again before opening a pull request. Never merge.

If the user says no or stop at any stage, stop there, leave the draft in place, and summarise what exists.

## 5. Headed execution
- Browser library: pass headless false using the repo's existing variable (e.g. `--variable HEADLESS:false`) or the `New Browser    headless=${False}` argument already used by the repo's setup keyword.
- SeleniumLibrary: use the repo's browser variable with a non-headless value (e.g. `--variable BROWSER:chrome`, not `headlesschrome`).
- If the repo hard-codes headless mode in a setup keyword, do not edit it; tell the user, and use the draft's own setup override only if they approve.

## 6. Result integrity
- The result comes only from Robot Framework's output: the test's final status in `output.xml` and the process exit code.
- **PASS** only if the generated test ran from setup to teardown, every step executed, and every expected result was asserted and passed.
- Any failure in setup, login, navigation, a step, an assertion or teardown means **FAIL**. A skipped or not-run test is **NOT RUN**, never PASS.
- Dry-run success is reported as "syntax OK", never as "passed".
- Report the counts exactly as Robot gives them (passed, failed, skipped).

## 7. Sensitive data rules
Never write real values into comments, `[Documentation]`, `[Tags]`, test or keyword names, commit messages or knowledge files. This includes: client or customer IDs and names, account and reference numbers, user names, emails, phone numbers, addresses, passwords, tokens, environment URLs and hostnames, and any data value the user typed into the request.
- Describe by role instead: "Search client" not "Search client 102938".
- Put real values in the module's existing data or variable file under a descriptive variable name (e.g. `${XREF_TEST_CLIENT_ID}`), or reference an existing variable.
- Before showing any draft and before Stage 5, scan the new code for these patterns (digits-only IDs of 4+ characters, emails, URLs, values from the user's request) and replace them with variables.

## 8. Coding standards
- Section order: `*** Settings ***`, `*** Variables ***`, `*** Test Cases ***`, `*** Keywords ***`. Spacing and indentation identical to the surrounding files.
- Every test: `[Documentation]` with test case ID, title and one-line purpose; `[Tags]` with the repo's standard tags, the test case ID and `ai-generated`.
- Every new keyword: `[Documentation]`, `[Arguments]` if any, `RETURN` (or `[Return]` for older Robot versions used by the repo).
- One business action per keyword, Title Case in the repo's verb style, no duplicates of existing keywords.
- Explicit assertion for every expected result with a clear message. Explicit waits only. Choose the assertion that proves the outcome: option present in a list, checkbox or radio state, field value, exact or contained text, element visible or hidden, row present in a grid (by unique value), toast or success message, count. Prefer the assertion keywords the repo already uses.
- After every navigation step, wait for the screen's proof element before the next action (use the repo's wait keyword). Where the map lists a blocking message for that step, assert it is not present, so a missing precondition fails with a clear message instead of a confusing later error.
- Use existing setup and teardown; add cleanup if the test creates data and the repo does so elsewhere.
- No commented-out code, debug logs, `Sleep`, literals for credentials, URLs or test data.
- Run robotidy or robocop on new code only if the repo configures them.

## 9. Marking generated code
Above every new test case, keyword and locator block:
```
# Generated by AI Robot Script Generator | <YYYY-MM-DD> | Source: <test case ID or generic description>
```
The Source is a test case ID (e.g. TC-1234) or a short generic description such as "Verify cross reference type in dropdown" - never data values (section 7). Every generated test carries the tag `ai-generated`.

## 10. Playwright output (only when asked)
Same stages, rules and marking. Write in the existing Playwright project's language and structure (ask where if none); prefer `getByRole`, `getByTestId`, `getByLabel`; web-first assertions; credentials from environment variables; run headed (`--headed`).

## 11. Error handling
- Ambiguous step: ask; never guess.
- Several candidate keywords: choose by preference rules, list alternatives in the plan.
- Element not found: first run the full new-feature discovery in section 16. Only if that finds nothing, report what is visible and ask whether the feature is deployed to this environment.
- Login or environment failure: report FAIL, stop, never retry repeatedly or risk locking accounts.
- Fix attempts exhausted: report FAIL with last error and diagnosis; leave the draft for manual work.

## 12. Step verification protocol (after every action, in exploration and in fixing)
Never assume an action worked. After each click, fill, select or navigation:
1. **Settle:** wait for loading to finish using the repo's own pattern (spinners or skeletons gone, network idle, element states). No fixed Sleep.
2. **Scan for interruptions:** modals, dialogs, native alerts, confirm boxes, toasts or snackbars, banners, inline validation errors, session-expired or login pages, new tabs or windows. Read their text.
3. **Confirm the expected state:** the target screen's proof element is visible, or the expected element state changed (checked, selected, value set, row added).
4. **Decide:**
   - Expected state present and no interruption: continue.
   - Interruption matches a known blocking message in the map: apply its fix (satisfy the precondition), re-plan, continue. Report it in the plan.
   - Interruption is a normal confirm (e.g. "Are you sure?") required by the test case: handle it the way existing keywords do.
   - Unknown interruption or expected state missing: take an accessibility or DOM snapshot, stop that path, and explain in plain words what is on screen. At most one retry, and only for clear timing issues.
5. Never report a screen as reached, or an element as "not found", until steps 1 to 3 are done.

## 13. Enterprise UI patterns (check `knowledge/ui-patterns.md` first; reuse the repo's handling keywords)
- **Frames and shadow DOM:** locate the frame or host first (Browser `>>>`, Selenium `Select Frame`); unselect afterwards.
- **Custom dropdowns (MUI, React-Select, Salesforce Lightning, combobox or listbox):** not native selects. Click to open, wait for the listbox (often rendered at the end of the page body), choose the option by role and accessible name, then verify the displayed value.
- **Checkboxes and radios with custom styling:** act on the input or its label as existing keywords do; verify the checked state, not just the click.
- **Date pickers:** prefer typing into the input if the repo does; otherwise navigate the calendar; verify the value.
- **Virtualised or paginated grids:** never rely on row index; filter or search first, scroll if needed, locate the row by a unique cell value, scope actions to that row.
- **Toasts and snackbars:** assert them immediately; they disappear.
- **New tab or window:** switch to it, verify, and switch back as the repo does.
- **Session timeout or forced re-login, unsaved-changes prompts, role-based hidden actions:** detect via the protocol and report; never work around permissions.
- **Dynamic IDs and duplicate elements:** scope locators to a stable container; prefer role, label, test IDs.

## 14. Exploration tools
- **Primary: a Robot Framework MCP server (e.g. rf-mcp)**, if installed and approved by the organisation: it runs the repo's real keywords step by step in a live session, so a route that works during exploration works in the script, for both Browser and SeleniumLibrary repos.
- **Helper: Playwright MCP** for accessibility and DOM snapshots and finding stable locators for new elements.
- If only Playwright MCP is available: replay the route by doing exactly what the route's keywords do (read their steps from `knowledge/.extract/keywords.json`), and validate every new locator again in the Robot run (Stage 4), since Playwright MCP is a separate browser.
- If no exploration tool is available and gaps exist: stop and explain which steps are unknown.
- Use test environments only; never store cookies, tokens or screenshots with personal data.

## 15. Learning (the knowledge improves with every script)
After a PASS, and only for facts proven in this run, append to the knowledge with `Status: learned (needs review)` and the evidence (test run and step):
- new screens, transitions, preconditions and proof elements to `app-map.md`;
- new blocking messages with cause and fix;
- new glossary terms the user used that resolved correctly;
- new keywords and locators (as already described in Stage 5).
Do this together with Stage 5 (after the user approves adding the test), never before. The next `@qa-knowledge-setup refresh` and the reviewer confirm or reject learned entries.

## 16. New features not yet in the knowledge (new dropdown, radio, checkbox, field, button, column)
A requested element missing from the knowledge is normal for new features. Never stop or report "not found" because the knowledge lacks it.
1. **Reach the section:** plan and replay the route to the nearest known screen the user named (sections 2b and 12). Confirm its proof element.
2. **Discover:** search in tiers, cheapest first, and stop as soon as one tier finds it. **Tier 0 (hint):** if the test case, requirement or user names a screen, section, panel or tab, start there. **Tier 1 (search the page code, no clicking):** search the whole DOM, including hidden elements, frames and shadow roots, for the user's words in text, labels, aria attributes, placeholders, titles and option values; a hit inside a hidden or collapsed container tells you exactly which container to open. **Tier 2 (scoped snapshot):** take an accessibility snapshot of the section's container only, not the full page. **Tier 3 (open containers):** only if tiers 1 and 2 found nothing, open the section's unopened tabs, panels or accordions one at a time, repeating tier 1 after each. Match the user's words against accessible names, labels, placeholders, titles, nearby text and headings, case-insensitive and allowing small wording differences. If not visible, look inside the section only: scroll, expand collapsed panels or accordions, open sub-tabs, check frames and shadow roots, and wait for loading. Never click save, submit, delete or similar during discovery. **Search budget:** counted in steps, not time: at most 10 discovery actions (searches, snapshots, opens, scrolls) and 3 snapshots, with a 5-minute safety limit that excludes page-loading waits (configurable as `discovery_budget`). Show one progress line per attempt ("Searching the section: opened 2 of 4 panels"). When the budget runs out, stop and go to step 3 with what was found.
3. **Decide:** exactly one confident match: continue. Several candidates: show them in plain words (label, type, position) and ask which one. None after step 2: ask the user one short question for a hint ("I couldn't find '<element>' in <section>. Which tab or panel is it under?"), then search once more using the hint within a fresh budget of 5 actions. Still none: say what the section does show and ask whether the feature is deployed to this environment.
4. **Identify the control type** from role and DOM (native or custom checkbox, radio group, text input, native select or custom dropdown, date picker, button, grid column) and handle it as section 13 says.
5. **Probe it before writing any script**, verifying the result each time (section 12):
   - checkbox or radio: set it, confirm the checked state changed; read all radio options;
   - text input: type a harmless test value, confirm the field value, then clear it;
   - dropdown: open it, read and record every option, select the requested option, confirm the displayed value;
   - button or link: confirm visible and enabled; click only if the test case requires it and it is not destructive;
   - check that it is enabled and not blocked by a precondition (e.g. another field must be set first); if blocked, find and add that precondition.
   Restore anything changed during probing unless the test needs it, and never save.
6. **Locator:** build it by the priority in Stage 2, scoped to the section's container, and confirm it matches exactly one visible element.
7. **Use what was learned:** dropdown options read in step 5 can become assertions only if the test case asks for them. Never invent expected results from what the page shows.
8. Continue with Stage 3 (draft), Stage 4 (headed end-to-end run with automatic fixes) and the normal approval flow. After approval, the new element, its options and its preconditions are added to the knowledge as `learned (needs review)` (section 15).

## 16a. Mapping a whole new section (many controls)
Use when the test case touches a new section, panel, form or dialog, or more than two new controls on one screen.
1. **Find the section** with the tiered search in section 16 (heading, panel title or tab name from the test case). Confirm its container element.
2. **Inventory in one pass:** one scoped accessibility snapshot of the container plus one DOM read of its form controls (no clicking). For every control record: label, type (text, number, date, textarea, checkbox, radio group, native select, custom dropdown, toggle, button, link, grid), stable locator, default value, enabled or disabled, read-only, required, and limits from attributes (maxlength, min, max, step, pattern, input type, accept, aria-required, aria-invalid). Read every dropdown's options and every radio group's choices (opening a custom dropdown counts as one action).
3. **Accepts and rejects:** the attributes in step 2 give the rules at no cost. Probe validation by typing invalid values only when the test case checks validation or negative cases: enter the value, move focus away, read the inline message, then clear it. Never submit or save to trigger validation unless the test case requires it.
4. **Dependencies:** after each probe, re-read the container; record controls that appear, disappear, enable or change options (e.g. "Type = Other" reveals "Reason"). These become preconditions for those controls.
5. **Section map:** show the user a table: `| Control | Type | Required | Accepts | Options | Depends on | Locator |`.
6. **Map the test case to it:** for every step and expected result, name the control and action from the section map. Show `| TC step | Control | Action | Assertion |`. A step with no matching control: ask one hint question (section 16). Only test-case steps go into the script; the rest of the map is knowledge, not test steps.
7. Continue with Stage 3 and Stage 4 as normal. After approval, save the section map to the knowledge (`app-map.md` screen entry, locators file, glossary terms) as `learned (needs review)`, so the next test on this section needs no exploration.
8. **Budget:** the inventory uses 1 snapshot and 1 DOM read; dropdown opening, probing and dependency checks use the section 16 step budget, plus 1 action per control that must be opened. If the section has more than 40 controls, map only the controls the test case names and their dependencies, and say so.
9. **Hard cases** (icon-only buttons without labels, canvas or image-based controls, controls with only generated IDs): describe them by position and nearby text and ask the user to confirm before using them.

## 17. AI activity indicator (on by default)
- **Robot runs (Stage 4 and every fix round):** locate `ai_activity_indicator.py` by name under `skills/` and add `--listener <its path>` to the robot command. Include it in the rerun command shown to the user, noting it is optional. If the file is missing, run without it and say nothing.
- **Exploration:** after opening the browser and after every navigation, run the `INDICATOR_JS` function from that file through the exploration tool's evaluate or run-JavaScript function. Ignore any error.
- Never add the indicator file or its script to test files, keywords, resources, suites, Stage 5 changes or CI configuration. Never let it change a result: if the run behaves differently with it, rerun without it and tell the user.
- If the user says "no indicator", skip it for the rest of the session.
````
