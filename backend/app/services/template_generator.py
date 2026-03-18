import logging
from typing import List, Optional

from app.models.actions import ProcessedAction, ElementContext
from app.models.scripts import ScriptOutput

logger = logging.getLogger(__name__)

TAG_TO_ROLE = {
    "a": "link", "button": "button", "input": "textbox",
    "textarea": "textbox", "select": "combobox", "img": "img",
    "h1": "heading", "h2": "heading", "h3": "heading",
    "h4": "heading", "h5": "heading", "h6": "heading",
}


def _esc(v: str) -> str:
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _role(el: ElementContext) -> str:
    return el.role or TAG_TO_ROLE.get((el.tag or "").lower(), "")


def _name(el: ElementContext) -> str:
    return el.aria_label or el.text_content or ""


def _is_clean_css(sel: str) -> bool:
    """Return True if the CSS selector is human-readable (no nth-child, no positional)."""
    if not sel:
        return False
    bad = ["nth-child", "nth-of-type", ":nth-", " > ", " + "]
    return not any(b in sel for b in bad)


# =====================================================================
# Playwright Python locators
# Strategy order matches the spec priority exactly.
# NEVER generates nth-child or positional CSS selectors.
# =====================================================================

def _pw_locator(el: Optional[ElementContext]) -> str:
    if el is None:
        return 'page.locator("body")'

    s = el.locator_strategy or "css"

    # P1: Testing data attributes
    if s == "data_testid":
        return f'page.get_by_test_id("{_esc(el.data_testid)}")'
    if s == "data_cy":
        return f'page.locator("[data-cy=\\"{_esc(el.data_cy)}\\"]")'
    if s == "data_qa":
        return f'page.locator("[data-qa=\\"{_esc(el.data_qa)}\\"]")'
    if s == "data_id":
        return f'page.locator("[data-id=\\"{_esc(el.data_id)}\\"]")'

    # P2: aria-label
    if s == "aria_label":
        role = _role(el)
        if role:
            return f'page.get_by_role("{role}", name="{_esc(el.aria_label)}", exact=True)'
        return f'page.get_by_label("{_esc(el.aria_label)}", exact=True)'

    # P3: role + name (globally unique)
    if s == "role_name":
        return f'page.get_by_role("{_role(el)}", name="{_esc(_name(el))}", exact=True)'
    if s == "role_name_scoped" and el.container_css:
        return f'page.locator("{_esc(el.container_css)}").get_by_role("{_role(el)}", name="{_esc(_name(el))}", exact=True)'

    # P3b: role + name, not globally unique — use .first to avoid strict mode
    if s == "role_name_first":
        return f'page.get_by_role("{_role(el)}", name="{_esc(_name(el))}", exact=True).first'

    # P4: id (stable)
    if s == "id":
        return f'page.locator("#{_esc(el.id)}")'

    # P5: name attribute
    if s == "name":
        return f'page.locator("[name=\\"{_esc(el.name)}\\"]")'

    # P6: placeholder
    if s == "placeholder":
        return f'page.get_by_placeholder("{_esc(el.placeholder)}", exact=True)'

    # P7: visible text exact match
    if s == "text":
        return f'page.get_by_text("{_esc(el.text_content)}", exact=True)'

    # P8: href (unique link)
    if s == "href":
        return f'page.locator("a[href=\\"{_esc(el.href)}\\"]")'

    # --- Semantic fallback: prefer role+name with .first over positional CSS ---
    role = _role(el)
    name = _name(el)
    if role and name:
        return f'page.get_by_role("{role}", name="{_esc(name)}", exact=True).first'
    if el.text_content:
        return f'page.get_by_text("{_esc(el.text_content)}", exact=True).first'

    # P9: CSS selector ONLY if clean (no nth-child/positional)
    if el.css_selector and _is_clean_css(el.css_selector):
        return f'page.locator("{_esc(el.css_selector)}")'

    # P10: XPath last resort
    if el.xpath:
        return f'page.locator("xpath={_esc(el.xpath)}")'

    return 'page.locator("body")'


def _generate_playwright(actions: List[ProcessedAction], url: str) -> str:
    lines = [
        "from playwright.sync_api import sync_playwright",
        "",
        "",
        "def main():",
        "    with sync_playwright() as p:",
        "        browser = p.chromium.launch(headless=False)",
        "        page = browser.new_page()",
        "        try:",
        f'            page.goto("{_esc(url)}")',
        '            page.wait_for_load_state("networkidle")',
        "",
    ]

    step = 0
    for action in actions:
        # Skip wait actions — we use wait_for_load_state after clicks instead
        if action.action_type == "wait":
            continue

        step += 1
        lines.append(f"            # Step {step}: {action.description}")

        if action.action_type == "navigate" and action.url:
            lines.append(f'            page.goto("{_esc(action.url)}")')
            lines.append('            page.wait_for_load_state("networkidle")')
        elif action.action_type == "click":
            lines.append(f"            {_pw_locator(action.element)}.click()")
            lines.append('            page.wait_for_load_state("networkidle")')
        elif action.action_type == "dblclick":
            lines.append(f"            {_pw_locator(action.element)}.dblclick()")
        elif action.action_type == "type":
            loc = _pw_locator(action.element)
            lines.append(f"            {loc}.click()")
            lines.append(f'            {loc}.fill("{_esc(action.value or "")}")')
        elif action.action_type == "keypress":
            lines.append(f'            page.keyboard.press("{action.value or "Enter"}")')
        elif action.action_type == "scroll":
            lines.append("            page.mouse.wheel(0, 300)")

        lines.append("")

    lines += [
        "        finally:",
        "            browser.close()",
        "",
        "",
        'if __name__ == "__main__":',
        "    main()",
        "",
    ]
    return "\n".join(lines)


