# extract\_repo.py (knowledge extractor)

Save as `skills/qa-knowledge-setup/extract_repo.py`. Paste **Part 1** and then **Part 2** directly after it into the same file, with nothing in between. First run: `python skills/qa-knowledge-setup/extract_repo.py --self-test` (use the same Python you use to run robot).

## Part 1 of 2

```python
#!/usr/bin/env python3
"""
extract_repo.py - deterministic fact extractor for Robot Framework QA repositories.

Part of the qa-knowledge-setup skill. Uses Robot Framework's official parsing API
(robot.api.parsing) to extract tests, keywords, variables, locators, imports and call
relations into compact JSON, so the AI never has to read raw source files.

- Read-only on the repository. Writes only to the output folder (default knowledge/.extract).
- Processes one file at a time (low memory).
- Incremental: files whose SHA-256 is unchanged are reused from the previous run.
- Masks secrets (variables named like password/token/secret/key) and emails / long digit runs.

Usage:
  python extract_repo.py                                   # whole repo (current folder)
  python extract_repo.py --scope "test cases/cross_reference.robot"
  python extract_repo.py --scope tests --scope resources --full
  python extract_repo.py --self-test                       # verify the extractor works here

Requires: robotframework >= 4.0 (already installed wherever tests run). PyYAML optional.
"""
import argparse, ast, hashlib, json, os, re, sys, tempfile, shutil
from datetime import datetime, timezone

try:
    from robot.api.parsing import get_model, get_resource_model, get_init_model
    from robot.version import VERSION as RF_VERSION
except ImportError:
    sys.exit("ERROR: Robot Framework is not installed in this Python environment. "
             "Use the same Python you use to run robot (e.g. activate your venv).")

SCHEMA_VERSION = 2
DEFAULT_EXCLUDES = {"results", "output", "outputs", "logs", "reports", ".venv", "venv",
                    "node_modules", ".git", "knowledge", "__pycache__", ".tmp",
                    "ai_generated_tests"}  # AI drafts must never become evidence
SECRET_NAME = re.compile(r"(pass(word)?|pwd|token|secret|api[_-]?key|credential|auth)", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
LONG_DIGITS = re.compile(r"(?<![\w$])\d{6,}(?!\w)")
LOCATOR_VALUE = re.compile(
    r"^\s*(css[=:]|xpath[=:]|id[=:]|name[=:]|text[=:]|link[=:]|partial link[=:]|class[=:]|"
    r"tag[=:]|dom[=:]|data-test|//|\(//|\.//|#[A-Za-z]|\[data-|role=|aria/|"
    r"[a-z]+\[[^\]]*=)", re.I)
LOCATOR_NAME = re.compile(r"(loc|locator|btn|button|txt|input|field|dropdown|ddl|select|"
                          r"link|tab|grid|row|cell|chk|checkbox|radio|lbl|label|icon|menu|"
                          r"xpath|css|selector|elem|element|dialog|modal|frame)", re.I)
# library keywords whose FIRST argument is a locator
BROWSER_LOCATOR_KWS = {"click", "fill text", "type text", "fill secret", "type secret",
    "select options by", "check checkbox", "uncheck checkbox", "get text", "get element",
    "get elements", "get attribute", "get property", "get element count", "get element states",
    "wait for elements state", "hover", "focus", "scroll to element", "clear text",
    "press keys", "get selected options", "upload file by selector", "highlight elements",
    "get checkbox state", "drag and drop", "take screenshot"}
SELENIUM_LOCATOR_KWS = {"click element", "click button", "click link", "click image",
    "input text", "input password", "select from list by label", "select from list by value",
    "select from list by index", "select checkbox", "unselect checkbox", "get text",
    "get webelement", "get webelements", "get element attribute", "get value",
    "wait until element is visible", "wait until element is not visible",
    "wait until element is enabled", "wait until page contains element",
    "wait until page does not contain element", "element should be visible",
    "element should not be visible", "element should contain", "element text should be",
    "page should contain element", "page should not contain element",
    "mouse over", "scroll element into view", "clear element text", "select frame",
    "list selection should be", "checkbox should be selected", "get selected list label",
    "set focus to element", "double click element", "press keys", "choose file",
    "element should be enabled", "element should be disabled", "get element count"}
LOCATOR_KWS = BROWSER_LOCATOR_KWS | SELENIUM_LOCATOR_KWS


def norm(name):
    return re.sub(r"[\s_]", "", (name or "")).lower()


def mask(value, var_name=""):
    if value is None:
        return value
    if var_name and SECRET_NAME.search(var_name):
        return "***MASKED***"
    v = EMAIL.sub("***EMAIL***", str(value))
    return LONG_DIGITS.sub("***NUM***", v)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def tname(node):
    return type(node).__name__


def tokens_of(stmt, *types):
    try:
        return [t.value for t in stmt.get_tokens(*types)]
    except Exception:
        return []


# ---------------------------------------------------------------- robot parsing
def collect_calls(body, depth=0, out=None, ctx=None):
    """Flatten keyword calls from a test/keyword body, including FOR/IF/TRY/WHILE/GROUP blocks."""
    out = [] if out is None else out
    for node in body or []:
        n = tname(node)
        if n == "KeywordCall":
            out.append({"keyword": node.keyword, "args": [mask(a) for a in node.args],
                        "assign": list(node.assign), "line": node.lineno,
                        "depth": depth, "context": ctx})
        elif n in ("For", "While", "If", "InlineIf", "Try", "Group"):
            header = getattr(node, "header", None)
            label = n.upper()
            if header is not None:
                cond = " ".join(tokens_of(header, "ARGUMENT"))
                label = f"{n.upper()} {mask(cond)}".strip()
            collect_calls(getattr(node, "body", []), depth + 1, out, label)
            nxt = getattr(node, "orelse", None) or getattr(node, "next", None)
            while nxt is not None:
                collect_calls(getattr(nxt, "body", []), depth + 1, out, label + " (branch)")
                nxt = getattr(nxt, "orelse", None) or getattr(nxt, "next", None)
        elif n in ("Setup", "Teardown"):
            name = getattr(node, "name", None)
            if name:
                out.append({"keyword": name, "args": [mask(a) for a in getattr(node, "args", ())],
                            "assign": [], "line": node.lineno, "depth": depth,
                            "context": n.upper()})
    return out


def parse_settings_block(body, rec):
    for node in body or []:
        n = tname(node)
        if n in ("Documentation",):
            rec["documentation"] = mask(getattr(node, "value", ""))
        elif n in ("Tags",):
            rec["tags"] = list(getattr(node, "values", ()))
        elif n == "Setup":
            rec["setup"] = getattr(node, "name", None)
        elif n == "Teardown":
            rec["teardown"] = getattr(node, "name", None)
        elif n == "Template":
            rec["template"] = getattr(node, "value", None)
        elif n == "Arguments":
            rec["arguments"] = list(getattr(node, "values", ()))
        elif n in ("ReturnSetting", "Return", "ReturnStatement"):
            rec["returns"] = list(getattr(node, "values", ()))
        elif n == "Timeout":
            rec["timeout"] = getattr(node, "value", None)


def parse_robot_file(path, rel):
    base = os.path.basename(path).lower()
    if base == "__init__.robot":
        model, kind = get_init_model(path), "init"
    elif path.lower().endswith(".resource"):
        model, kind = get_resource_model(path), "resource"
    else:
        model = get_model(path)
        kind = "suite"
    rec = {"file": rel, "kind": kind, "settings": {}, "imports": {"libraries": [],
           "resources": [], "variables": []}, "tests": [], "keywords": [], "variables": [],
           "errors": []}
    has_tests = False
    for section in model.sections:
        sname = tname(section)
        if sname == "SettingSection":
            for node in section.body:
                n = tname(node)
                if n == "LibraryImport":
                    rec["imports"]["libraries"].append({"name": node.name,
                        "args": list(node.args), "alias": getattr(node, "alias", None),
                        "line": node.lineno})
                elif n == "ResourceImport":
                    rec["imports"]["resources"].append({"name": node.name, "line": node.lineno})
                elif n == "VariablesImport":
                    rec["imports"]["variables"].append({"name": node.name, "line": node.lineno})
                elif n == "Documentation":
                    rec["settings"]["documentation"] = mask(node.value)
                elif n in ("SuiteSetup", "SuiteTeardown", "TestSetup", "TestTeardown",
                           "TestTemplate", "TestTimeout"):
                    rec["settings"][n] = {"name": getattr(node, "name", None) or
                                          getattr(node, "value", None),
                                          "args": [mask(a) for a in getattr(node, "args", ())]}
                elif n in ("ForceTags", "TestTags", "DefaultTags", "KeywordTags"):
                    rec["settings"][n] = list(node.values)
        elif sname == "VariableSection":
            for node in section.body:
                if tname(node) == "Variable" and getattr(node, "name", None):
                    raw = " | ".join(node.value) if node.value else ""
                    rec["variables"].append({"name": node.name, "value": mask(raw, node.name),
                                             "line": node.lineno})
        elif sname == "TestCaseSection":
            has_tests = True
            for tc in section.body:
                if tname(tc) != "TestCase":
                    continue
                t = {"name": tc.name, "line": tc.lineno, "documentation": "", "tags": [],
                     "setup": None, "teardown": None, "template": None}
                parse_settings_block(tc.body, t)
                t["steps"] = collect_calls(tc.body)
                rec["tests"].append(t)
        elif sname == "KeywordSection":
            for kw in section.body:
                if tname(kw) != "Keyword":
                    continue
                k = {"name": kw.name, "line": kw.lineno, "documentation": "", "tags": [],
                     "arguments": [], "returns": [], "embedded_args": "${" in kw.name}
                parse_settings_block(kw.body, k)
                k["steps"] = collect_calls(kw.body)
                rec["keywords"].append(k)
    if kind == "suite" and not has_tests:
        rec["kind"] = "resource"   # .robot file used only as a keyword/resource file
    for err in getattr(model, "errors", []) or []:
        rec["errors"].append(str(err))
    return rec


# ---------------------------------------------------------------- python & data files
def parse_python_file(path, rel):
    rec = {"file": rel, "kind": "python", "keywords": [], "variables": [], "errors": []}
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="replace").read())
    except SyntaxError as e:
        rec["errors"].append(f"SyntaxError: {e}")
        return rec

    def kw_from_func(fn, cls=None):
        if fn.name.startswith("_"):
            return
        kname, explicit = fn.name.replace("_", " ").title(), False
        for d in fn.decorator_list:
            dn = d.func if isinstance(d, ast.Call) else d
            dname = getattr(dn, "id", None) or getattr(dn, "attr", None)
            if dname == "keyword":
                explicit = True
                if isinstance(d, ast.Call):
                    for a in d.args[:1]:
                        if isinstance(a, ast.Constant) and isinstance(a.value, str):
                            kname = a.value
                    for kwarg in d.keywords:
                        if kwarg.arg == "name" and isinstance(kwarg.value, ast.Constant):
                            kname = kwarg.value.value
        args = [a.arg for a in fn.args.args if a.arg != "self"]
        rec["keywords"].append({"name": kname, "line": fn.lineno, "arguments": args,
                                "class": cls, "decorated": explicit,
                                "documentation": mask(ast.get_docstring(fn) or "")})

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            kw_from_func(node)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    kw_from_func(item, node.name)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and not tgt.id.startswith("_"):
                    try:
                        val = ast.literal_eval(node.value)
                    except Exception:
                        val = "<dynamic>"
                    if isinstance(val, (str, int, float, bool)):
                        rec["variables"].append({"name": "${" + tgt.id + "}",
                            "value": mask(str(val), tgt.id), "line": node.lineno})
                    elif isinstance(val, dict):
                        rec["variables"].append({"name": "&{" + tgt.id + "}",
                            "value": {k: mask(str(v), str(k)) for k, v in val.items()},
                            "line": node.lineno})
                    elif isinstance(val, (list, tuple)):
                        rec["variables"].append({"name": "@{" + tgt.id + "}",
                            "value": [mask(str(v)) for v in val], "line": node.lineno})
    return rec


def parse_data_file(path, rel):
    rec = {"file": rel, "kind": "data", "keywords": [], "variables": [], "errors": []}
    try:
        if path.lower().endswith(".json"):
            data = json.load(open(path, encoding="utf-8"))
        else:
            import yaml  # optional
            data = yaml.safe_load(open(path, encoding="utf-8"))
    except ImportError:
        rec["errors"].append("PyYAML not installed; YAML variable file skipped")
        return rec
    except Exception as e:
        rec["errors"].append(f"{type(e).__name__}: {e}")
        return rec

    def walk(prefix, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(f"{prefix}.{k}" if prefix else str(k), v)
        elif isinstance(obj, (str, int, float, bool)):
            rec["variables"].append({"name": "${" + prefix + "}",
                                     "value": mask(str(obj), prefix), "line": None})
    walk("", data if isinstance(data, dict) else {})
    return rec


# ---------------------------------------------------------------- discovery
def discover(root, scopes, excludes):
    exts = (".robot", ".resource")  # python/yaml/json files are added only when imported
    targets = [os.path.join(root, s) for s in scopes] if scopes else [root]
    found = set()
    for t in targets:
        if os.path.isfile(t):
            found.add(os.path.abspath(t))
            continue
        if not os.path.isdir(t):
            print(f"WARNING: scope not found: {t}")
            continue
        for dirpath, dirnames, filenames in os.walk(t):
            dirnames[:] = [d for d in dirnames if d not in excludes and not d.startswith(".")]
            for fn in filenames:
                if fn.lower().endswith(exts):
                    found.add(os.path.abspath(os.path.join(dirpath, fn)))
    return found


def resolve_import(from_file, name, root):
    if "${" in name:
        return None
    cand = os.path.normpath(os.path.join(os.path.dirname(from_file), name))
    if os.path.isfile(cand):
        return cand
    cand = os.path.normpath(os.path.join(root, name))
    return cand if os.path.isfile(cand) else None


_PY_INDEX = None
KNOWN_LIBRARIES = {"browser", "seleniumlibrary", "builtin", "collections", "string",
                   "operatingsystem", "datetime", "process", "xml", "screenshot", "dialogs",
                   "telnet", "requestslibrary", "databaselibrary", "appiumlibrary"}


def find_python_library(name, root, excludes):
    """Find a repo-local Python library imported by module name (e.g. 'Library  CdrHelpers')."""
    global _PY_INDEX
    if "${" in name or "/" in name or "\\" in name or norm(name) in KNOWN_LIBRARIES:
        return None
    if _PY_INDEX is None:
        _PY_INDEX = {}
        skip = set(excludes) | {"site-packages", "dist-packages"}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
            for fn in filenames:
                if fn.endswith(".py"):
                    mod = os.path.basename(dirpath) if fn == "__init__.py" else fn[:-3]
                    _PY_INDEX.setdefault(mod, []).append(os.path.join(dirpath, fn))
    hits = _PY_INDEX.get(name.split(".")[-1], [])
    return os.path.abspath(hits[0]) if len(hits) == 1 else None


def expand_scope_with_imports(root, files, excludes):
    """Add resources / variable / python library files imported (transitively) by in-scope files."""
    queue, seen = list(files), set(files)
    while queue:
        f = queue.pop()
        if not f.lower().endswith((".robot", ".resource")):
            continue
        try:
            model = get_resource_model(f) if f.lower().endswith(".resource") else get_model(f)
        except Exception:
            continue
        for section in model.sections:
            if tname(section) != "SettingSection":
                continue
            for node in section.body:
                if tname(node) in ("ResourceImport", "VariablesImport", "LibraryImport"):
                    p = resolve_import(f, node.name, root)
                    if not p and tname(node) == "LibraryImport":
                        p = find_python_library(node.name, root, excludes)
                    if p and p not in seen:
                        seen.add(p)
                        queue.append(p)
    return seen
```

