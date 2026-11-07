# qa-knowledge-setup SKILL.md

Save the block below as `skills/qa-knowledge-setup/qa-knowledge-setup.md (or skills/qa-knowledge-setup/SKILL.md)` in the QA automation repo. Testers use only this skill to build or refresh all knowledge.

```markdown
---
name: qa-knowledge-setup
description: One-step, user-friendly entry point that builds, refreshes or checks the whole QA knowledge base for a repo, a folder or a single .robot file. Runs app-knowledge-builder, keyword-knowledge-builder, locator-knowledge-builder and knowledge-reviewer in order, narrating progress in plain language so any tester can follow. Use when the user says build, setup, refresh, update, rebuild, review or status for knowledge.
version: 1.3.0
---

# QA Knowledge Setup

## 1. Commands
| Command | What it does |
| `@qa-knowledge-setup build` | Build all knowledge for the whole repo, then review |
| `@qa-knowledge-setup build <folder or .robot file>` | Same, limited to that folder or file; adds to existing knowledge |
| `@qa-knowledge-setup build <topic name>` | Same, limited to the tests about that topic, e.g. `build cross reference` |
| `@qa-knowledge-setup refresh` | Update only what changed since the last build (also resumes an interrupted build) |
| `@qa-knowledge-setup rebuild` | Rebuild everything from scratch |
| `@qa-knowledge-setup rebuild <folder, .robot file or topic>` | Rebuild only that scope from scratch (extractor runs with `--full`); other knowledge is kept |
| `@qa-knowledge-setup status` | Show knowledge status and freshness; changes nothing |

Any wording with the same meaning maps to these. No command: if no knowledge exists assume `build`, otherwise `refresh`, and say so in one line.
Older knowledge: if `knowledge/app-map.md` is missing or `knowledge/.extract/summary.json` has `schema_version` below 2, a `refresh` is not enough; run a full rebuild of the requested scope automatically and say so in one line ("Your knowledge was built by an older version, so I'm rebuilding it with the application map.").
For any scope - whole repo, folder or one file - always build all three knowledge types (app, keyword, locator) for that scope, then review it, and merge into existing knowledge without losing anything.

## 2. Progress reporting is mandatory
- **Send a visible chat message to the user** (not only a thought, plan or tool call) at each of these moments: before starting, after the extractor, before and after each of the 4 parts, after each module in long runs, and at the end. Never run more than about 2 minutes or 10 tool calls without a visible message.
- Each message is one or two plain lines, using the templates in section 3.
- **Also write every progress message to `knowledge/progress.md`** (overwrite at start of the run, append after), with a timestamp, so the user can open that file anytime to see where the run is.
- Sub-agents or workers must report back to the main agent, which posts the message; a worker finishing silently is not allowed.

## 2a. How to talk to the user (narration style)
The user may not know the repo or Robot Framework. Narrate like a helpful colleague:
- Plain language, short sentences, no internal jargon (say "the steps your tests perform", not "flow registry").
- Before each stage, one line on what is happening and why. After it, one line with the result in numbers.
- Never go silent during long work; never flood the chat with file-by-file logs.
- Use exactly the messages below as templates (fill in the values).

## 3. Flow

### Step 1 - Check and plan
- Locate each skill file by name anywhere under `skills/`: `<name>.md` or `<name>/SKILL.md` or `<name>/<name>.md`, for app-knowledge-builder, keyword-knowledge-builder, locator-knowledge-builder and knowledge-reviewer. Follow the instructions in each file when running that part. If one is missing: "I can't start yet: the <name> skill is missing from the skills folder."
- Locate the extractor `extract_repo.py` under `skills/` (e.g. `skills/qa-knowledge-setup/extract_repo.py` or `skills/qa-knowledge-setup/scripts/extract_repo.py`) and use that path for every run. If there is more than one, use the newest and say so; if none, stop and say it is missing.
- Record branch and commit. Never create or switch branches.
- Count the scope, then say:

> "I'm going to learn how this application is tested, so I can later write new test scripts for you.
> I found <N> test files with about <T> tests and <R> keyword/resource files.
> I'll do this in 4 parts: 1) understand the application's screens and steps, 2) learn the existing keywords, 3) learn the existing locators, 4) double-check everything against the code.
> This can take a while for a large repo. I'll show progress as I go, and if anything stops me you can resume with `@qa-knowledge-setup refresh`.
> Starting now."

Do not wait for an answer; start immediately. Ask no questions before or during the run. The scope is exactly what the command gave: no target means the whole repo; an existing path means that folder or file; anything else is a topic name.
For a topic name: match it (case-insensitive, ignoring spaces, hyphens and underscores) against .robot file names, suite and test names, `[Tags]`, `Force Tags` and `[Documentation]`, plus existing flow and screen names in app knowledge. Include the resource files those tests use. List the matched files in the opening message ("Building knowledge for 'cross reference': 2 test files, 14 tests: <file names>"). If nothing matches, stop and say so, suggesting the closest file or topic names found; do not build the whole repo instead.

### Step 1b - Extract facts (no AI tokens)
Run the extractor in the terminal with the same Python used to run robot:
`python <extractor path>` (e.g. `python skills/qa-knowledge-setup/extract_repo.py`; add `--scope <path>` once per folder or file for scoped builds; for a topic, pass the matched files as scopes; add `--full` for rebuild).
Say: "Collecting facts from your code with Robot Framework's own parser..." then show the counts it prints.
- If it fails (e.g. Robot Framework not found), stop and tell the user the exact error and fix; do not fall back to reading raw files.
- All builders and the reviewer must use `knowledge/.extract/` (summary.json, tests.json, keywords.json, locators.json, variables.json) as their source of facts. Open raw source files only for a specific line range when the meaning of a step is unclear, never to re-collect facts.
- `knowledge/.extract/` is a cache: never edit it by hand; it can be deleted and regenerated at any time. It may contain raw test data, so make sure `knowledge/.extract/` is listed in `.gitignore` (tell the user if it is not); never commit it.
- The extract includes `routes.json` (real entry routes and prerequisites for every keyword, computed from all tests) and `ui-signals.json` (on-screen messages and UI patterns). Part 1 must use them to build the application map, glossary and UI patterns.

### Step 2 - Part 1 of 4: application knowledge
> "Part 1 of 4: Reading your tests to understand the application's screens and business steps..."

Run app-knowledge-builder for the scope. For long runs, after each module: "Module <i> of <M> done (<name>)." When finished:
> "Part 1 done: found <S> screens and <F> business flows across <M> areas, mapped how to reach every screen and what must happen first (<P> preconditions, <B> known blocking messages)."

### Step 3 - Part 2 of 4: keyword knowledge
> "Part 2 of 4: Learning the reusable keywords your team has already written..."

Run keyword-knowledge-builder. When finished:
> "Part 2 done: catalogued <K> keywords. <C> of <F> flows are fully covered by existing keywords."

### Step 4 - Part 3 of 4: locator knowledge
> "Part 3 of 4: Learning how your tests find elements on each screen..."

Run locator-knowledge-builder. When finished:
> "Part 3 done: catalogued <L> locators (<H> highly stable, <W> fragile ones flagged)."

### Step 5 - Part 4 of 4: review
> "Part 4 of 4: Double-checking everything against the actual code..."

Run knowledge-reviewer (report only). When finished, show the status table (area, status, issues).

### Step 6 - Finish
If all PASS:
> "All done. I now understand this repo: <M> areas, <F> flows, <K> keywords, <L> locators.
> What you can do next:
> - Create a test script: `@robot-script-generator TC-1234` or `@robot-script-generator check that <what you want to verify>`
> - After pulling new code: `@qa-knowledge-setup refresh`
> - See the knowledge health anytime: `@qa-knowledge-setup status`"

If there are WARN or FAIL areas:
> "Done, but <n> areas need attention: <list>. Scripts for those areas may be less reliable. Do you want me to fix the critical issues now?"
Only on yes, hand over to knowledge-reviewer remediation, then show the final message above.

## 4. Failure handling
- If a part fails, stop and say in plain words: "I stopped at part <n> (<name>) because <reason>. What's done is saved. Fix <what> and run `@qa-knowledge-setup refresh` to continue."
- Never leave the user without a next step.

## 5. Memory and stability (prevents editor crashes)
- **Stages in order, bounded parallel work inside a stage.** Stages always run in sequence: app, then keyword, then locator, then review; never run two builders at once. Inside a stage, split the work into independent units (one module or file group each) and run them with at most `max_parallel_workers` workers at a time (config, default 5, never above 6). Each worker writes only its own module or screen file; the main agent writes the index files and logs after all workers finish. Start the next unit only when a worker finishes.
- **Adaptive limit.** If the run logs show the previous run was interrupted (crash or out-of-memory), use 2 workers for this run and say so in one line; return to the normal limit after a clean run.
- **Always finish all stages.** A stage counts as done only when its index file and run log say complete. After a crash, `@qa-knowledge-setup refresh` resumes the unfinished stage and then runs every remaining stage (keyword, locator, review) automatically.
- **Small batches.** Inside every stage, process at most 5 source files per batch (fewer if files are over 1,000 lines). After each batch: write results to the knowledge files, append a checkpoint line to that stage's run log, and do not carry the batch's raw content forward.
- **Do not open files in editor tabs.** Read files with the file-read tool or terminal commands (e.g. `grep`, `sed -n`) in ranges of at most 300 lines. Close any tabs you opened.
- **No heavy helpers.** Helper scripts must stream one file at a time and never load the whole repo into memory.
- **Large scope.** If the scope has more than 40 test files, tell the user it will run in chunks, then build one module at a time; after each module, say "Module <i> of <M> saved."
- **Automatic resume.** Every run checks the run logs first and continues from the last checkpoint instead of redoing finished work. If the editor crashed, the user just runs `@qa-knowledge-setup refresh`.

## 6. Rules
- Write only inside `knowledge/`. Never modify tests, resources, config or skill files.
- Helper scripts, if needed, go in `knowledge/.tmp/` and are deleted at the end; never commit them.
- No sensitive data in any message or output.
- Never commit or push. If asked, propose `chore(knowledge): <build|refresh> knowledge base` and ask before committing.
```

## Tester quick guide (put this in `skills/README.md`)

1. One-time: `@qa-knowledge-setup build`
2. After pulling new changes: `@qa-knowledge-setup refresh`
3. Generate a script: `@robot-script-generator TC-1234` (or describe the check in one line)
4. The generator creates the test and runs it automatically (you will see the browser), fixing it if needed. It only asks before adding the test to the suite and before committing.
