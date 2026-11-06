# app-knowledge-builder SKILL.md

Save the content below as `skills/app-knowledge-builder/SKILL.md` in the QA automation repo. Copy everything from the `---` front matter onwards.

````markdown
---
name: app-knowledge-builder
description: Builds or incrementally refreshes the application knowledge base of a Robot Framework QA automation repository. Analyses regression suites, resource files and an optional qTest CSV export to map modules, screens, navigation paths, business flows, entities and test data, with stable IDs used by keyword-knowledge-builder, locator-knowledge-builder and robot-script-generator. Use when asked to build, create, refresh, update or rebuild application knowledge.
version: 1.0.0
---

# App Knowledge Builder

## 1. Purpose and principles
Produce an accurate, evidence-based map of how the application under test works, derived from the existing automated regression tests. It is the foundation for every downstream skill, so accuracy beats speed.

- **Evidence only.** Every screen, flow and entity must be traceable to at least one source test or qTest case. Never infer features that are not evidenced; record uncertainty under Open questions.
- **Read-only on the codebase.** Never modify, move, format or delete any `.robot`, `.resource`, `.py`, variable or config file. Write only inside `knowledge/`.
- **Stable IDs.** IDs, once issued, never change. Downstream skills depend on them.
- **Deterministic output.** Same input produces the same structure: sort modules, screens and flows alphabetically by ID; use the exact templates below.
- **No secrets.** Never copy passwords, tokens, API keys, connection strings, real customer names or personal data into knowledge files. Refer to them by variable name only (e.g. `${PORTAL_PASSWORD}`).

## 2. Inputs
**Primary source of facts: `knowledge/.extract/`** (produced by `skills/qa-knowledge-setup/scripts/extract_repo.py`). Use `tests.json` for test names, files, lines, tags, documentation, setup/teardown, templates and ordered steps (with resolved keyword targets); `summary.json` for library per file, test organisation and parse errors. If `.extract/` is missing or older than the current commit, run the extractor first. Do not read raw `.robot` files to collect facts; open a raw file only for a specific line range when a step's business meaning is unclear. Your job here is meaning: modules, screens, flows, business-language steps and IDs.

1. **Config (optional):** `knowledge/config.yaml`
   - `project_name` (default: repo folder name)
   - `suites_paths` (default: auto-detect folders containing `.robot` files)
   - `resources_paths` (default: auto-detect `.resource` and keyword `.robot` files)
   - `qtest_export_path` (default: `qtest-export/`)
   - `exclude_paths` (always excluded: `results/`, `output/`, `logs/`, `reports/`, `.venv/`, `venv/`, `node_modules/`, `.git/`)
   - `module_map` (optional: folder or tag to module name overrides)
2. **Robot Framework sources:** suites, resource files, variable files, and `__init__.robot` files (suite setup and teardown).
3. **qTest export (optional):** `.csv` preferred; `.xlsx` accepted. Expected columns (match case-insensitively and by closest name): Test Case ID, Name, Module or Folder, Description, Precondition, Step, Expected Result, Priority, Status. If the folder is missing or empty, proceed with Robot sources only and record `qtest_export_used: no`.

If the user's request names specific folders, modules or files, limit the run to those.

## 3. Outputs
```
knowledge/
  app-knowledge.md          # index, registries, run metadata
  app/
    MOD-<NAME>.md           # one detail file per module
  app-knowledge.log.md      # run history (append-only)
```
Create missing folders. Overwrite only the files you are regenerating; never delete a module file, mark it deprecated instead.

## 4. Procedure

### Step 1: Pre-flight
- Confirm the workspace is a git repository and capture `git rev-parse HEAD` and the current branch. If there are uncommitted changes to `.robot` or `.resource` files, warn the user that knowledge will reflect the working copy.
- Load `knowledge/config.yaml` if present; validate paths exist and report any that do not.
- Inventory sources: count suite files, test cases, resource files, keywords, and qTest rows. Show this inventory to the user before heavy processing.

