import json
import logging
from typing import Callable, Awaitable

from playwright.async_api import CDPSession, Page

logger = logging.getLogger(__name__)

INJECTED_SCRIPT = """
(function() {
    if (window.__browserRecorderInjected) return;
    window.__browserRecorderInjected = true;

    // ======================================================================
    // Constants
    // ======================================================================
    var TAG_TO_ROLE = {
        A:'link', BUTTON:'button', INPUT:'textbox', TEXTAREA:'textbox',
        SELECT:'combobox', IMG:'img',
        H1:'heading', H2:'heading', H3:'heading',
        H4:'heading', H5:'heading', H6:'heading'
    };
    var ROLE_TAGS = {
        link: 'a',
        button: 'button,input[type="button"],input[type="submit"],input[type="reset"]',
        textbox: 'input:not([type]),input[type="text"],input[type="email"],input[type="password"],input[type="search"],input[type="tel"],input[type="url"],textarea',
        combobox: 'select',
        img: 'img',
        heading: 'h1,h2,h3,h4,h5,h6',
        listitem: 'li',
        checkbox: 'input[type="checkbox"]',
        radio: 'input[type="radio"]'
    };
    var LANDMARK_TAGS = ['nav','header','footer','main','aside','article','section','form'];

    // ======================================================================
    // Helpers
    // ======================================================================
    function isUnique(sel) {
        try { return document.querySelectorAll(sel).length === 1; }
        catch(e) { return false; }
    }

    // Check if an element is visible (not hidden by CSS)
    function isElementVisible(el) {
        if (!el) return false;
        if (el.offsetWidth === 0 && el.offsetHeight === 0) return false;
        var style = window.getComputedStyle(el);
        return style.display !== 'none' && style.visibility !== 'hidden';
    }

    // Check uniqueness among VISIBLE elements only (matches Playwright behavior)
    function isVisibleUnique(sel) {
        try {
            var els = document.querySelectorAll(sel);
            var count = 0;
            for (var i = 0; i < els.length; i++) {
                if (isElementVisible(els[i])) count++;
            }
            return count === 1;
        } catch(e) { return false; }
    }

    // Check if an id looks stable (not auto-generated)
    function isStableId(id) {
        if (!id || id.length > 80) return false;
        // Pure numbers
        if (/^\\d+$/.test(id)) return false;
        // Hex hashes (8+ hex chars)
        if (/^[a-f0-9]{8,}$/i.test(id)) return false;
        // Framework-generated prefixes
        if (/^(comp|ember|react|vue|ng|el|radix|rc|mui|chakra)-/i.test(id)) return false;
        // Trailing random suffix after a dash/underscore (5+ random chars)
        if (/[_-][a-z0-9]{6,}$/i.test(id)) return false;
        // Contains colons or dollar signs (framework artifacts)
        if (/[:$]/.test(id)) return false;
        // Name followed by 3+ digits (e.g. "input123", "field0042")
        if (/^[a-zA-Z]+\\d{3,}$/.test(id)) return false;
        // UUID patterns
        if (/[0-9a-f]{8}-[0-9a-f]{4}/i.test(id)) return false;
        return true;
    }

    function getAccessibleName(el) {
        // 1. aria-label
        var a = el.getAttribute('aria-label');
        if (a && a.trim()) return a.trim();
        // 2. aria-labelledby
        var lblId = el.getAttribute('aria-labelledby');
        if (lblId) {
            var parts = lblId.split(/\\s+/);
            var texts = [];
            for (var p = 0; p < parts.length; p++) {
                var ref = document.getElementById(parts[p]);
                if (ref) texts.push((ref.textContent || '').trim());
            }
            var joined = texts.join(' ').trim();
            if (joined && joined.length <= 80) return joined;
        }
        // 3. <label for="id"> for form elements
        if (el.id && (el.tagName === 'INPUT' || el.tagName === 'SELECT' || el.tagName === 'TEXTAREA')) {
            try {
                var label = document.querySelector('label[for="' + CSS.escape(el.id) + '"]');
                if (label) {
                    var lt = (label.textContent || '').trim();
                    if (lt && lt.length <= 80) return lt;
                }
            } catch(e) {}
        }
        // 4. alt text for images
        if (el.tagName === 'IMG') {
            var alt = el.getAttribute('alt');
            if (alt && alt.trim()) return alt.trim();
        }
        // 5. title attribute
        var title = el.getAttribute('title');
        if (title && title.trim()) return title.trim();
        // 6. Direct child text nodes only
        var dt = '';
        for (var i = 0; i < el.childNodes.length; i++) {
            if (el.childNodes[i].nodeType === 3) dt += el.childNodes[i].textContent;
        }
        dt = dt.trim();
        if (dt && dt.length <= 80) return dt;
        // 7. Full textContent for small elements
        var full = (el.textContent || '').trim();
        if (full.length <= 50) return full;
        return null;
    }

    // Get visible inner text (for dedicated text strategy)
    function getVisibleText(el) {
        if (!el) return null;
        var dt = '';
        for (var i = 0; i < el.childNodes.length; i++) {
            if (el.childNodes[i].nodeType === 3) dt += el.childNodes[i].textContent;
        }
        dt = dt.trim();
        if (dt && dt.length <= 60) return dt;
        var full = (el.textContent || '').trim();
        if (full.length <= 50) return full;
        return null;
    }

    // Test if exact text uniquely matches one VISIBLE element of same tag
    function testTextUnique(el, text) {
        if (!text) return false;
        var tag = el.tagName.toLowerCase();
        try {
            var all = document.querySelectorAll(tag);
            var count = 0;
            for (var i = 0; i < all.length; i++) {
                var t = getVisibleText(all[i]);
                if (t === text && isElementVisible(all[i])) count++;
            }
            return count === 1;
        } catch(e) { return false; }
    }

    function testRoleNameUnique(role, name) {
        if (!role || !name) return false;
        var tagSel = ROLE_TAGS[role];
        var candidates = [];
        if (tagSel) {
            try { candidates = Array.from(document.querySelectorAll(tagSel)); } catch(e) {}
        }
        try {
            var explicit = document.querySelectorAll('[role="' + role + '"]');
            for (var i = 0; i < explicit.length; i++) {
                if (candidates.indexOf(explicit[i]) === -1) candidates.push(explicit[i]);
            }
        } catch(e) {}
        var matches = candidates.filter(function(c) {
            return getAccessibleName(c) === name && isElementVisible(c);
        });
        return matches.length === 1;
    }

    function testRoleNameUniqueInContainer(containerEl, role, name) {
        if (!containerEl || !role || !name) return false;
        var tagSel = ROLE_TAGS[role];
        var candidates = [];
        if (tagSel) {
            try { candidates = Array.from(containerEl.querySelectorAll(tagSel)); } catch(e) {}
        }
        try {
            var explicit = containerEl.querySelectorAll('[role="' + role + '"]');
            for (var i = 0; i < explicit.length; i++) {
                if (candidates.indexOf(explicit[i]) === -1) candidates.push(explicit[i]);
            }
        } catch(e) {}
        var matches = candidates.filter(function(c) {
            return getAccessibleName(c) === name && isElementVisible(c);
        });
        return matches.length === 1;
    }

    function findContainerSelector(el) {
        var current = el.parentElement;
        while (current && current !== document.body) {
            var tag = current.tagName.toLowerCase();
            var isLandmark = LANDMARK_TAGS.indexOf(tag) !== -1;
            var explicitRole = current.getAttribute('role');
            if (isLandmark || explicitRole) {
                if (current.id && isStableId(current.id)) return '#' + CSS.escape(current.id);
                var ariaL = current.getAttribute('aria-label');
                if (ariaL) {
                    var sel = tag + '[aria-label="' + CSS.escape(ariaL) + '"]';
                    if (isUnique(sel)) return sel;
                }
                if (isUnique(tag)) return tag;
                if (current.className && typeof current.className === 'string') {
                    var classes = current.className.trim().split(/\\s+/).filter(function(c) { return c.length > 0; });
                    if (classes.length > 0) {
                        var clsSel = tag + '.' + classes.map(function(c) { return CSS.escape(c); }).join('.');
                        if (isUnique(clsSel)) return clsSel;
                    }
                }
                if (explicitRole) {
                    var rSel = '[role="' + explicitRole + '"]';
                    if (isUnique(rSel)) return rSel;
                }
            }
            current = current.parentElement;
        }
        return null;
    }

    // ======================================================================
    // Selector strategy — STRICT PRIORITY ORDER per spec:
    //   1. data-testid / data-cy / data-qa / data-id  (testing attributes)
    //   2. aria-label  (accessibility, stable)
    //   3. role + visible text  (semantic, readable)
    //   4. id  (only if stable — skip auto-generated)
    //   5. name attribute  (reliable for forms)
    //   6. placeholder  (for inputs when nothing better)
    //   7. visible text exact match  (for buttons/links)
    //   8. clean CSS selector  (tag + stable classes)
    //   9. XPath  (absolute last resort)
    // Each candidate is tested for uniqueness in the live DOM.
    // ======================================================================
    function computeLocatorStrategy(el) {
        if (!el || !el.tagName) return {strategy: 'css', container: null};

        // --- Priority 1: Testing data attributes (always win) ---
        if (el.getAttribute('data-testid'))
            return {strategy: 'data_testid', container: null};
        if (el.getAttribute('data-cy'))
            return {strategy: 'data_cy', container: null};
        if (el.getAttribute('data-qa'))
            return {strategy: 'data_qa', container: null};
        if (el.getAttribute('data-id'))
            return {strategy: 'data_id', container: null};

        // --- Priority 2: aria-label (tested for visible uniqueness) ---
        var ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel && ariaLabel.trim()) {
            if (isVisibleUnique('[aria-label="' + CSS.escape(ariaLabel.trim()) + '"]'))
                return {strategy: 'aria_label', container: null};
        }

        // --- Priority 3: role + accessible name ---
        var role = el.getAttribute('role') || TAG_TO_ROLE[el.tagName] || null;
        var accName = getAccessibleName(el);
        if (role && accName) {
            // 3a. Unique globally
            if (testRoleNameUnique(role, accName))
                return {strategy: 'role_name', container: null};
            // 3b. Unique within nearest landmark container
            var containerSel = findContainerSelector(el);
            if (containerSel) {
                var containerEl = document.querySelector(containerSel);
                if (containerEl && testRoleNameUniqueInContainer(containerEl, role, accName))
                    return {strategy: 'role_name_scoped', container: containerSel};
            }
        }

        // --- Priority 4: id (only if stable, not auto-generated) ---
        if (el.id && isStableId(el.id))
            return {strategy: 'id', container: null};

        // --- Priority 5: name attribute (tested for uniqueness) ---
        var nameAttr = el.getAttribute('name');
        if (nameAttr) {
            if (isUnique('[name="' + CSS.escape(nameAttr) + '"]'))
                return {strategy: 'name', container: null};
        }

        // --- Priority 6: placeholder (tested for uniqueness) ---
        var ph = el.getAttribute('placeholder');
        if (ph && ph.trim()) {
            if (isUnique('[placeholder="' + CSS.escape(ph.trim()) + '"]'))
                return {strategy: 'placeholder', container: null};
        }

        // --- Priority 7: visible text exact match (for buttons/links) ---
        var visText = getVisibleText(el);
        if (visText && testTextUnique(el, visText))
            return {strategy: 'text', container: null};

        // --- Priority 8: href for links (tested for uniqueness) ---
        if (el.tagName === 'A' && el.getAttribute('href')) {
            var href = el.getAttribute('href');
            if (isUnique('a[href="' + CSS.escape(href) + '"]'))
                return {strategy: 'href', container: null};
        }

        // --- Fallback: role+name even if not globally unique ---
        // Better than positional CSS; generator will use .first
        if (role && accName) {
            return {strategy: 'role_name_first', container: null};
        }

        // --- Priority 9: CSS selector (last resort) ---
        return {strategy: 'css', container: null};
    }

    // ======================================================================
    // CSS/XPath selector generation
    // ======================================================================
    function generateCSSSelector(el) {
        if (el.id && isStableId(el.id)) return '#' + CSS.escape(el.id);

        // Testing attributes
        var testid = el.getAttribute('data-testid');
        if (testid) return '[data-testid="' + testid + '"]';
        var dataCy = el.getAttribute('data-cy');
        if (dataCy) return '[data-cy="' + dataCy + '"]';
        var dataQa = el.getAttribute('data-qa');
        if (dataQa) return '[data-qa="' + dataQa + '"]';

        // Unique class combination
        if (el.className && typeof el.className === 'string') {
            var classes = el.className.trim().split(/\\s+/).filter(function(c) { return c.length > 0; });
            if (classes.length > 0) {
                // Filter out dynamic/hash-like classes
                var stableClasses = classes.filter(function(c) {
                    if (c.length > 40) return false;
                    if (/^[a-f0-9]{6,}$/i.test(c)) return false;
                    if (/^_[a-zA-Z0-9]{5,}$/.test(c)) return false;
                    return true;
                });
                if (stableClasses.length > 0) {
                    var selector = el.tagName.toLowerCase() + '.' + stableClasses.map(function(c) { return CSS.escape(c); }).join('.');
                    try {
                        if (document.querySelectorAll(selector).length === 1) return selector;
                    } catch(e) {}
                }
            }
        }

        // nth-child path (always unique)
        var parts = [];
        var current = el;
        while (current && current !== document.body && current !== document.documentElement) {
            var sel = current.tagName.toLowerCase();
            var parent = current.parentElement;
            if (parent) {
                var siblings = Array.from(parent.children).filter(function(c) { return c.tagName === current.tagName; });
                if (siblings.length > 1) {
                    var index = siblings.indexOf(current) + 1;
                    sel += ':nth-child(' + index + ')';
                }
            }
            parts.unshift(sel);
            current = current.parentElement;
        }
        return parts.join(' > ');
    }

    function generateXPath(el) {
        if (el.id && isStableId(el.id)) return '//*[@id="' + el.id + '"]';
        var parts = [];
        var current = el;
        while (current && current.nodeType === Node.ELEMENT_NODE) {
            var index = 1;
            var sibling = current.previousElementSibling;
            while (sibling) {
                if (sibling.tagName === current.tagName) index++;
                sibling = sibling.previousElementSibling;
            }
            parts.unshift(current.tagName.toLowerCase() + '[' + index + ']');
            current = current.parentElement;
        }
        return '/' + parts.join('/');
    }

    // ======================================================================
    // Full element context extraction — captures EVERY available attribute
    // ======================================================================
    function getElementContext(el) {
        if (!el || !el.tagName) return null;

        var accName = getAccessibleName(el);
        var role = el.getAttribute('role') || TAG_TO_ROLE[el.tagName] || null;
        var loc = computeLocatorStrategy(el);

        return {
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            class_name: (el.className && typeof el.className === 'string') ? el.className.trim() || null : null,
            name: el.getAttribute('name') || null,
            aria_label: el.getAttribute('aria-label') || null,
            aria_labelledby: el.getAttribute('aria-labelledby') || null,
            role: role,
            text_content: accName,
            title: el.getAttribute('title') || null,
            data_testid: el.getAttribute('data-testid') || null,
            data_id: el.getAttribute('data-id') || null,
            data_cy: el.getAttribute('data-cy') || null,
            data_qa: el.getAttribute('data-qa') || null,
            placeholder: el.getAttribute('placeholder') || null,
            href: el.getAttribute('href') || null,
            input_type: el.getAttribute('type') || null,
            value: (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT') ? (el.value || null) : null,
            css_selector: generateCSSSelector(el),
            xpath: generateXPath(el),
            locator_strategy: loc.strategy,
            container_css: loc.container
        };
    }

    // ======================================================================
    // Action reporting
    // ======================================================================
    function reportAction(data) {
        try { window._reportAction(JSON.stringify(data)); }
        catch(e) { console.error('Failed to report action:', e); }
    }

    // ======================================================================
    // Input debouncing — collapse rapid input events into one final value
    // ======================================================================
    var inputTimer = null;
    var lastInputData = null;

    function debouncedInputReport(el, value) {
        lastInputData = {
            action_type: 'type',
            timestamp: Date.now() / 1000,
            text: value,
            element: getElementContext(el)
        };
        if (inputTimer) clearTimeout(inputTimer);
        inputTimer = setTimeout(function() {
            if (lastInputData) {
                reportAction(lastInputData);
                lastInputData = null;
            }
        }, 300);
    }

    // ======================================================================
    // Event listeners
    // ======================================================================
    document.addEventListener('click', function(e) {
        // Walk up to find the meaningful clickable element (not inner span/svg)
        var target = e.target;
        var clickable = target;
        var current = target;
        while (current && current !== document.body) {
            var tag = current.tagName;
            if (tag === 'A' || tag === 'BUTTON' ||
                current.getAttribute('role') === 'button' ||
                current.getAttribute('role') === 'link' ||
                current.getAttribute('role') === 'tab' ||
                current.getAttribute('role') === 'menuitem' ||
                current.getAttribute('role') === 'option' ||
                current.onclick ||
                current.getAttribute('data-testid') ||
                current.getAttribute('data-cy') ||
                (tag === 'INPUT' && (current.type === 'submit' || current.type === 'button' || current.type === 'checkbox' || current.type === 'radio'))) {
                clickable = current;
                break;
            }
            current = current.parentElement;
        }
        reportAction({
            action_type: 'click',
            timestamp: Date.now() / 1000,
            x: e.clientX, y: e.clientY,
            element: getElementContext(clickable)
        });
    }, true);

    document.addEventListener('dblclick', function(e) {
        reportAction({
            action_type: 'dblclick',
            timestamp: Date.now() / 1000,
            x: e.clientX, y: e.clientY,
            element: getElementContext(e.target)
        });
    }, true);

    document.addEventListener('input', function(e) {
        debouncedInputReport(e.target, e.target.value);
    }, true);

    document.addEventListener('keydown', function(e) {
        var specialKeys = ['Enter', 'Tab', 'Escape', 'Backspace', 'Delete',
            'ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'];
        if (specialKeys.indexOf(e.key) !== -1) {
            if (lastInputData) {
                reportAction(lastInputData);
                lastInputData = null;
                if (inputTimer) { clearTimeout(inputTimer); inputTimer = null; }
            }
            reportAction({
                action_type: 'keydown',
                timestamp: Date.now() / 1000,
                key: e.key,
                element: getElementContext(e.target)
            });
        }
    }, true);

    // Select/change for dropdowns
    document.addEventListener('change', function(e) {
        if (e.target.tagName === 'SELECT') {
            reportAction({
                action_type: 'type',
                timestamp: Date.now() / 1000,
                text: e.target.value,
                element: getElementContext(e.target)
            });
        }
    }, true);

    var observer = new MutationObserver(function() {
        if (!window.__browserRecorderInjected) window.__browserRecorderInjected = true;
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
})();
"""


