# robot-script-generator SKILL.md

Save the block below as `skills/robot-script-generator/SKILL.md` in the QA automation repo. It uses the knowledge files from the three builders and the status from knowledge-reviewer.

````markdown
---
name: robot-script-generator
description: Generates production-quality Robot Framework test scripts from AIDLC test cases, a test case ID, or a plain-language request. Reuses existing keywords and locators from the knowledge base, explores only missing UI parts live through Playwright MCP, follows the repository's own conventions for Browser (Playwright) or SeleniumLibrary, generates a draft, runs it in a visible browser and fixes it automatically until it passes end to end, then asks before adding it to the repo, branching or committing. Never writes sensitive data into code comments, documentation or tags. Can also produce a Playwright script when explicitly asked. Use when asked to generate, create, write or automate a test script.
version: 1.1.0
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
If the request has no test case ID and no description of what to check (e.g. only "execute", "run" or "generate"), do nothing else: never run existing suites or the whole repo. Ask: "Which test case ID or check do you want me to automate?" and wait.
If the input is a plain request, restate it as numbered steps and expected results and ask the user to confirm before continuing.

## 3. Pre-flight (read-only; report problems and stop if blocking)
1. Record current branch and commit. **Do not create or switch branches here.**
2. Knowledge files exist for app, keywords and locators. If not, tell the user: "Run `@qa-knowledge-setup build` first."
3. Freshness: if relevant suites or resources changed after the knowledge `last_commit`, warn and offer `@qa-knowledge-setup refresh`.
4. `knowledge/knowledge-status.md`: PASS continue; WARN warn and continue; FAIL or needs-human-review ask for explicit confirmation.
5. Resolve test environment URL and credential variables from repo conventions; confirm non-production.
6. Playwright MCP available if any gap exists.

## 4. Staged workflow (questions only before repo changes)

### Stage 1 - Plan
Extract test case ID, title, preconditions, test data (as variable names), numbered steps and numbered expected results. Resolve each step against knowledge (flow, flow step mapping, keyword, locator; prefer preferred duplicates, flow-level keywords, High then Medium stability locators). Mark each step RESOLVED, PARTIAL or GAP.
Show: `| Step | Action | Resolution | Keyword / Locator | Notes |`
Continue to the next stage without asking. Stop and ask only if a step is ambiguous, the test case is unclear, or the module's knowledge status is FAIL or needs-human-review.

### Stage 2 - Explore gaps (only if PARTIAL or GAP steps exist)
Open a **headed** browser via Playwright MCP on the test environment, replay RESOLVED steps to reach the gap, perform only the gap steps. Never click destructive actions unless the test case requires them; ask if unsure. Capture locators in this priority: `data-testid`/`data-qa` > stable unique `id` > role + accessible name > label-anchored CSS or short relative XPath > visible text. Never absolute XPath, index-based or generated IDs. Verify each matches exactly one visible element. Close the browser; save no cookies, tokens or screenshots with personal data.

### Stage 3 - Generate into a draft file (no existing file is touched)
Write the complete test, any new keywords and new locators into a **draft** file: `ai_generated_tests/<module>/<test_case_id_or_short_name>.robot` at the repo root (create the folders if missing; this staging folder is the standard location for AI-generated tests awaiting approval; it must import the same resources and libraries as the target suite, with resource and variable file paths adjusted relative to the draft's location, so it runs standalone). Follow the coding standards in section 8. Run `robot --dryrun` on the draft and fix errors.
Show the user the draft path and the full script.
Tell the user the draft path and that you are now running it in a visible browser. Do not ask; go straight to Stage 4. Never present the script as working before Stage 4 proves it.

### Stage 4 - Run headed and report
Runs automatically after Stage 3. Run only the draft test, headed (section 5), with output to `<default_output_dir>/ai-scriptgen/`. Determine the result strictly by section 6.
- **PASS:** report per-step results, duration, log and report paths.
- **FAIL:** report the failing step, the exact error, a diagnosis (locator, timing, data, environment, logic, or possible application defect). Do not ask the user. Automatically fix and rerun, up to `max_fix_attempts` (default 3) rounds. For each round: read the failing step and error from `output.xml` and the log; compare the failing step with how existing keywords and locators in the knowledge files handle the same screen; re-inspect the live page with Playwright MCP; apply the smallest correct fix (locator, wait, data, step order); rerun the full test end to end. Show one progress line per round ("Attempt 2 of 3: fixed dropdown wait, rerunning"). If it still fails after the last round, stop and explain to the user in plain language: which step fails, what the screen shows, what was tried in each round, the most likely cause, and what they can do next. If an expected result genuinely fails, report it as a possible defect; do not change the assertion.
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
- Explicit assertion for every expected result with a clear message. Explicit waits only.
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
- Element not found: report what is visible; ask whether the feature is deployed to this environment.
- Login or environment failure: report FAIL, stop, never retry repeatedly or risk locking accounts.
- Fix attempts exhausted: report FAIL with last error and diagnosis; leave the draft for manual work.
````
