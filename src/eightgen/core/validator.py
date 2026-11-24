"""Validates generated HTML5 games for structure, JavaScript sanity, and playability.

Validation layers:

1. Real HTML parsing (``html.parser``) instead of substring checks, so script
   bodies and structure are collected the way a browser would see them.
2. JavaScript sanity checks: bracket/string/template/regex-aware balance
   scanning, truncation heuristics, and a real JS parse via ``node --check``
   when Node.js is available.
3. Playability heuristics (game loop, input listeners, visual container).
"""

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from html.parser import HTMLParser
from typing import List, Optional, Tuple


@dataclass
class ValidationResult:
    """Outcome of HTML5 game validation check."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


_VOID_ELEMENTS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

# End tags HTML5 allows to be omitted; never flag these as unclosed.
_OPTIONAL_END_TAGS = frozenset({
    "p", "li", "dt", "dd", "rt", "rp", "optgroup", "option", "colgroup",
    "caption", "thead", "tbody", "tfoot", "tr", "td", "th",
    "html", "head", "body",
})

_REGEX_PRECEDING_KEYWORDS = frozenset({
    "return", "typeof", "instanceof", "in", "of", "new", "delete", "void",
    "case", "do", "else", "yield", "await", "throw",
})

# Trailing characters that strongly suggest the code was cut off mid-statement.
# Deliberately conservative: a trailing ';', ')', '}' or identifier is a normal
# script ending, and node --check already catches most real truncations.
_TRUNCATION_TAILS = frozenset("=,:&|?.")


class _DocumentParser(HTMLParser):
    """Collect script bodies and structural issues with a real HTML parse."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: List[str] = []
        self.scripts: List[Tuple[str, str]] = []
        self.unclosed: List[str] = []
        self._in_script = False
        self._script_type = ""
        self._script_buf: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "script" and not self._in_script:
            self._in_script = True
            attr_map = {k: (v or "") for k, v in attrs}
            self._script_type = attr_map.get("type", "").lower()
            self._script_buf = []
        if tag in _VOID_ELEMENTS:
            return
        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_script:
            self._in_script = False
            self.scripts.append((self._script_type, "".join(self._script_buf)))
        if tag in _VOID_ELEMENTS:
            return
        if tag in self.stack:
            while self.stack:
                top = self.stack.pop()
                if top == tag:
                    break
                if top not in _OPTIONAL_END_TAGS:
                    self.unclosed.append(top)
        # Stray closing tags are tolerated (browsers ignore them too).

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_buf.append(data)

    def close(self) -> None:
        super().close()
        if self._in_script:
            # Unterminated <script>: treat collected content as the last script.
            self._in_script = False
            self.scripts.append((self._script_type, "".join(self._script_buf)))
        for leftover in self.stack:
            if leftover not in _OPTIONAL_END_TAGS:
                self.unclosed.append(leftover)


def _js_syntax_check_enabled() -> bool:
    return os.getenv("EIGHTGEN_JS_SYNTAX_CHECK", "1").strip().lower() not in (
        "0", "false", "no", "off",
    )


@lru_cache(maxsize=1)
def _node_binary() -> Optional[str]:
    return shutil.which("node") or shutil.which("nodejs")


def _regex_allowed_after(prev_token: str) -> bool:
    if not prev_token:
        return True
    if prev_token[-1] in "(,=:[!&|?{};+-*%~^<>":
        return True
    return prev_token in _REGEX_PRECEDING_KEYWORDS