## Part 2 of 2

```python
# ---------------------------------------------------------------- relations helpers
# Run Keyword family: index of the argument that is itself a keyword name
RUN_KW_ARG = {"runkeyword": 0, "runkeywordandreturnstatus": 0, "runkeywordandignoreerror": 0,
              "runkeywordandcontinueonfailure": 0, "runkeywordandreturn": 0,
              "runkeywordandwarnonfailure": 0, "runkeywordif": 1, "runkeywordunless": 1,
              "runkeywordandexpecterror": 1, "runkeywordandreturnif": 1,
              "waituntilkeywordsucceeds": 2, "repeatkeyword": 1}
ROUTE_DEPTH = 3          # how deep to follow user keywords when computing prerequisites
UI_PATTERNS = {
    "frames": re.compile(r"select frame|unselect frame|>>>|iframe", re.I),
    "dialogs_alerts": re.compile(r"handle alert|handle future dialogs|alert should|dialog|modal|"
                                 r"popup|pop-up|confirm", re.I),
    "toasts_messages": re.compile(r"toast|snackbar|notification|banner|message", re.I),
    "loading_waits": re.compile(r"spinner|loader|loading|busy|progress|wait for load state|"
                                r"wait for response|wait for request|wait for condition|"
                                r"networkidle|network idle|wait until element is not visible", re.I),
    "windows_tabs": re.compile(r"switch window|switch page|switch browser|switch context|"
                               r"new page|new tab|close page|get window handles", re.I),
    "custom_dropdowns": re.compile(r"listbox|combobox|role=option|mui|lightning|"
                                   r"select options by|select from list|dropdown", re.I),
    "date_pickers": re.compile(r"date ?picker|calendar", re.I),
    "grids_tables": re.compile(r"grid|table|ag-|virtual|scroll", re.I),
    "shadow_dom": re.compile(r">>>|shadow", re.I),
    "sleep": re.compile(r"^\s*sleep\s*$", re.I),
}
MESSAGE_HINT = re.compile(r"\b(no|not|select|required|invalid|error|please|must|denied|"
                          r"unable|failed|warning|expired|unsaved|confirm)\b", re.I)
ASSERT_KWS = {"shouldcontain", "shouldbeequal", "shouldbeequalasstrings", "elementshouldcontain",
              "elementtextshouldbe", "pageshouldcontain", "waituntilpagecontains",
              "gettext", "alertshouldbepresent", "handlealert", "handlefuturedialogs"}


def call_names(step):
    """Keyword names a step really calls, including Run Keyword variants."""
    name, args = step["keyword"], step.get("args", []) or []
    n = norm(name.split(".")[-1])
    if n == "runkeywords":
        if "AND" not in [a.upper() for a in args]:
            return [name] + list(args)
        out, take = [name], True
        for a in args:
            if a.upper() == "AND":
                take = True
            elif take:
                out.append(a)
                take = False
        return out
    if n in ("runkeywordif", "runkeywordunless"):
        out = [name] + ([args[1]] if len(args) > 1 else [])
        for j, a in enumerate(args):
            if a == "ELSE" and j + 1 < len(args):
                out.append(args[j + 1])
            elif a == "ELSE IF" and j + 2 < len(args):
                out.append(args[j + 2])
        return out
    idx = RUN_KW_ARG.get(n)
    if idx is not None and len(args) > idx:
        return [name, args[idx]]
    return [name]


# ---------------------------------------------------------------- aggregation
def detect_library(rec):
    libs = {l["name"].split(".")[0] for l in rec.get("imports", {}).get("libraries", [])}
    if "Browser" in libs and "SeleniumLibrary" in libs:
        return "mixed"
    if "Browser" in libs:
        return "Browser"
    if "SeleniumLibrary" in libs:
        return "SeleniumLibrary"
    return None


def build_aggregates(records, out_dir, root):
    keywords, tests, locators, variables, libs = [], [], [], [], {}
    kw_index, init_settings = {}, {}
    for rec in records:
        lib = detect_library(rec) if rec["kind"] != "python" else None
        if lib:
            libs[rec["file"]] = lib
        if rec["kind"] == "init":
            init_settings[os.path.dirname(rec["file"])] = rec.get("settings", {})
        for k in rec.get("keywords", []):
            entry = dict(k, file=rec["file"], source_kind=rec["kind"])
            entry["calls"] = sorted({c for s in k.get("steps", []) for c in call_names(s)})
            keywords.append(entry)
            kw_index.setdefault(norm(k["name"]), []).append(entry)
        for t in rec.get("tests", []):
            steps = list(t.get("steps", []))
            tmpl = t.get("template") or (rec.get("settings", {}).get("TestTemplate") or {}).get("name")
            if tmpl and str(tmpl).upper() != "NONE":
                # data-driven test: the template keyword is the real step
                steps.append({"keyword": tmpl, "args": [], "line": t["line"],
                              "context": "TEMPLATE"})
            tests.append({"file": rec["file"], "name": t["name"], "line": t["line"],
                          "tags": t.get("tags", []), "documentation": t.get("documentation"),
                          "setup": t.get("setup"), "teardown": t.get("teardown"),
                          "template": t.get("template"),
                          "steps": [{"keyword": s["keyword"], "line": s["line"],
                                     "context": s["context"], "args": s["args"]}
                                    for s in steps],
                          "suite_settings": rec.get("settings", {})})
        for v in rec.get("variables", []):
            variables.append(dict(v, file=rec["file"]))
            val = v["value"] if isinstance(v["value"], str) else ""
            is_loc = bool(val) and len(val) < 400 and not SECRET_NAME.search(v["name"]) and (
                LOCATOR_VALUE.search(val) or (LOCATOR_NAME.search(v["name"]) and
                ("=" in val or val.startswith(("/", "#", ".", "[")))))
            if is_loc:
                locators.append({"variable": v["name"], "value": val, "file": rec["file"],
                                 "line": v["line"], "origin": "variable", "used_by": []})
    # embedded-argument keywords: match on normalised names (spaces, underscores, case ignored)
    embedded = []
    for k in keywords:
        if k.get("embedded_args"):
            parts = re.split(r"\$\{[^}]*\}", k["name"])
            pat = ".+?".join(re.escape(norm(p)) for p in parts)
            try:
                embedded.append((re.compile("^" + pat + "$"), k))
            except re.error:
                pass

    def resolve(call):
        hits = kw_index.get(norm(call))
        if not hits and "." in call:
            hits = kw_index.get(norm(call.split(".", 1)[1]))
        if hits:
            return hits
        n1 = norm(call)
        n2 = norm(call.split(".", 1)[1]) if "." in call else n1
        return [k for rx, k in embedded if rx.match(n1) or rx.match(n2)]

    loc_by_var = {norm(l["variable"].strip("${}@&")): l for l in locators}
    inline = []
    used_count = {}
    locator_kw_norm = {norm(x) for x in LOCATOR_KWS}

    def scan_steps(owner_type, owner_name, owner_file, steps):
        for s in steps:
            for c in call_names(s):
                for target in resolve(c):
                    key = (target["file"], target["name"])
                    used_count[key] = used_count.get(key, 0) + 1
            for a in s["args"]:
                for var in re.findall(r"[$@&]\{([^}]+)\}", a):
                    l = loc_by_var.get(norm(var))
                    if l is not None:
                        ref = f"{owner_type}:{owner_file}::{owner_name}"
                        if ref not in l["used_by"]:
                            l["used_by"].append(ref)
            if norm(s["keyword"].split(".")[-1]) in locator_kw_norm and s["args"]:
                first = s["args"][0]
                if "${" not in first and first.strip():
                    inline.append({"variable": None, "value": first, "file": owner_file,
                                   "line": s["line"], "origin": "inline",
                                   "used_by": [f"{owner_type}:{owner_file}::{owner_name}"]})

    for k in keywords:
        scan_steps("keyword", k["name"], k["file"], k.get("steps", []))
    for t in tests:
        scan_steps("test", t["name"], t["file"], t["steps"])
    # keywords used only as suite/test setup, teardown or template also count as used
    for rec in records:
        for key, val in (rec.get("settings") or {}).items():
            if isinstance(val, dict) and val.get("name") and str(val["name"]).upper() != "NONE":
                for target in resolve(val["name"]):
                    k2 = (target["file"], target["name"])
                    used_count[k2] = used_count.get(k2, 0) + 1
    for k in keywords:
        k["used_count"] = used_count.get((k["file"], k["name"]), 0)
        k["resolved_calls"] = {c: [f'{r["file"]}::{r["name"]}' for r in resolve(c)]
                               for c in k["calls"]}
    for t in tests:
        for s in t["steps"]:
            s["resolved"] = sorted({f'{r["file"]}::{r["name"]}'
                                    for c in call_names(s) for r in resolve(c)})

    # ---- relations: real entry routes and prerequisites, computed from every test
    def setup_steps(t):
        """Steps that run before the test body: __init__ suite setups, suite setup, test setup."""
        pre, d = [], os.path.dirname(t["file"])
        chain = []
        while True:
            if d in init_settings:
                chain.append(init_settings[d])
            if not d:
                break
            d = os.path.dirname(d)
        for st in reversed(chain):
            ss = st.get("SuiteSetup")
            if ss and ss.get("name") and ss["name"].upper() != "NONE":
                pre.append({"keyword": ss["name"], "args": ss.get("args", []),
                            "line": None, "context": "SUITE SETUP"})
        sset = t["suite_settings"]
        ss = sset.get("SuiteSetup")
        if ss and ss.get("name") and ss["name"].upper() != "NONE":
            pre.append({"keyword": ss["name"], "args": ss.get("args", []),
                        "line": None, "context": "SUITE SETUP"})
        has_own = any(s.get("context") == "SETUP" for s in t["steps"])
        ts = sset.get("TestSetup")
        if not has_own and ts and ts.get("name") and ts["name"].upper() != "NONE":
            pre.append({"keyword": ts["name"], "args": ts.get("args", []),
                        "line": None, "context": "TEST SETUP"})
        return pre

    def token_for(step, call, depth):
        if not call or call.upper() == "NONE":
            return None, None          # [Setup]  NONE disables a setup; not a step
        hits = resolve(call)
        if hits:
            return f'{hits[0]["file"]}::{hits[0]["name"]}', hits[0]
        n = norm(call.split(".")[-1])
        if n in RUN_KW_ARG or n == "runkeywords":
            return None, None          # the wrapper itself is not a navigation step
        if depth == 0 and call == step["keyword"]:
            first = (step.get("args") or [""])[0]
            return f'lib:{step["keyword"]} {first}'.strip(), None
        return None, None

    def expand(steps, depth, seen, top_idx, out):
        for i, s in enumerate(steps):
            if s.get("context") == "TEARDOWN":
                continue
            ti = i if top_idx is None else top_idx
            for c in call_names(s):
                tok, kw = token_for(s, c, depth)
                if not tok:
                    continue
                out.append((tok, ti))
                if kw and depth < ROUTE_DEPTH and tok not in seen and len(out) < 400:
                    expand(kw.get("steps", []), depth + 1, seen | {tok}, ti, out)
        return out

    order_ref, before_sets, examples, tok_tests = {}, {}, {}, {}
    for t in tests:
        top = setup_steps(t) + [s for s in t["steps"] if s.get("context") != "TEARDOWN"]
        seq = expand(top, 0, frozenset(), None, [])
        tref = f'{t["file"]}::{t["name"]}'
        seen_here = set()
        for pos, (tok, ti) in enumerate(seq):
            if tok in seen_here:
                continue
            seen_here.add(tok)
            prior = list(dict.fromkeys(x for x, _ in seq[:pos] if x != tok))
            before_sets[tok] = (set(prior) if tok not in before_sets
                                else before_sets[tok] & set(prior))
            order_ref.setdefault(tok, {x: i for i, x in enumerate(prior)})
            route = [f'{s["keyword"]}    {"    ".join(s.get("args", [])[:2])}'.strip()
                     for s in top[:ti + 1]]
            ex = examples.setdefault(tok, {})
            key = " > ".join(route)
            if key not in ex and len(ex) < 3:
                ex[key] = {"source_test": tref, "route": route}
        for tok in seen_here:
            tok_tests[tok] = tok_tests.get(tok, 0) + 1
    routes = {}
    for tok, req in before_sets.items():
        order = order_ref.get(tok, {})
        routes[tok] = {
            "tests_using": tok_tests.get(tok, 0),
            "always_before": sorted(req, key=lambda x: order.get(x, 0)),
            "example_routes": sorted(examples.get(tok, {}).values(),
                                     key=lambda e: len(e["route"]))}

    # ---- UI patterns and on-screen messages actually handled by the tests
    ui = {name: {"count": 0, "examples": []} for name in UI_PATTERNS}
    messages = []

    def note(text, where):
        for name, rx in UI_PATTERNS.items():
            if text and rx.search(text):
                ui[name]["count"] += 1
                if len(ui[name]["examples"]) < 5:
                    ui[name]["examples"].append(where)

    for owner in [(k["file"], k.get("steps", [])) for k in keywords] + \
                 [(t["file"], t["steps"]) for t in tests]:
        f, steps = owner
        for s in steps:
            where = f'{f}:{s.get("line")}'
            note(s["keyword"], where)
            for a in s.get("args", [])[:2]:
                note(a, where)
            if norm(s["keyword"].split(".")[-1]) in ASSERT_KWS or "text=" in " ".join(s["args"]):
                for a in s.get("args", []):
                    txt = a.split("text=", 1)[-1] if "text=" in a else a
                    if "${" not in txt and MESSAGE_HINT.search(txt) and len(messages) < 300:
                        messages.append({"text": mask(txt), "keyword": s["keyword"],
                                         "where": where})
    for l in locators:
        note(l["value"], f'{l["file"]}:{l["line"]}')

    dupes = {}
    for l in locators:
        dupes.setdefault(l["value"].strip(), []).append(f'{l["file"]}::{l["variable"]}')
    duplicates = {k: v for k, v in dupes.items() if len(v) > 1}
    unresolved = sorted({c for t in tests for s in t["steps"] if not s["resolved"]
                         for c in call_names(s) if c.upper() != "NONE"}
                        | {c for k in keywords for c, r in k["resolved_calls"].items() if not r})

    def dump(name, obj):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, ensure_ascii=False)

    dump("tests.json", tests)
    dump("keywords.json", keywords)
    dump("locators.json", locators + inline)
    dump("variables.json", variables)
    dump("routes.json", routes)
    dump("ui-signals.json", {"patterns": ui, "messages": messages})
    summary = {"schema_version": SCHEMA_VERSION, "rf_version": RF_VERSION,
               "generated_at": datetime.now(timezone.utc).isoformat(),
               "counts": {"files": len(records), "tests": len(tests),
                          "user_keywords": len(keywords),
                          "locator_variables": len(locators), "inline_locators": len(inline),
                          "variables": len(variables),
                          "route_entries": len(routes), "ui_messages": len(messages),
                          "duplicate_locator_values": len(duplicates),
                          "unresolved_calls": len(unresolved)},
               "libraries_per_file": libs,
               "ui_patterns_detected": {k: v["count"] for k, v in ui.items() if v["count"]},
               "test_organisation": ("one-test-per-file"
                                     if tests and all(sum(1 for t in tests if t["file"] == f) == 1
                                                      for f in {t["file"] for t in tests})
                                     else "many-tests-per-suite" if tests else "unknown"),
               "duplicate_locator_values": duplicates,
               "unresolved_calls_sample": unresolved[:200],
               "parse_errors": {r["file"]: r["errors"] for r in records if r.get("errors")}}
    dump("summary.json", summary)
    return summary


# ---------------------------------------------------------------- main
def git_commit(root):
    try:
        import subprocess
        return subprocess.run(["git", "-C", root, "rev-parse", "HEAD"], capture_output=True,
                              text=True, timeout=10).stdout.strip() or None
    except Exception:
        return None


def run(root, scopes, out_dir, full, extra_excludes):
    root = os.path.abspath(root)
    out_dir = os.path.abspath(os.path.join(root, out_dir))
    files_dir = os.path.join(out_dir, "files")
    os.makedirs(files_dir, exist_ok=True)
    excludes = DEFAULT_EXCLUDES | set(extra_excludes or [])
    cache_path = os.path.join(out_dir, "cache.json")
    cache = {}
    if not full and os.path.exists(cache_path):
        try:
            cache = json.load(open(cache_path, encoding="utf-8"))
        except Exception:
            cache = {}          # damaged cache (e.g. an earlier run was interrupted): rebuild

    files = discover(root, scopes, excludes)
    # scoped runs: include __init__.robot files of parent folders (suite setups such as login)
    for f in list(files):
        d = os.path.dirname(f)
        while d.startswith(root):
            init = os.path.join(d, "__init__.robot")
            if os.path.isfile(init):
                files.add(init)
            nd = os.path.dirname(d)
            if d == root or nd == d:
                break
            d = nd
    # follow Resource / Variables / Library(path) imports so scoped runs stay complete and
    # python or yaml/json files are included only when the test code actually imports them
    files = expand_scope_with_imports(root, files, excludes)
    records, changed, reused = [], 0, 0
    for path in sorted(files):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if any(part in excludes for part in rel.split("/")[:-1]):
            continue
        digest = sha256(path)
        rec_file = os.path.join(files_dir, re.sub(r"[^\w.-]", "_", rel) + ".json")
        if cache.get(rel) == digest and os.path.exists(rec_file):
            try:
                records.append(json.load(open(rec_file, encoding="utf-8")))
                reused += 1
                continue
            except Exception:
                pass            # damaged cached record: parse the file again
        try:
            low = path.lower()
            if low.endswith((".robot", ".resource")):
                rec = parse_robot_file(path, rel)
            elif low.endswith(".py"):
                rec = parse_python_file(path, rel)
            else:
                rec = parse_data_file(path, rel)
        except Exception as e:
            rec = {"file": rel, "kind": "error", "keywords": [], "variables": [],
                   "errors": [f"{type(e).__name__}: {e}"]}
        rec["sha256"] = digest
        with open(rec_file, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1, ensure_ascii=False)
        cache[rel] = digest
        records.append(rec)
        changed += 1
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)
    summary = build_aggregates(records, out_dir, root)
    summary.update({"root": root, "scope": scopes or ["<whole repo>"],
                    "git_commit": git_commit(root),
                    "files_parsed": changed, "files_reused_from_cache": reused})
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)
    c = summary["counts"]
    print(f"Extract complete -> {out_dir}")
    print(f"  files: {c['files']} (parsed {changed}, reused {reused})")
    print(f"  tests: {c['tests']}  user keywords: {c['user_keywords']}  "
          f"locator variables: {c['locator_variables']}  inline locators: {c['inline_locators']}")
    print(f"  duplicate locator values: {c['duplicate_locator_values']}  "
          f"unresolved keyword calls: {c['unresolved_calls']} (library keywords are expected here)")
    print(f"  route entries: {c['route_entries']}  on-screen messages found: {c['ui_messages']}  "
          f"UI patterns: {', '.join(summary['ui_patterns_detected']) or 'none'}")
    if summary["parse_errors"]:
        print(f"  files with parse warnings: {len(summary['parse_errors'])} (see summary.json)")
    return summary


SAMPLE = {
 "tests/cross_reference.robot": """*** Settings ***
Documentation    Cross reference tests
Library          Browser
Resource         ../resources/common.resource
Resource         ../resources/xref.resource
Test Setup       Login To Portal    ${USER}    ${PASSWORD}
Test Tags        xref

*** Test Cases ***
Verify Cross Reference Type Available
    [Documentation]    TC-1001 type is listed
    [Tags]    TC-1001    smoke
    Open Client    ${CLIENT_ID}
    Navigate To Cross Reference Tab
    FOR    ${t}    IN    ABCD    EFGH
        Cross Reference Type Should Exist    ${t}
    END

Add Cross Reference
    [Tags]    TC-1002
    Open Client    ${CLIENT_ID}
    Run Keyword    Navigate To Cross Reference Tab
    Click    ${XREF_ADD_BTN}
    Click    css=#save
""",
 "resources/common.resource": """*** Settings ***
Library    Browser

*** Variables ***
${USER}          qa_user
${PASSWORD}      SuperSecret1
${LOGIN_BTN}     id=login
${CLIENT_ID}     1234567

*** Keywords ***
Login To Portal
    [Arguments]    ${user}    ${pwd}
    Fill Text    id=username    ${user}
    Fill Secret    id=password    $pwd
    Click    ${LOGIN_BTN}

Open Client
    [Arguments]    ${client}
    Fill Text    css=#search    ${client}
    Click    text=Open
""",
 "resources/xref.resource": """*** Settings ***
Library    Browser

*** Variables ***
${XREF_TAB}         css=[data-testid="xref-tab"]
${XREF_ADD_BTN}     xpath=//button[text()="Add"]
${XREF_TYPE_DDL}    id=xrefType

*** Keywords ***
Navigate To Cross Reference Tab
    Click    ${XREF_TAB}

Cross Reference Type Should Exist
    [Arguments]    ${type}
    Click    ${XREF_ADD_BTN}
    ${opts}=    Get Text    ${XREF_TYPE_DDL}
    Should Contain    ${opts}    ${type}
"""}


def self_test():
    tmp = tempfile.mkdtemp(prefix="extract_selftest_")
    try:
        for rel, content in SAMPLE.items():
            p = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w", encoding="utf-8").write(content)
        s = run(tmp, ["tests/cross_reference.robot"], "knowledge/.extract", True, [])
        c = s["counts"]
        out = os.path.join(tmp, "knowledge/.extract")
        kws = json.load(open(os.path.join(out, "keywords.json")))
        locs = json.load(open(os.path.join(out, "locators.json")))
        vars_ = json.load(open(os.path.join(out, "variables.json")))
        routes = json.load(open(os.path.join(out, "routes.json")))
        nav = routes.get("resources/xref.resource::Navigate To Cross Reference Tab", {})
        checks = {
            "2 tests found": c["tests"] == 2,
            "4 user keywords found": c["user_keywords"] == 4,
            "keyword call resolved": any(k["name"] == "Open Client" and k["used_count"] >= 2
                                         for k in kws),
            "locator variables found (>=4)": c["locator_variables"] >= 4,
            "inline locator found": c["inline_locators"] >= 1,
            "locator usage linked": any(l.get("variable") == "${XREF_ADD_BTN}" and l["used_by"]
                                        for l in locs),
            "password masked": all(v["value"] == "***MASKED***" for v in vars_
                                   if v["name"] == "${PASSWORD}"),
            "long id masked": all("1234567" not in str(v["value"]) for v in vars_),
            "Browser detected": "Browser" in s["libraries_per_file"].values(),
            "prerequisite found (open client before tab)":
                "resources/common.resource::Open Client" in nav.get("always_before", []),
            "setup in route (login before tab)":
                "resources/common.resource::Login To Portal" in nav.get("always_before", []),
            "Run Keyword target resolved": any(k["name"] == "Navigate To Cross Reference Tab"
                                               and k["used_count"] >= 2 for k in kws),
            "FOR loop steps captured": any(st["context"] and st["context"].startswith("FOR")
                                           for t in json.load(open(os.path.join(out, "tests.json")))
                                           for st in t["steps"]),
        }
        ok = all(checks.values())
        print("\nSELF-TEST " + ("PASSED" if ok else "FAILED") + f" (Robot Framework {RF_VERSION})")
        for name, passed in checks.items():
            print(f"  [{'OK' if passed else 'FAIL'}] {name}")
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--root", default=".", help="repository root (default: current folder)")
    ap.add_argument("--scope", action="append", default=[],
                    help="file or folder to limit extraction (repeatable); imports are followed")
    ap.add_argument("--out", default="knowledge/.extract", help="output folder relative to root")
    ap.add_argument("--full", action="store_true", help="ignore cache and re-parse everything")
    ap.add_argument("--exclude", action="append", default=[], help="extra folder names to skip")
    ap.add_argument("--self-test", action="store_true", help="run built-in verification and exit")
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    run(a.root, a.scope, a.out, a.full, a.exclude)


if __name__ == "__main__":
    main()
```
