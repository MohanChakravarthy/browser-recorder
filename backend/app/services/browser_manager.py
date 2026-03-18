import asyncio
import base64
import logging
from typing import Optional, Callable, Awaitable

from playwright.async_api import async_playwright, Browser, Page, Playwright, CDPSession

from app.config import settings

logger = logging.getLogger(__name__)

# Mapping of special key names to CDP key descriptors
SPECIAL_KEYS: dict[str, dict] = {
    "Enter": {
        "key": "Enter",
        "code": "Enter",
        "windowsVirtualKeyCode": 13,
        "nativeVirtualKeyCode": 13,
    },
    "Backspace": {
        "key": "Backspace",
        "code": "Backspace",
        "windowsVirtualKeyCode": 8,
        "nativeVirtualKeyCode": 8,
    },
    "Tab": {
        "key": "Tab",
        "code": "Tab",
        "windowsVirtualKeyCode": 9,
        "nativeVirtualKeyCode": 9,
    },
    "Escape": {
        "key": "Escape",
        "code": "Escape",
        "windowsVirtualKeyCode": 27,
        "nativeVirtualKeyCode": 27,
    },
    "Delete": {
        "key": "Delete",
        "code": "Delete",
        "windowsVirtualKeyCode": 46,
        "nativeVirtualKeyCode": 46,
    },
    "ArrowUp": {
        "key": "ArrowUp",
        "code": "ArrowUp",
        "windowsVirtualKeyCode": 38,
        "nativeVirtualKeyCode": 38,
    },
    "ArrowDown": {
        "key": "ArrowDown",
        "code": "ArrowDown",
        "windowsVirtualKeyCode": 40,
        "nativeVirtualKeyCode": 40,
    },
    "ArrowLeft": {
        "key": "ArrowLeft",
        "code": "ArrowLeft",
        "windowsVirtualKeyCode": 37,
        "nativeVirtualKeyCode": 37,
    },
    "ArrowRight": {
        "key": "ArrowRight",
        "code": "ArrowRight",
        "windowsVirtualKeyCode": 39,
        "nativeVirtualKeyCode": 39,
    },
    "Home": {
        "key": "Home",
        "code": "Home",
        "windowsVirtualKeyCode": 36,
        "nativeVirtualKeyCode": 36,
    },
    "End": {
        "key": "End",
        "code": "End",
        "windowsVirtualKeyCode": 35,
        "nativeVirtualKeyCode": 35,
    },
    "PageUp": {
        "key": "PageUp",
        "code": "PageUp",
        "windowsVirtualKeyCode": 33,
        "nativeVirtualKeyCode": 33,
    },
    "PageDown": {
        "key": "PageDown",
        "code": "PageDown",
        "windowsVirtualKeyCode": 34,
        "nativeVirtualKeyCode": 34,
    },
    "Shift": {
        "key": "Shift",
        "code": "ShiftLeft",
        "windowsVirtualKeyCode": 16,
        "nativeVirtualKeyCode": 16,
    },
    "Control": {
        "key": "Control",
        "code": "ControlLeft",
        "windowsVirtualKeyCode": 17,
        "nativeVirtualKeyCode": 17,
    },
    "Alt": {
        "key": "Alt",
        "code": "AltLeft",
        "windowsVirtualKeyCode": 18,
        "nativeVirtualKeyCode": 18,
    },
    "Meta": {
        "key": "Meta",
        "code": "MetaLeft",
        "windowsVirtualKeyCode": 91,
        "nativeVirtualKeyCode": 91,
    },
    " ": {
        "key": " ",
        "code": "Space",
        "windowsVirtualKeyCode": 32,
        "nativeVirtualKeyCode": 32,
        "text": " ",
    },
}


# Stealth script to avoid bot detection and CAPTCHAs
STEALTH_SCRIPT = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
    configurable: true,
});

// Override navigator.languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
    configurable: true,
});

// Override navigator.plugins (make it look like a real browser)
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
        ];
        plugins.length = 3;
        return plugins;
    },
    configurable: true,
});

// Override navigator.mimeTypes
Object.defineProperty(navigator, 'mimeTypes', {
    get: () => {
        const mimeTypes = [
            { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
        ];
        mimeTypes.length = 1;
        return mimeTypes;
    },
    configurable: true,
});

// Fix chrome.runtime to exist
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.runtime) {
    window.chrome.runtime = {
        connect: function() {},
        sendMessage: function() {},
    };
}