### Step 2: Detect framework and conventions
- **Automation library** from `Library` imports and `requirements*.txt` / `pyproject.toml`: `Browser` = Robot Framework Browser (Playwright); `SeleniumLibrary` = Selenium. Record per suite if mixed.
- **Test organisation:** one test per `.robot` file, or many tests per suite file.
- **Test ID convention:** where qTest IDs live (tags such as `TC-1234`, `[Documentation]`, or test names).
- **Environment and login pattern:** how URLs and credentials are supplied (variable files, CLI variables, environment variables).
- **Common setup and teardown** from `__init__.robot` and `Suite Setup` / `Test Setup`.

### Step 3: Choose full or incremental run
- If `knowledge/app-knowledge.md` has `last_commit` and that commit exists, run `git diff --name-only <last_commit> HEAD` and process only changed, added or deleted sources; regenerate only the affected module files and the index.
- If `last_commit` is missing or unreachable, or the user asks for a rebuild, run in full.
- Deleted tests: remove their citations; if a flow loses all evidence, mark it `deprecated` (keep its ID).

### Step 4: Build the module list
- Derive modules from folder structure, suite names, `Force Tags`, `[Documentation]` and qTest Module or Folder, applying `module_map` overrides.
- Show the proposed module list (name, ID, number of tests) and continue unless the user objects. Avoid modules with under 3 tests unless clearly distinct.

### Step 5: Process one module at a time
Large repos (hundreds of tests) must never be read in one pass. Memory safety: parallel workers only up to the limit set by qa-knowledge-setup (default 5), one module per worker, each writing only its own module file, with the index written by the main agent after all workers finish; read at most 5 files per batch using the file-read tool or terminal commands in ranges of at most 300 lines, never by opening editor tabs; after each batch write results and a checkpoint to the run log and do not carry raw file content forward; on start, resume from the last checkpoint.
1. For each module, read its tests: name, `[Documentation]`, `[Tags]`, `[Setup]`, `[Teardown]`, `[Template]` and steps.
2. Follow keyword calls into resource files only as deep as needed to understand navigation and business actions (normally 2 levels). Do not catalogue keywords or locators here; other skills do that.
3. Expand data-driven tests (`[Template]`, FOR loops) into the business variations they cover, e.g. one flow with several cross reference types.
4. Match qTest rows to tests by ID. Use qTest steps and expected results to describe business meaning. Record unmatched qTest cases as **Not automated**, and Robot tests with no qTest ID as **No qTest link**.
5. Write the module file, then append a progress line to the run log, then move to the next module. If the run is interrupted, resume from the log.

### Step 6: Extract per module
- **Screens:** ID, name, navigation path from login, and UI areas (tabs, grids, dialogs, dropdowns, forms) evidenced by tests.
- **Flows:** ID, name, purpose, preconditions, test data (by variable name), ordered business steps, screens touched, expected results, variations, priority if known, and source tests.
- **Entities:** business objects and their known values or types (e.g. Client, Cross Reference, Cross Reference Type).
- **Dependencies:** flows that must run first (e.g. Login, Open Client).

### Step 7: Build the index
Assemble `knowledge/app-knowledge.md` from all module files (template in section 6).

### Step 8: Self-validate before finishing
Your output must pass knowledge-reviewer. Apply its evidence, coverage, link, convention and data-safety checks to every entry written in this run, fix any failure, and only then finish. Helper scripts, if needed, go in `knowledge/.tmp/` and are deleted before finishing; never leave them in the repo.
- Every flow cites at least one existing source file and test name (verify the files exist).
- Every screen referenced by a flow is defined in a module file.
- No duplicate IDs; no previously issued ID is missing (deprecated is fine).
- No secrets or personal data in output (scan for password, token, secret, apikey patterns and email addresses).
- Counts in the index match the module files.
Fix any failure before reporting.

### Step 9: Report to the user
Summarise: full or incremental run, modules processed, counts of screens, flows, entities and tests covered, qTest matched vs not automated vs no qTest link, deprecated items, open questions, and output paths. Do not commit; leave committing to the user.

