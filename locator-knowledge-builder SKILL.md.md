# locator-knowledge-builder SKILL.md

Save the block below as `skills/locator-knowledge-builder/SKILL.md` in the QA automation repo. Run it after app-knowledge-builder and keyword-knowledge-builder.

````markdown
---
name: locator-knowledge-builder
description: Builds or incrementally refreshes the locator knowledge base of a Robot Framework QA automation repository. Catalogues every locator (variables, locator files, inline locators in keywords and tests), normalises their strategy and syntax for Browser (Playwright) or SeleniumLibrary, rates their stability, and links each to the screen IDs from app-knowledge-builder and the keyword IDs from keyword-knowledge-builder, so robot-script-generator can reuse existing locators and add new ones in the right place and style. Use when asked to build, refresh or rebuild locator knowledge.
version: 1.0.0
---

# Locator Knowledge Builder

## 1. Purpose and principles
Give robot-script-generator a reliable answer to: "Is there already a locator for this element on this screen, what is its exact variable name and syntax, how stable is it, and where should a new locator go?"

- **Evidence only.** Every entry comes from a real definition in the repo, with file and line.
- **Read-only on the codebase.** Never modify, move, format or delete repo files. Write only inside `knowledge/`.
- **Static analysis only.** Do not open a browser or call Playwright MCP in this skill; live verification belongs to robot-script-generator.
- **Linked by IDs.** Use screen IDs from `knowledge/app-knowledge.md` and keyword IDs from `knowledge/keyword-knowledge.md` exactly. Never invent screen or keyword IDs.
- **Stable IDs, deterministic output.** Sort by locator ID; use the templates below.
- **No secrets or personal data.** Locators containing real customer names, emails or IDs are recorded with the value masked and flagged.

## 2. Prerequisites and inputs
- `knowledge/app-knowledge.md` and `knowledge/keyword-knowledge.md` must exist. If either is missing, stop and ask the user to run the earlier builders first.
- `knowledge/config.yaml` (optional): same paths and excludes as the other builders; optional `locator_paths`.
- Sources: `*** Variables ***` sections, variable files (`.py`, `.yaml`, `.json`), dedicated locator or page-object files, `.resource` files, and inline locators inside keywords and tests.

## 3. Outputs
```
knowledge/
  locator-knowledge.md          # index, conventions, registry
  locators/
    SCREEN-<...>.md             # locators grouped by screen
    UNMAPPED.md                 # locators not yet tied to a screen
  locator-knowledge.log.md      # run history (append-only)
```

## 4. Procedure

### Step 1: Pre-flight
- Capture `git rev-parse HEAD` and branch; warn about uncommitted changes to locator or resource files.
- Load the screen registry from app knowledge and the keyword registry from keyword knowledge.
- Inventory: count locator variables, locator files, inline locators. Show the inventory before heavy processing.

### Step 2: Full or incremental
Same rule as the other builders, using `last_commit` in `locator-knowledge.md`. Run in full if app or keyword knowledge has a newer commit than recorded in `linked_app_commit` / `linked_keyword_commit`.

### Step 3: Detect conventions (write to the index)
- Automation library per file: Browser or SeleniumLibrary.
- Where locators live: variables sections, separate locator files per page, page objects, or inline.
- Naming style of locator variables (e.g. `${XREF_TYPE_DROPDOWN}`, `${btn_save}`), and any prefixes or suffixes for element type.
- Preferred strategies actually used (e.g. `id=`, `css=`, `xpath=`, `text=`, `data-testid`, Selenium `id:` / `xpath:` / `css:`).
- Dynamic locator patterns: templated variables (`${ROW_BY_NAME}` with `{name}` placeholders), `Replace String`, `Format String`, embedded arguments.
- Frame, iframe and shadow DOM handling patterns (`>>>`, `Select Frame`, `id=frame >>> css=...`).

