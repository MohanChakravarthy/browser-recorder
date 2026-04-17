# save_session.py
from playwright.sync_api import sync_playwright

PORTAL_URL = "https://your-portal-url.com"  # CHANGE THIS
SESSION_FILE = "auth_state.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        print(f"\n>>> Opening {PORTAL_URL}")
        print(">>> Steps to complete in the browser:")
        print("    1. Click 'Continue to SSO Login'")
        print("    2. Complete Microsoft login (email, password, MFA)")
        print("    3. Wait until you land on the portal dashboard")
        print(">>> Then come back here and press ENTER\n")

        page.goto(PORTAL_URL)

        input("Press ENTER after you've fully logged in and see the portal dashboard...")

        context.storage_state(path=SESSION_FILE)
        print(f"\n✓ Session saved to {SESSION_FILE}")

        browser.close()

if __name__ == "__main__":
    main()




# crawl_page.py
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

SESSION_FILE = "auth_state.json"
OUTPUT_DIR = Path("snapshot_store")
OUTPUT_DIR.mkdir(exist_ok=True)

# CHANGE these two for each page you want to capture
PAGE_URL = "https://your-portal-url.com/some-page"
PAGE_NAME = "SomePage"

EXTRACT_SCRIPT = """
() => {
  const fields = document.querySelectorAll('input, select, textarea');
  const buttons = document.querySelectorAll('button, input[type=submit], input[type=button]');

  const fieldData = Array.from(fields)
    .filter(el => el.type !== 'hidden')
    .map(el => ({
      name: el.name || el.id || '',
      label: el.labels && el.labels[0] ? el.labels[0].innerText : '',
      type: el.type || el.tagName.toLowerCase(),
      required: el.required || false,
      max_length: el.maxLength > 0 ? el.maxLength : null,
      placeholder: el.placeholder || '',
      pattern: el.pattern || null,
      options: el.tagName === 'SELECT'
        ? Array.from(el.options).map(o => o.value)
        : null
    }));

  const buttonData = Array.from(buttons).map(el => ({
    label: el.innerText || el.value || '',
    type: el.type || 'button'
  }));

  return {
    url: window.location.href,
    title: document.title,
    fields: fieldData,
    buttons: buttonData
  };
}
"""

def main():
    if not Path(SESSION_FILE).exists():
        print(f"✗ {SESSION_FILE} not found. Run save_session.py first.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()

        print(f">>> Navigating to {PAGE_URL}")
        page.goto(PAGE_URL, wait_until="networkidle")

        print(">>> Extracting fields...")
        data = page.evaluate(EXTRACT_SCRIPT)

        snapshot = {
            "page_name": PAGE_NAME,
            "url": data["url"],
            "title": data["title"],
            "fields": data["fields"],
            "buttons": data["buttons"],
            "business_rules": [],      # you fill these manually
            "roles_allowed": []        # you fill these manually
        }

        output_file = OUTPUT_DIR / f"{PAGE_NAME}.json"
        output_file.write_text(json.dumps(snapshot, indent=2))

        print(f"\n✓ Captured {len(data['fields'])} fields, {len(data['buttons'])} buttons")
        print(f"✓ Saved to {output_file}")

        browser.close()

if __name__ == "__main__":
    main()