class CDPInjector:
    """Injects JavaScript into the browser page via CDP to capture user interactions."""

    def __init__(self) -> None:
        self._action_callback: Callable[[dict], Awaitable[None]] | None = None
        self._cdp_session: CDPSession | None = None

    async def inject(
        self,
        cdp_session: CDPSession,
        page: Page,
        action_callback: Callable[[dict], Awaitable[None]] | None = None,
    ) -> None:
        self._cdp_session = cdp_session
        self._action_callback = action_callback

        await cdp_session.send("Runtime.enable")
        await cdp_session.send("Page.enable")
        cdp_session.on("Runtime.bindingCalled", self._on_binding_called)
        await cdp_session.send("Runtime.addBinding", {"name": "_reportAction"})
        await cdp_session.send("Page.addScriptToEvaluateOnNewDocument", {"source": INJECTED_SCRIPT})
        await cdp_session.send("Runtime.evaluate", {"expression": INJECTED_SCRIPT})
        logger.info("CDP injector script injected successfully.")

    async def _on_binding_called(self, params: dict) -> None:
        if params.get("name") != "_reportAction":
            return
        payload_str = params.get("payload", "")
        try:
            action_data = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse action payload: {payload_str}")
            return
        logger.info(f"Action captured via CDP: {action_data.get('action_type')}")
        if self._action_callback:
            try:
                await self._action_callback(action_data)
            except Exception as e:
                logger.error(f"Action callback error: {e}")