### Step 4: Catalogue locators, one file at a time
For each locator record:
- Locator ID `LOC-<SCREEN or COMMON>-<NAME>`, variable name (or `inline` with keyword ID), file path and line.
- Raw value exactly as written (masking personal data) and the **normalised** form: strategy + selector.
- Library syntax: Browser or SeleniumLibrary.
- Element type (button, input, dropdown, option, tab, link, grid, row, cell, checkbox, radio, label, dialog, frame) and business meaning ("Cross Reference Type dropdown").
- Dynamic: yes/no; if yes, its placeholders and how they are filled.
- Frame or shadow context, if any.
- **Links:** screen ID (from the keywords and flows that use it), and keyword IDs that use it.
- Usage count and status: `active`, `unused`, `deprecated`.
- **Stability rating** (see section 5) with a one-line reason.

To map a locator to a screen: follow the keywords that use it to their screen links; if several screens, choose the one where it is used most and list the others. If none, put it in UNMAPPED.md.

### Step 5: Detect quality issues (report only, never fix)
- Duplicates: different variables with the same normalised selector; mark the most-used as **preferred**.
- Same variable name defined in multiple files with different values (conflict).
- Brittle locators: absolute XPath, index-based (`[3]`, `nth=`), auto-generated class names or IDs, long text matches likely to change.
- Inline locators that should be variables, per the repo's own convention.

### Step 6: Self-validate
- Locator IDs unique; file paths and lines exist.
- Every screen and keyword ID used exists in the other knowledge files.
- Counts in the index match the screen files.
- No unmasked personal data or secrets.

### Step 7: Report
Run type, locators catalogued, mapped vs unmapped, stability breakdown, duplicates, conflicts, brittle locators, output paths. Do not commit.

## 5. Stability rating
- **High:** dedicated test attributes (`data-testid`, `data-qa`), stable unique `id`, ARIA role + accessible name.
- **Medium:** semantic CSS, short relative XPath anchored on stable attributes or labels, exact visible text of stable labels.
- **Low:** absolute XPath, index or position based, generated classes or IDs, long or translated text.
The generator prefers High, then Medium; Low locators are reused only if no alternative exists, and flagged.

## 6. ID rules
- `LOC-<SCREEN-SHORT>-<NAME>` or `LOC-COMMON-<NAME>`, uppercase, hyphenated, unique, never renamed or reused. If the variable is renamed in code, keep the ID and update the name.

## 7. Templates

### Screen file: `knowledge/locators/SCREEN-<...>.md`
```
# Locators: <Screen name> (SCREEN-<...>)
Last updated: <ISO date> | Commit: <hash>
Defined in: <main locator file for this screen>

| Locator ID | Variable | Element | Meaning | Strategy | Selector | Dynamic | Stability | Used by | Status |

## Details (only for dynamic, framed, duplicate or low-stability locators)
### LOC-<...>
- File: <path>:<line>
- Placeholders: {name} filled by <keyword ID>
- Frame: <frame locator>
- Duplicate of: LOC-<...> (preferred: yes|no)
- Stability reason: <why>

## Where new locators for this screen go
<file path and section, following the repo convention>
```

### Index file: `knowledge/locator-knowledge.md`
```
# Locator Knowledge: <project_name>

## Metadata
- schema_version: 1
- generated_at / last_commit / branch
- linked_app_commit / linked_keyword_commit

## Conventions
- Library, locator storage layout, naming style (with a real example)
- Strategies in use and the preferred order for new locators
- Dynamic locator pattern (with a real example)
- Frame / shadow DOM pattern

## Screen coverage
| Screen ID | Locators | High | Medium | Low | File |

## Quality findings
- Duplicates, conflicts, brittle locators, inline locators, unmapped count
```

## 8. Error handling
- Unparseable file: skip, log, continue.
- Locator built at runtime that cannot be resolved statically: record its pattern and the keyword that builds it, mark `Dynamic: yes (runtime)`.
- Ambiguous screen mapping: link the primary screen, list the others.
- Large files: process in sections; never skim.

## 9. Example requests
- "@locator-knowledge-builder build the locator knowledge for this repo."
- "@locator-knowledge-builder refresh locator knowledge since the last run."
- "@locator-knowledge-builder rebuild locator knowledge for the Cross Reference screen only."
````
