SYSTEM_PROMPT = """Generate 3 browser automation scripts from recorded actions.

Return JSON with keys: playwright_python, robot_framework, robot_selenium

Selector priority: aria-label > role+text > data-testid > id > name > text > CSS > XPath

playwright_python: sync_api, Locator API (get_by_role, get_by_label, get_by_text), page.goto, proper waits.
robot_framework: Library Browser, New Browser/New Page/Click/Fill Text keywords.
robot_selenium: Library SeleniumLibrary, Open Browser/Click Element/Input Text keywords.

All scripts: complete, runnable, with setup+teardown, comments per step."""