# =====================================================================
# Robot Framework (Browser library)
# =====================================================================

def _rf_selector(el: Optional[ElementContext]) -> str:
    if el is None:
        return "body"
    s = el.locator_strategy or "css"

    if s == "data_testid":
        return f'[data-testid="{_esc(el.data_testid)}"]'
    if s == "data_cy":
        return f'[data-cy="{_esc(el.data_cy)}"]'
    if s == "data_qa":
        return f'[data-qa="{_esc(el.data_qa)}"]'
    if s == "data_id":
        return f'[data-id="{_esc(el.data_id)}"]'
    if s == "aria_label":
        return f'[aria-label="{_esc(el.aria_label)}"]'
    if s == "role_name":
        return f'role={_role(el)}[name="{_esc(_name(el))}"]'
    if s == "role_name_scoped" and el.container_css:
        return f'{el.container_css} >> role={_role(el)}[name="{_esc(_name(el))}"]'
    if s == "role_name_first":
        return f'role={_role(el)}[name="{_esc(_name(el))}"] >> nth=0'
    if s == "id":
        return f"#{_esc(el.id)}"
    if s == "name":
        return f'[name="{_esc(el.name)}"]'
    if s == "placeholder":
        return f'[placeholder="{_esc(el.placeholder)}"]'
    if s == "text":
        return f'text="{_esc(el.text_content)}"'
    if s == "href":
        return f'a[href="{_esc(el.href)}"]'

    # Semantic fallback
    role = _role(el)
    name = _name(el)
    if role and name:
        return f'role={role}[name="{_esc(name)}"] >> nth=0'
    if el.text_content:
        return f'text="{_esc(el.text_content)}"'
    if el.css_selector and _is_clean_css(el.css_selector):
        return el.css_selector
    if el.xpath:
        return f"xpath={el.xpath}"
    return "body"


def _generate_robot_framework(actions: List[ProcessedAction], url: str) -> str:
    lines = [
        "*** Settings ***",
        "Library    Browser",
        "",
        "*** Test Cases ***",
        "Recorded Test",
        "    New Browser    chromium    headless=false",
        "    New Page    " + url,
        "    Wait For Load State    networkidle",
        "",
    ]

    step = 0
    for action in actions:
        if action.action_type == "wait":
            continue

        step += 1
        lines.append(f"    # Step {step}: {action.description}")

        if action.action_type == "navigate" and action.url:
            lines.append(f"    Go To    {action.url}")
            lines.append("    Wait For Load State    networkidle")
        elif action.action_type == "click":
            lines.append(f"    Click    {_rf_selector(action.element)}")
            lines.append("    Wait For Load State    networkidle")
        elif action.action_type == "dblclick":
            lines.append(f"    Click    {_rf_selector(action.element)}    clickCount=2")
        elif action.action_type == "type":
            sel = _rf_selector(action.element)
            lines.append(f"    Click    {sel}")
            lines.append(f"    Fill Text    {sel}    {action.value or ''}")
        elif action.action_type == "keypress":
            lines.append(f"    Keyboard Key    press    {action.value or 'Enter'}")
        elif action.action_type == "scroll":
            lines.append("    Scroll By    0    300")

        lines.append("")

    lines += ["    # Teardown", "    Close Browser", ""]
    return "\n".join(lines)


# =====================================================================
# Robot Framework + SeleniumLibrary
# =====================================================================

FORM_TAGS = {"input", "textarea", "select"}


def _selenium_form_locator(el: ElementContext, name: str) -> str:
    """Build a SeleniumLibrary locator for form elements (input/textarea/select).

    Form elements have no text content, so normalize-space() won't work.
    Instead, use the element's own attributes or its associated <label>.
    """
    tag = (el.tag or "input").lower()
    if el.aria_label:
        return f'xpath://{tag}[@aria-label="{_esc(el.aria_label)}"]'
    if el.placeholder:
        return f'css:{tag}[placeholder="{_esc(el.placeholder)}"]'
    if el.name:
        return f"name:{el.name}"
    if el.id:
        return f"id:{el.id}"
    # Find by associated <label> text
    return f'xpath://label[normalize-space()="{_esc(name)}"]/following::{tag}[1]'