def _scan_js_balance(js: str) -> Optional[str]:
    """Bracket/string-aware balance scan; returns an error message or None.

    Understands single/double quotes, template literals (including `${...}`
    nesting), comments, and regex literals so legitimate game code with
    patterns like ``/[/{}]/`` does not produce false positives.
    """
    stack: List[Tuple[str, int]] = []
    template_markers: set = set()
    pairs = {")": "(", "]": "[", "}": "{"}
    mode = "code"
    prev_token = ""
    word = ""
    i, n = 0, len(js)

    while i < n:
        c = js[i]
        nxt = js[i + 1] if i + 1 < n else ""

        if mode == "code":
            if c == "/" and nxt == "/":
                mode = "line_comment"; i += 2; continue
            if c == "/" and nxt == "*":
                mode = "block_comment"; i += 2; continue
            if c == "'":
                mode = "squote"; i += 1; continue
            if c == '"':
                mode = "dquote"; i += 1; continue
            if c == "`":
                mode = "template"; i += 1; continue
            if c == "/" and _regex_allowed_after(word or prev_token):
                mode = "regex"; i += 1; continue
            if c in "([{":
                stack.append((c, i))
            elif c in ")]}":
                if not stack:
                    return f"Unexpected closing '{c}' (no matching opening bracket)."
                open_char, open_pos = stack[-1]
                if pairs[c] != open_char:
                    return (
                        f"Mismatched bracket: '{c}' closes '{open_char}' "
                        f"opened at offset {open_pos}."
                    )
                stack.pop()
                if c == "}" and open_pos in template_markers:
                    template_markers.discard(open_pos)
                    mode = "template"
            if c.isspace():
                i += 1; continue
            if c.isalnum() or c in "_$":
                word += c
            else:
                word = ""
                prev_token = c
            i += 1; continue

        if mode in ("squote", "dquote", "template"):
            quote = {"squote": "'", "dquote": '"', "template": "`"}[mode]
            if c == "\\":
                i += 2; continue
            if mode == "template" and c == "$" and nxt == "{":
                stack.append(("{", i + 1))
                template_markers.add(i + 1)
                mode = "code"
                word = ""
                i += 2; continue
            if c == quote:
                mode = "code"
                i += 1; continue
            i += 1; continue

        if mode == "regex":
            if c == "\\":
                i += 2; continue
            if c == "[":
                # consume char class
                i += 1
                while i < n and js[i] != "]":
                    i += 2 if js[i] == "\\" else 1
                i += 1; continue
            if c == "/":
                mode = "code"
                i += 1
                continue
            if c == "\n":
                # Unterminated regex (line terminator) — treat as plain code.
                mode = "code"
                continue
            i += 1; continue

        if mode == "line_comment":
            if c == "\n":
                mode = "code"
            i += 1; continue

        if mode == "block_comment":
            if c == "*" and nxt == "/":
                mode = "code"
                i += 2; continue
            i += 1; continue

    if mode in ("squote", "dquote", "template"):
        return f"Unterminated {mode} string literal."
    if mode == "block_comment":
        return "Unterminated block comment."
    if mode == "regex":
        return "Unterminated regular expression literal."
    if stack:
        open_char, open_pos = stack[-1]
        return (
            f"Unbalanced '{open_char}' opened at offset {open_pos} — "
            "the code appears truncated or malformed."
        )
    return None


def _node_check(js: str) -> Optional[str]:
    """Parse the script with Node.js when available; None when OK/inconclusive."""
    if not _js_syntax_check_enabled():
        return None
    node = _node_binary()
    if not node:
        return None

    def _run(code: str, module: bool) -> Optional[str]:
        suffix = ".mjs" if module else ".js"
        try:
            with tempfile.NamedTemporaryFile(
                "w", suffix=suffix, delete=True, encoding="utf-8"
            ) as handle:
                handle.write(code)
                handle.flush()
                proc = subprocess.run(
                    [node, "--check", handle.name],
                    capture_output=True, text=True, timeout=5,
                )
        except (OSError, subprocess.TimeoutExpired):
            return None  # inconclusive — never fail the game for tooling issues
        if proc.returncode == 0:
            return "OK"
        return (proc.stderr or proc.stdout or "").strip()

    classic_err = _run(js, module=False)
    if classic_err == "OK":
        return None
    # Retry as an ES module (top-level await, import/export syntax).
    module_err = _run(js, module=True)
    if module_err == "OK":
        return None
    err_text = classic_err or module_err
    if not err_text:
        return None  # node unavailable/timeout: stay inconclusive
    first_line = next(
        (line for line in err_text.splitlines() if "Error" in line or "error" in line),
        err_text.splitlines()[0] if err_text.splitlines() else "syntax error",
    )
    return f"JavaScript syntax error: {first_line.strip()[:220]}"


