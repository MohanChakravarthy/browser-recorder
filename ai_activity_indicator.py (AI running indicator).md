# ai\_activity\_indicator.py (AI running indicator)

Save as `skills/ai_activity_indicator.py`. Copy only the code inside the grey box. The robot-script-generator finds it by name anywhere under `skills/` and adds it only to its own runs. Never add it to test suites or CI pipelines. Colours: RBC blue (#005DAA) border and badge with a light blue glow.

```python
"""
ai_activity_indicator.py - shows a soft blue "AI running" border in the browser while the AI runs a test.

Optional, visual only. Used by robot-script-generator for its own headed runs:
    robot --listener skills/ai_activity_indicator.py ... ai_generated_tests/<module>/<file>.robot
Never add this to test code, suites or CI pipelines. Normal runs are unaffected.

Safe by design:
- The overlay ignores the mouse (pointer-events: none), so it never blocks clicks.
- Its label sits in a closed shadow root, so text locators and "Page Should Contain" never see it.
- Styles are set from script (no <style> tag), so strict Content-Security-Policy pages still work.
- Re-applied after each browser keyword, because page navigation removes it.
- Every error is swallowed: the indicator can never fail or slow down a test noticeably.
Colours: RBC blue (#005DAA) border with a light blue glow.
Works with the Browser library (Playwright) and SeleniumLibrary. Robot Framework 4+.
"""

ROBOT_LISTENER_API_VERSION = 2

INDICATOR_JS = r"""() => {
  if (document.getElementById('ai-activity-indicator')) return;
  const root = document.documentElement;
  if (!root) return;
  const d = document.createElement('div');
  d.id = 'ai-activity-indicator';
  d.setAttribute('aria-hidden', 'true');
  Object.assign(d.style, {position: 'fixed', top: '0', left: '0', right: '0', bottom: '0',
    pointerEvents: 'none', zIndex: '2147483647', borderRadius: '6px',
    boxShadow: 'inset 0 0 0 3px rgba(0,93,170,0.9), inset 0 0 28px 6px rgba(102,178,255,0.55)'});
  const sr = d.attachShadow({mode: 'closed'});
  const b = document.createElement('span');
  b.textContent = 'AI running';
  Object.assign(b.style, {position: 'absolute', top: '8px', right: '12px',
    font: '600 12px/1 Segoe UI, Arial, sans-serif', color: '#fff',
    background: 'rgba(0,93,170,0.9)', padding: '5px 9px', borderRadius: '10px'});
  sr.appendChild(b);
  root.appendChild(d);
  if (d.animate) {
    d.animate([
      {boxShadow: 'inset 0 0 0 2px rgba(0,93,170,0.6), inset 0 0 14px 2px rgba(102,178,255,0.35)'},
      {boxShadow: 'inset 0 0 0 4px rgba(0,93,170,1), inset 0 0 40px 10px rgba(102,178,255,0.75)'}
    ], {duration: 1600, iterations: Infinity, direction: 'alternate', easing: 'ease-in-out'});
  }
}"""

_busy = False


def _library(class_name):
    try:
        from robot.libraries.BuiltIn import BuiltIn
        libs = BuiltIn().get_library_instance(all=True)
    except Exception:
        return None
    for lib in libs.values():
        if type(lib).__name__ == class_name:
            return lib
    return None


def _show(libname):
    global _busy
    if _busy:
        return
    _busy = True
    try:
        if libname == "Browser":
            lib = _library("Browser")
            if lib is not None:
                lib.evaluate_javascript(None, INDICATOR_JS)
        elif libname == "SeleniumLibrary":
            lib = _library("SeleniumLibrary")
            if lib is not None:
                lib.driver.execute_script("(" + INDICATOR_JS + ")();")
    except Exception:
        pass  # no page yet, page navigating, browser closed: ignore
    finally:
        _busy = False


def end_keyword(name, attrs):
    libname = attrs.get("libname")
    if libname in ("Browser", "SeleniumLibrary"):
        low = (attrs.get("kwname") or name or "").lower()
        if "close" in low:
            return
        _show(libname)
```

## How to check it once

Run any existing headed test with the listener added, for example:

`robot --listener skills/ai_activity_indicator.py --test "<test name>" --variable HEADLESS:false <suite file>`

You should see a pulsing RBC-blue border with a light blue glow and an "AI running" badge at the top right. The test result must be the same as without it. If the border does not appear, the test is unaffected; tell me what you see.

Note: screenshots taken during AI runs will show the border. Runs without `--listener` never show it.
