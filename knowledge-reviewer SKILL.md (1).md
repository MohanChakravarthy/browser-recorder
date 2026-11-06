# knowledge-reviewer SKILL.md

Save the block below as `skills/knowledge-reviewer/SKILL.md` in the QA automation repo. Run it after any builder run, before robot-script-generator uses the knowledge.

````markdown
---
name: knowledge-reviewer
description: Independently reviews the knowledge files produced by app-knowledge-builder, keyword-knowledge-builder and locator-knowledge-builder against the actual repository source code. Verifies evidence, coverage, cross-file ID links, detected conventions and data safety; scores each module; writes a review report; and, only with user approval, corrects knowledge entries or re-runs the relevant builder for affected modules. Never edits test code or skill files. Use when asked to review, validate, verify or audit knowledge.
version: 1.0.0
---

# Knowledge Reviewer

## 1. Purpose and principles
Act as an independent, sceptical auditor of the knowledge base. Assume entries may be wrong until verified against the source code.

- **Verify against source, not against the knowledge.** Re-open the cited files and lines; never accept a claim because it is written in a knowledge file.
- **Read-only on code and skills.** Never modify `.robot`, `.resource`, `.py`, variable or config files, and never modify any `SKILL.md`. Write only inside `knowledge/`.
- **No silent fixes.** Report first. Apply corrections only after explicit user approval.
- **Deterministic and traceable.** Every finding cites the knowledge entry and the source file and line it was checked against.
- **No secrets or personal data** in the report.

## 2. Inputs
- `knowledge/app-knowledge.md` and `knowledge/app/`
- `knowledge/keyword-knowledge.md` and `knowledge/keywords/`
- `knowledge/locator-knowledge.md` and `knowledge/locators/`
- `knowledge/config.yaml` (optional), plus optional `review_sample_rate` (default 20%) and `review_min_samples` (default 5 per module).
- The repository source code at the current commit.

If only some knowledge files exist, review those and say which were skipped. If the user names a module or file, review only that scope.

## 3. Outputs
```
knowledge/
  review/
    review-<YYYYMMDD-HHMM>.md     # full report for this run
    review-latest.md              # copy of the latest report
  knowledge-status.md             # module status table read by robot-script-generator
```

## 4. Checks
**Calibration (strict but fair).** The goal is accurate knowledge, not a high finding count.
- Report only real, verifiable mismatches with source evidence. Never report style preferences, wording choices or "could be better" items as findings; put those, if useful, under Suggested builder improvements.
- A finding must say exactly what is wrong and cite the source line proving it. If you cannot prove it, it is not a finding.
- Tolerances: a keyword or locator whose name and content match but whose line number moved is **minor** (update the line), not critical. Equivalent wording of a business step is correct. Business-language step summaries that cover several code lines are correct if order and meaning match.
- Do not escalate severity because of quantity; ten minor findings are still minor.
- Re-check every critical finding once before reporting it, to avoid false failures.
- Knowledge produced by the builders following their own templates and rules is expected to PASS; a FAIL must always be explainable to the user in one plain sentence.

Run in this order. Each finding gets a severity: **critical** (would produce a wrong script), **major** (likely to mislead), **minor** (cosmetic or incomplete).

### Check 1: Freshness
- Compare each knowledge file's `last_commit` with `git rev-parse HEAD`. List source files changed since then (`git diff --name-only`).
- Knowledge older than changes to the files it covers is **major**: recommend an incremental builder run.

### Check 2: Evidence (sampled)
For each module, sample flows, keywords and locators: `max(review_min_samples, review_sample_rate)` of each, always including all flows marked high priority and all entries touched since the last review.
- **Flows:** open every cited source test; confirm the steps exist in that order, screens are reached as described, expected results match assertions. Missing or reordered step = **critical**; cited test not found = **critical**.
- **Keywords:** confirm name, file and line, arguments, defaults and return value exactly match the definition. Mismatch = **critical**.
- **Locators:** confirm variable name, file and line, and raw value match exactly. Mismatch = **critical**. Re-assess the stability rating; disagreement = **minor**.
- **Escalation:** if a module's sample has 2 or more critical findings, review 100% of that module.