def _check_scripts(scripts: List[Tuple[str, str]]) -> List[str]:
    """Run JS sanity checks across all script bodies."""
    errors: List[str] = []
    for index, (script_type, code) in enumerate(scripts, start=1):
        stripped = code.strip()
        if not stripped:
            continue
        label = "" if len(scripts) == 1 else f" (script #{index})"

        balance_err = _scan_js_balance(code)
        if balance_err:
            errors.append(f"JavaScript problem{label}: {balance_err}")
            continue

        tail = stripped[-1]
        if tail in _TRUNCATION_TAILS:
            errors.append(
                f"JavaScript problem{label}: code ends with '{tail}', "
                "suggesting truncated output."
            )
            continue

        node_err = _node_check(code)
        if node_err:
            module_note = " as a module" if "module" in script_type else ""
            errors.append(f"JavaScript problem{label}{module_note}: {node_err}")
    return errors


class GameValidator:
    """Validates game HTML structure and interactivity essentials."""

    @staticmethod
    def smoke_test(html_code: str, timeout_ms: int = 5000) -> Optional[str]:
        """Run the game in a headless browser and report runtime errors.

        Returns None when the game loads cleanly (or when the check cannot run:
        Playwright is not installed), otherwise a human-readable error string.
        Callers gate this behind ``Settings.smoke_test`` /
        ``EIGHTGEN_SMOKE_TEST=1`` because it requires Playwright browsers.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None  # Playwright not installed: stay silent, never block.

        errors: List[str] = []
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.on("pageerror", lambda exc: errors.append(str(exc)))
                    page.set_content(html_code, wait_until="load", timeout=timeout_ms)
                    page.wait_for_timeout(500)
                finally:
                    browser.close()
        except Exception as exc:
            # Tooling problems must never fail a game.
            return f"Smoke test could not run: {exc}"
        if errors:
            first = errors[0][:220]
            return f"Runtime error in headless browser: {first}"
        return None

    @staticmethod
    def validate(html_code: str, check_js: bool = True) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        if not html_code or not html_code.strip():
            return ValidationResult(is_valid=False, errors=["Empty or missing HTML code."])

        code_lower = html_code.lower()

        # 1. Real HTML structure parse.
        parser = _DocumentParser()
        try:
            parser.feed(html_code)
            parser.close()
        except Exception as exc:  # pragma: no cover - parser is very tolerant
            errors.append(f"HTML parsing failed: {exc}")

        if "<html" not in code_lower and "<!doctype html" not in code_lower:
            errors.append("Missing <!DOCTYPE html> or <html> tag.")

        if "</html>" not in code_lower:
            errors.append("Unclosed <html> tag or truncated document.")

        for tag in dict.fromkeys(parser.unclosed):
            warnings.append(f"Unclosed <{tag}> tag (browsers will auto-repair it).")

        # 2. Script extraction and JavaScript sanity checks.
        scripts = parser.scripts
        if not scripts:
            errors.append("Missing <script> tag with game logic.")
        else:
            total_script_len = sum(len(code.strip()) for _, code in scripts)
            if total_script_len < 50:
                errors.append("Script tag appears empty or too short to contain game logic.")
            elif check_js:
                errors.extend(_check_scripts(scripts))

        # 3. Visual container (Canvas or DOM container).
        has_canvas = "<canvas" in code_lower
        has_container = "id=" in code_lower or "class=" in code_lower
        if not has_canvas and not has_container:
            errors.append("Missing visual container (no <canvas> or interactive DOM element found).")

        # 4. Interactivity (loop or event listeners).
        has_raf = "requestanimationframe" in code_lower
        has_interval = "setinterval" in code_lower
        has_events = (
            "addeventlistener" in code_lower
            or "onkeydown" in code_lower
            or "onclick" in code_lower
            or "onkeyup" in code_lower
            or "ontouchstart" in code_lower
        )

        if not (has_raf or has_interval or has_events):
            errors.append("Game does not appear to have an update loop or user input event listeners.")

        # Warning checks.
        if "audio" not in code_lower and "audiocontext" not in code_lower:
            warnings.append("No Web Audio API detected for sound effects.")

        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