// Override permissions API
if (navigator.permissions) {
    const originalQuery = navigator.permissions.query;
    navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters)
    );
}

// Override WebGL vendor and renderer
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) {
        return 'Intel Inc.';
    }
    if (parameter === 37446) {
        return 'Intel Iris OpenGL Engine';
    }
    return getParameter.call(this, parameter);
};

// Fix for headless detection via window.outerWidth/outerHeight
if (window.outerWidth === 0) {
    Object.defineProperty(window, 'outerWidth', { get: () => window.innerWidth });
}
if (window.outerHeight === 0) {
    Object.defineProperty(window, 'outerHeight', { get: () => window.innerHeight + 85 });
}

// Fix screen dimensions
Object.defineProperty(screen, 'availWidth', { get: () => screen.width });
Object.defineProperty(screen, 'availHeight', { get: () => screen.height - 40 });

// Remove automation-related properties
delete navigator.__proto__.webdriver;

// Fix for iframe contentWindow detection
const originalAttachShadow = Element.prototype.attachShadow;
if (originalAttachShadow) {
    Element.prototype.attachShadow = function() {
        return originalAttachShadow.apply(this, arguments);
    };
}

// Prevent detection via Error stack traces
const originalError = Error;
Error = function(...args) {
    const error = new originalError(...args);
    const stack = error.stack || '';
    error.stack = stack.replace(/headless/gi, '');
    return error;
};
Error.prototype = originalError.prototype;
Error.captureStackTrace = originalError.captureStackTrace;
"""


class BrowserManager:
    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
        self._cdp_session: Optional[CDPSession] = None
        self._screencast_active: bool = False
        self._screencast_callback: Optional[Callable[[bytes], Awaitable[None]]] = None
        self._on_frame_handler: Optional[Callable] = None

    @property
    def page(self) -> Optional[Page]:
        return self._page

    @property
    def browser(self) -> Optional[Browser]:
        return self._browser

    @property
    def playwright(self) -> Optional[Playwright]:
        return self._playwright

    async def start(self) -> None:
        """Launch Playwright and Chromium browser with stealth anti-detection."""
        logger.info("Starting browser manager...")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--disable-default-apps",
                "--disable-extensions",
                "--disable-sync",
                "--disable-translate",
                "--no-first-run",
                "--window-size=1280,800",
            ],
        )
        context = await self._browser.new_context(
            viewport={
                "width": settings.BROWSER_VIEWPORT_WIDTH,
                "height": settings.BROWSER_VIEWPORT_HEIGHT,
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Inject stealth scripts before any page loads
        await context.add_init_script(STEALTH_SCRIPT)

        self._page = await context.new_page()
        # Navigate to a default page so there's visible content
        try:
            await self._page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=10000)
        except Exception as e:
            logger.warning(f"Could not load default page: {e}")
        logger.info("Browser manager started successfully.")

    async def stop(self) -> None:
        """Clean up browser resources."""
        logger.info("Stopping browser manager...")
        if self._screencast_active:
            await self.stop_screencast()
        if self._cdp_session:
            try:
                await self._cdp_session.detach()
            except Exception:
                pass
            self._cdp_session = None
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        self._page = None
        logger.info("Browser manager stopped.")

    async def get_cdp_session(self) -> CDPSession:
        """Create or return existing CDP session on the page."""
        if self._cdp_session is None:
            if self._page is None:
                raise RuntimeError("Browser page not initialized")
            self._cdp_session = await self._page.context.new_cdp_session(self._page)
        return self._cdp_session

    async def start_screencast(
        self, callback: Callable[[bytes], Awaitable[None]]
    ) -> None:
        """Start CDP screencast and call callback with raw JPEG bytes for each frame."""
        # Stop any existing screencast first
        if self._screencast_active:
            await self.stop_screencast()

        cdp = await self.get_cdp_session()
        self._screencast_callback = callback

        async def on_frame(params: dict) -> None:
            try:
                frame_data = base64.b64decode(params["data"])
                session_id = params.get("sessionId", 0)
                try:
                    await callback(frame_data)
                except Exception as e:
                    logger.error(f"Screencast callback error: {e}")
                # Acknowledge the frame so CDP sends the next one
                try:
                    await cdp.send("Page.screencastFrameAck", {"sessionId": session_id})
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Frame processing error: {e}")

        self._on_frame_handler = on_frame
        cdp.on("Page.screencastFrame", on_frame)

        await cdp.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": settings.SCREENCAST_QUALITY,
                "maxWidth": settings.BROWSER_VIEWPORT_WIDTH,
                "maxHeight": settings.BROWSER_VIEWPORT_HEIGHT,
                "everyNthFrame": 1,
            },
        )
        self._screencast_active = True
        logger.info("Screencast started.")

    async def stop_screencast(self) -> None:
        """Stop the CDP screencast."""
        if self._cdp_session and self._screencast_active:
            try:
                await self._cdp_session.send("Page.stopScreencast")
            except Exception:
                pass
            # Remove the event handler to prevent duplicates on restart
            if self._on_frame_handler:
                try:
                    self._cdp_session.remove_listener("Page.screencastFrame", self._on_frame_handler)
                except Exception:
                    pass
                self._on_frame_handler = None
            self._screencast_active = False
            logger.info("Screencast stopped.")

    async def dispatch_mouse_event(
        self,
        event_type: str,
        x: int,
        y: int,
        button: str = "left",
        click_count: int = 1,
    ) -> None:
        """Dispatch a CDP mouse event."""
        cdp = await self.get_cdp_session()
        cdp_button = button if button in ("left", "right", "middle", "none") else "left"
        await cdp.send(
            "Input.dispatchMouseEvent",
            {
                "type": event_type,
                "x": x,
                "y": y,
                "button": cdp_button,
                "clickCount": click_count,
            },
        )

    async def dispatch_key_event(
        self,
        event_type: str,
        key: str,
        text: Optional[str] = None,
        modifiers: int = 0,
    ) -> None:
        """Dispatch a CDP keyboard event."""
        cdp = await self.get_cdp_session()

        params: dict = {
            "type": event_type,
            "modifiers": modifiers,
        }

        is_printable = len(key) == 1 and key not in SPECIAL_KEYS

        if key in SPECIAL_KEYS:
            desc = SPECIAL_KEYS[key]
            params["key"] = desc["key"]
            params["code"] = desc["code"]
            params["windowsVirtualKeyCode"] = desc["windowsVirtualKeyCode"]
            params["nativeVirtualKeyCode"] = desc["nativeVirtualKeyCode"]
            if "text" in desc and event_type == "keyDown":
                params["text"] = desc["text"]
        else:
            params["key"] = key
            if len(key) == 1:
                params["code"] = f"Key{key.upper()}" if key.isalpha() else key
                params["windowsVirtualKeyCode"] = ord(key.upper()) if key.isalpha() else ord(key)
                params["nativeVirtualKeyCode"] = params["windowsVirtualKeyCode"]
                # Don't set text on keyDown for printable chars — use a separate char event instead
                # Setting text on keyDown AND sending char causes double input

        await cdp.send("Input.dispatchKeyEvent", params)

        # For printable characters, dispatch a separate 'char' event after keyDown
        # This is what actually inserts text into input fields
        if event_type == "keyDown" and is_printable:
            char_text = text if text is not None else key
            await cdp.send(
                "Input.dispatchKeyEvent",
                {
                    "type": "char",
                    "text": char_text,
                    "key": key,
                    "modifiers": modifiers,
                },
            )

    async def dispatch_scroll(
        self, x: int, y: int, delta_x: float, delta_y: float
    ) -> None:
        """Dispatch a CDP scroll (mouseWheel) event."""
        cdp = await self.get_cdp_session()
        await cdp.send(
            "Input.dispatchMouseEvent",
            {
                "type": "mouseWheel",
                "x": x,
                "y": y,
                "deltaX": delta_x,
                "deltaY": delta_y,
            },
        )

    async def navigate(self, url: str) -> None:
        """Navigate the page to the given URL."""
        if self._page is None:
            raise RuntimeError("Browser page not initialized")
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.error(f"Navigation error: {e}")
            raise

    def get_current_url(self) -> str:
        """Return the current page URL."""
        if self._page is None:
            return ""
        return self._page.url

    def get_cdp_endpoint(self) -> str:
        """Return the browser's CDP WebSocket endpoint for script replay."""
        if self._browser is None:
            return ""
        # Playwright's chromium browser exposes the wsEndpoint via the underlying connection
        try:
            return self._browser._impl_obj._browser.ws_endpoint  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback: try the contexts approach
            return ""