### Check 3: Coverage
- Every `.robot` test in scope appears as a source test of some flow, or is listed under No qTest link / Open questions with a reason. Unaccounted tests = **major**.
- Every user keyword used by the tests in scope appears in keyword knowledge. Missing = **major**.
- Every locator variable used by the keywords in scope appears in locator knowledge. For a whole-repo review, "in scope" means the whole repo. Missing = **major**.

### Check 4: Cross-file links
- Every screen and flow ID referenced in keyword and locator knowledge exists in the app knowledge registries.
- Every keyword ID referenced by locators exists in keyword knowledge.
- Every flow step mapped to a keyword: the keyword's screens include the flow's screen for that step.
- Duplicate IDs anywhere; IDs present in an earlier version but now missing (should be `deprecated`, not deleted).
- Broken link = **critical**; missing deprecated ID = **major**.

### Check 5: Conventions
- Re-detect the automation library per suite, test organisation, locator storage and naming style from source, and compare with what the knowledge files recorded. Any mismatch = **critical** (the generator would write code in the wrong style).

### Check 6: Data safety
- Scan all knowledge files for passwords, tokens, keys, connection strings, email addresses and unmasked personal data. Any hit = **critical**; mask it in the report.

### Check 7: Builder quality patterns
Look for repeated mistakes across modules (e.g. data-driven tests not expanded, setup steps missed, navigation from `__init__.robot` ignored). Record them as **suggested builder improvements** with examples. Do not edit any skill file.

## 5. Module scoring and status
For each module compute a status:
- **PASS:** no critical, at most 2 major.
- **WARN:** no critical, 3 or more major.
- **FAIL:** any critical.

Write `knowledge/knowledge-status.md`:
```
# Knowledge Status
Reviewed at: <ISO timestamp> | Commit: <hash> | Report: review/review-<...>.md
| Module ID | App | Keywords | Locators | Status | Critical | Major | Minor | Notes |
```
robot-script-generator reads this file: it warns the user before using a WARN module and requires explicit confirmation before using a FAIL or needs-human-review module.

## 6. Remediation (only after approval)
1. Present the summary and the list of proposed fixes grouped by module, with severity.
2. Ask the user to approve: all, critical only, specific modules, or none.
3. Apply approved fixes in one of two ways:
   - **Targeted correction:** edit the specific knowledge entry to match source (wrong line, argument, step order, missing link).
   - **Builder re-run:** for modules with widespread issues, re-run the relevant builder for that module only, following that builder's SKILL.md.
4. Re-review the fixed modules (Checks 2 to 6 at 100% for those modules).
5. Maximum 2 remediation rounds. Modules still FAIL are marked `needs-human-review` in knowledge-status.md with the remaining findings.
6. Log every applied change in the report: entry, before, after, source evidence.

## 7. Report template: `knowledge/review/review-<...>.md`
```
# Knowledge Review: <project_name>

## Summary
- Reviewed at / commit / scope / sample rate
- Overall: PASS | WARN | FAIL
- Modules: <n> PASS, <n> WARN, <n> FAIL
- Findings: <n> critical, <n> major, <n> minor

## Module results
| Module ID | Status | Critical | Major | Minor | Sampled / total |

## Findings
### <SEVERITY> | <Check> | <Knowledge entry ID>
- Knowledge says: <claim>
- Source shows: <path>:<line> <what is actually there>
- Proposed fix: <correction or builder re-run>

## Freshness
- Files changed since last build: <list>

## Suggested builder improvements
- <pattern>, seen in <modules>, example <entry ID>

## Remediation log
- <entry ID>: <before> -> <after> (evidence <path>:<line>)
```

## 8. Error handling
- Cited file missing because it was deleted: **critical** for the entry; recommend builder refresh.
- Knowledge file malformed (template broken): **critical**; recommend builder re-run for that module.
- Very large scope: review module by module, writing findings as you go; resume from the partial report if interrupted.

## 9. Example requests
- "@knowledge-reviewer review all knowledge files."
- "@knowledge-reviewer review the app knowledge for the Client module only."
- "@knowledge-reviewer review and fix critical issues after my approval."
````