## 5. ID rules (critical for linking)
- Module: `MOD-<NAME>`, e.g. `MOD-CLIENT`.
- Screen: `SCREEN-<MODULE>-<NAME>`, e.g. `SCREEN-CLIENT-CROSS-REFERENCE-TAB`.
- Flow: `FLOW-<MODULE>-<ACTION>`, e.g. `FLOW-CLIENT-ADD-CROSS-REFERENCE`.
- Entity: `ENT-<NAME>`, e.g. `ENT-CROSS-REFERENCE-TYPE`.
- Uppercase, hyphen-separated, ASCII only, max 60 characters, unique across the repo.
- Never rename or reuse an ID. Mark obsolete items `Status: deprecated`. If a name changes, keep the ID and update the name.

## 6. Templates

### Module file: `knowledge/app/MOD-<NAME>.md`
```
# Module: <Name> (MOD-<NAME>)
Last updated: <ISO date> | Commit: <hash> | Status: active

## Summary
<2-3 sentences: what this module does for the business>

## Screens
### SCREEN-<...> | <Name>
- Navigation: Login > <Menu> > <Page> > <Tab>
- UI areas: <tabs, grids, dialogs, dropdowns, forms>
- Status: active

## Flows
### FLOW-<...> | <Name>
- Purpose: <one line>
- Depends on: FLOW-<...>
- Preconditions: <state required>
- Test data: ${VARIABLE_NAMES}
- Steps:
  1. <business-language step>
  2. ...
- Screens: SCREEN-<...>, SCREEN-<...>
- Expected results: <observable outcomes>
- Variations: <data-driven cases, e.g. types ABCD, EFGH>
- Priority: <from qTest if known>
- Source tests: <path>::<test name> [<qTest ID>]
- Status: active

## Entities
- ENT-<...> | <Name>: <attributes / known values>

## Not automated (qTest only)
- <qTest ID> | <name> | <one-line summary>

## No qTest link
- <path>::<test name>

## Open questions
- <what is unclear and which test raised it>
```

### Index file: `knowledge/app-knowledge.md`
```
# Application Knowledge: <project_name>

## Metadata
- schema_version: 1
- generated_at: <ISO timestamp>
- last_commit: <hash>
- branch: <branch>
- automation_library: Browser | SeleniumLibrary | mixed (see per-suite list)
- test_organisation: one-test-per-file | many-tests-per-suite
- test_id_convention: <e.g. tag TC-####>
- qtest_export_used: yes | no

## Overview
<one paragraph describing the application>

## Modules
| Module ID | Name | File | Screens | Flows | Tests |

## Screen registry
| Screen ID | Name | Module | Navigation |

## Flow registry
| Flow ID | Name | Module | Depends on | Status |

## Common flows
<login, main navigation, global setup and teardown>

## Coverage
- Robot tests analysed / qTest matched / not automated / no qTest link
```

## 7. Writing rules
- Business language in steps ("Open client", "Go to Cross Reference tab"), never locators or code.
- Concise bullets; no copied code blocks from the repo.
- Use only the templates above; do not add or rename sections.
- When unsure, ask in Open questions rather than guess.

## 8. Error handling
- Unparseable file: skip it, list it in the report and run log, continue.
- qTest file with unrecognised columns: show the detected headers, map what you can, and ask the user to confirm the mapping before using it.
- Conflicting evidence (e.g. two navigation paths): record both with their sources and add an Open question.
- Context pressure: if a module is too large, split it into sub-modules (`MOD-CLIENT-XREF`) rather than skimming.

## 9. Example requests
- "@app-knowledge-builder build the application knowledge for this repo."
- "@app-knowledge-builder build the application knowledge using the regression suites and the qTest export."
- "@app-knowledge-builder refresh the application knowledge for changes since the last run."
- "@app-knowledge-builder rebuild the knowledge for the Client module only."
````
