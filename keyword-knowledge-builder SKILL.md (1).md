# keyword-knowledge-builder SKILL.md

Save the block below as `skills/keyword-knowledge-builder/SKILL.md` in the QA automation repo. Run it after app-knowledge-builder.

````markdown
---
name: keyword-knowledge-builder
description: Builds or incrementally refreshes the keyword knowledge base of a Robot Framework QA automation repository. Catalogues every user keyword (and the library keywords in use), records arguments, return values, location and usage, links each keyword to the screen and flow IDs from app-knowledge-builder, and records the repo's coding conventions so robot-script-generator can reuse keywords and write code in the same style. Use when asked to build, refresh or rebuild keyword knowledge.
version: 1.0.0
---

# Keyword Knowledge Builder

## 1. Purpose and principles
Give robot-script-generator a reliable answer to: "Which existing keyword performs this business step, how do I call it, and where should a new keyword go?"

- **Evidence only.** Every keyword entry comes from a real definition in the repo, with file and line.
- **Read-only on the codebase.** Never modify, move, format or delete repo files. Write only inside `knowledge/`.
- **Linked by IDs.** Reuse screen and flow IDs exactly as defined in `knowledge/app-knowledge.md`. Never invent new screen or flow IDs; report unmatched keywords instead.
- **Stable IDs and deterministic output.** Sort entries alphabetically by keyword ID; use the templates below.
- **No secrets.** Never copy credential values; refer to variables by name only.

## 2. Prerequisites and inputs
- `knowledge/app-knowledge.md` and `knowledge/app/` must exist. If missing, stop and ask the user to run app-knowledge-builder first.
- `knowledge/config.yaml` (optional): same paths and excludes as app-knowledge-builder.
- Sources: `.resource` files, `*** Keywords ***` sections in `.robot` files, Python keyword libraries in the repo (functions or methods decorated with `@keyword` or exposed via library classes), variable files, `requirements*.txt` / `pyproject.toml`.

## 3. Outputs
```
knowledge/
  keyword-knowledge.md        # index, conventions, registry
  keywords/
    MOD-<NAME>.md             # keywords grouped by module
    COMMON.md                 # cross-module keywords (login, navigation, waits, utilities)
  keyword-knowledge.log.md    # run history (append-only)
```

## 4. Procedure

### Step 1: Pre-flight
- Capture `git rev-parse HEAD` and branch; warn about uncommitted changes to keyword files.
- Read the app knowledge index: load the screen, flow and module registries.
- Inventory: count resource files, user keywords, Python library keywords. Show the inventory before heavy processing.

### Step 2: Full or incremental
Same rule as app-knowledge-builder, using `last_commit` in `keyword-knowledge.md`. Also run in full if `app-knowledge.md` has a newer `last_commit` than the keyword knowledge was linked against (recorded as `linked_app_commit`).

### Step 3: Detect conventions (write to the index)
- Automation library per resource file: Browser or SeleniumLibrary (from `Library` imports).
- Resource file layout: e.g. one resource per page or module, a common resource, a locators file.
- Keyword naming style (e.g. Title Case verbs: "Navigate To Cross Reference Tab"), argument style (`${client_name}` vs `${CLIENT_NAME}`), embedded-argument usage.
- Documentation style: whether keywords use `[Documentation]`, `[Tags]`, `[Arguments]`, `[Return]` / `RETURN`.
- Wait and assertion patterns actually used (e.g. `Wait For Elements State`, `Wait Until Element Is Visible`, `Get Text ... ==`).
- Where locators are defined: in keywords inline, in variables sections, or in separate locator files.
- Test organisation (copied from app knowledge): one test per file or many tests per suite.

### Step 4: Catalogue keywords, one resource file at a time
For each user keyword record:
- Keyword ID `KW-<MODULE or COMMON>-<NAME>`, exact keyword name, file path and line number.
- Arguments with defaults, embedded arguments, return value.
- One-line purpose in business language (from `[Documentation]`, or inferred from its steps; mark inferred).
- Library keywords it calls (summarised) and user keywords it calls (by keyword ID), giving a call tree.
- Locator variables it uses (by variable name only; locator-knowledge-builder details them).
- **Links:** screen IDs it acts on and flow IDs or flow steps it performs, matched from the app knowledge flows and the tests that call it.
- **Usage:** number of tests calling it and 2-3 example tests (path::test name).
- **Level:** `step` (one UI action), `page` (a screen task), or `flow` (a complete business flow).
- Status: `active`, `unused` (no callers), or `deprecated` (removed from code).