def _rf_selenium_locator(el: Optional[ElementContext]) -> str:
    if el is None:
        return "css:body"
    s = el.locator_strategy or "css"
    tag = (el.tag or "*").lower()
    is_form = tag in FORM_TAGS

    if s == "data_testid":
        return f'css:[data-testid="{_esc(el.data_testid)}"]'
    if s == "data_cy":
        return f'css:[data-cy="{_esc(el.data_cy)}"]'
    if s == "data_qa":
        return f'css:[data-qa="{_esc(el.data_qa)}"]'
    if s == "data_id":
        return f'css:[data-id="{_esc(el.data_id)}"]'
    if s == "aria_label":
        return f'css:[aria-label="{_esc(el.aria_label)}"]'
    if s in ("role_name", "role_name_first"):
        name = _name(el)
        if is_form:
            return _selenium_form_locator(el, name)
        if el.aria_label:
            return f'xpath://{tag}[@aria-label="{_esc(el.aria_label)}"]'
        return f'xpath://{tag}[normalize-space()="{_esc(name)}"]'
    if s == "role_name_scoped" and el.container_css:
        name = _name(el)
        if is_form:
            return _selenium_form_locator(el, name)
        container_tag = el.container_css.split('.')[0].split('#')[0].split('[')[0]
        return f'xpath://{container_tag or "*"}//{tag}[normalize-space()="{_esc(name)}"]'
    if s == "id":
        return f"id:{el.id}"
    if s == "name":
        return f"name:{el.name}"
    if s == "placeholder":
        return f'css:{tag}[placeholder="{_esc(el.placeholder)}"]'
    if s == "text":
        if is_form:
            return _selenium_form_locator(el, el.text_content or "")
        return f'xpath://{tag}[normalize-space()="{_esc(el.text_content)}"]'
    if s == "href":
        return f'css:a[href="{_esc(el.href)}"]'

    # Semantic fallback
    role = _role(el)
    name = _name(el)
    if role and name:
        if is_form:
            return _selenium_form_locator(el, name)
        return f'xpath://{tag}[normalize-space()="{_esc(name)}"]'
    if el.text_content:
        if is_form:
            return _selenium_form_locator(el, el.text_content)
        return f'xpath://{tag}[normalize-space()="{_esc(el.text_content)}"]'
    if el.css_selector and _is_clean_css(el.css_selector):
        return f"css:{el.css_selector}"
    if el.xpath:
        return f"xpath:{el.xpath}"
    return "css:body"


def _generate_robot_selenium(actions: List[ProcessedAction], url: str) -> str:
    KEY_MAP = {
        "Enter": "ENTER", "Tab": "TAB", "Escape": "ESCAPE",
        "Backspace": "BACKSPACE", "Delete": "DELETE",
        "ArrowUp": "ARROW_UP", "ArrowDown": "ARROW_DOWN",
        "ArrowLeft": "ARROW_LEFT", "ArrowRight": "ARROW_RIGHT",
    }
    lines = [
        "*** Settings ***",
        "Library    SeleniumLibrary",
        "",
        "*** Test Cases ***",
        "Recorded Test",
        f"    Open Browser    {url}    chrome",
        "    Maximize Browser Window",
        "",
    ]

    step = 0
    for action in actions:
        if action.action_type == "wait":
            continue

        step += 1
        lines.append(f"    # Step {step}: {action.description}")

        if action.action_type == "navigate" and action.url:
            lines.append(f"    Go To    {action.url}")
        elif action.action_type == "click":
            loc = _rf_selenium_locator(action.element)
            lines.append(f"    Wait Until Element Is Visible    {loc}")
            lines.append(f"    Click Element    {loc}")
        elif action.action_type == "dblclick":
            loc = _rf_selenium_locator(action.element)
            lines.append(f"    Wait Until Element Is Visible    {loc}")
            lines.append(f"    Double Click Element    {loc}")
        elif action.action_type == "type":
            loc = _rf_selenium_locator(action.element)
            lines.append(f"    Wait Until Element Is Visible    {loc}")
            lines.append(f"    Click Element    {loc}")
            lines.append(f"    Input Text    {loc}    {action.value or ''}")
        elif action.action_type == "keypress":
            lines.append(f"    Press Keys    None    {KEY_MAP.get(action.value or 'Enter', action.value or 'ENTER')}")
        elif action.action_type == "scroll":
            lines.append("    Execute JavaScript    window.scrollBy(0, 300)")

        lines.append("")

    lines += ["    # Teardown", "    Close All Browsers", ""]
    return "\n".join(lines)


# =====================================================================
# Public API
# =====================================================================

class TemplateGenerator:
    """Generates automation scripts from processed actions using templates (no AI)."""

    def generate(self, actions: List[ProcessedAction], url: str) -> ScriptOutput:
        logger.info(f"Template-generating scripts for {len(actions)} actions at {url}")
        return ScriptOutput(
            playwright_python=_generate_playwright(actions, url),
            robot_framework=_generate_robot_framework(actions, url),
            robot_selenium=_generate_robot_selenium(actions, url),
        )