Also record library keywords actually used in the repo, with usage counts, so the generator knows the accepted vocabulary.

### Step 5: Map flow steps to keywords
For every flow in the app knowledge, map each business step to the keyword that performs it (or `GAP` if none). Write this as a step-to-keyword table in the module file. This table is what robot-script-generator uses first.

### Step 6: Detect quality issues (report only, never fix)
- Duplicate or near-duplicate keywords (same steps, different names): list them and mark the most-used as **preferred**.
- Keywords with hard-coded waits (`Sleep`), hard-coded data or credentials-like literals.
- Unused keywords.

### Step 7: Self-validate
Your output must pass knowledge-reviewer. Apply its evidence, coverage, link, convention and data-safety checks to every entry written in this run, fix any failure, and only then finish. Helper scripts, if needed, go in `knowledge/.tmp/` and are deleted before finishing; never leave them in the repo.
- Every keyword ID unique; every file path and line exists.
- Every screen and flow ID used exists in the app knowledge registries.
- Counts in the index match the module files.
- No secrets in output.

### Step 8: Report
Run type, keywords catalogued, links made, flows fully covered vs with gaps, duplicates, unused, unmatched keywords, output paths. Do not commit.

## 5. ID rules
- `KW-<MODULE>-<NAME>` or `KW-COMMON-<NAME>`, uppercase, hyphenated, unique, never renamed or reused. If a keyword is renamed in code, keep the ID and update the name.

## 6. Templates

### Module file: `knowledge/keywords/MOD-<NAME>.md`
```
# Keywords: <Module name> (MOD-<NAME>)
Last updated: <ISO date> | Commit: <hash>

## Flow step mapping
### FLOW-<...> | <Flow name>
| # | Business step | Keyword ID | Keyword call |
| 1 | Log in | KW-COMMON-LOGIN-TO-PORTAL | Login To Portal    ${USER}    ${PASSWORD} |
| 2 | Open client | KW-CLIENT-OPEN-CLIENT | Open Client    ${client_name} |
| 3 | Select new option | GAP | - |

## Keywords
### KW-<...> | <Exact Keyword Name>
- File: <path>:<line>
- Library: Browser | SeleniumLibrary
- Level: step | page | flow
- Arguments: ${arg1}, ${arg2}=default
- Returns: <value or none>
- Purpose: <business language> (inferred: yes|no)
- Screens: SCREEN-<...>
- Flows: FLOW-<...> (step n)
- Calls: KW-<...>, KW-<...>
- Locator variables: ${CROSS_REF_TAB}, ...
- Used by: <count> tests, e.g. <path>::<test>
- Preferred: yes | no (duplicate of KW-<...>)
- Status: active | unused | deprecated
```

### Index file: `knowledge/keyword-knowledge.md`
```
# Keyword Knowledge: <project_name>

## Metadata
- schema_version: 1
- generated_at / last_commit / branch
- linked_app_commit: <app knowledge commit>

## Conventions
- Automation library (per resource file if mixed)
- Resource layout and where new keywords for each module belong
- Naming, argument and documentation style (with one real example)
- Wait and assertion patterns in use
- Where locators live
- Test organisation

## Registry
| Keyword ID | Name | Module | Level | Used by | Status |

## Library keywords in use
| Library | Keyword | Uses |

## Coverage
- Flows fully mapped / flows with gaps (list gap steps)

## Quality findings
- Duplicates, Sleep usage, hard-coded data, unused keywords
```

## 7. Error handling
- Unparseable file: skip, log, continue.
- Keyword that matches no screen or flow: keep it, list it under "Unlinked" in the module or COMMON file.
- Ambiguous match (one keyword fits several flows): link all, note it.
- Large resource files: process in sections; never skim.

## 8. Example requests
- "@keyword-knowledge-builder build the keyword knowledge for this repo."
- "@keyword-knowledge-builder refresh keyword knowledge since the last run."
- "@keyword-knowledge-builder rebuild keyword knowledge for the Client module only."
````
