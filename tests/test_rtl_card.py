"""Tests for scripts/rtl-card.py: the Markdown-to-RTL-card PreToolUse hook.

Covers the Markdown converter (pure functions, loaded via ``_load``), the
sentinel matching, and the hook's stdin/stdout contract (via subprocess):
sentinel input is rewritten through ``hookSpecificOutput.updatedInput``,
everything else stays silent, and malformed stdin fails open.

RTL sample text is spelled with ``\\u`` escapes so the source file stays ASCII
(repo rule: English-only source).
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import unittest

from _load import load

card = load("scripts/rtl-card.py", "rtl_card")

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(TESTS_DIR), "scripts", "rtl-card.py")

SALAM = "\u0633\u0644\u0627\u0645"
MATN = "\u0645\u062a\u0646"

MD = (
    "# " + SALAM + "\n\n"
    + MATN + " **bold** with `git status` and [docs](https://example.com/d) "
    "and https://github.com/rajool\n\n"
    "- item one\n"
    "- item two\n\n"
    "1. step one\n"
    "2. step two\n\n"
    "> a short quote\n\n"
    "| col | val |\n"
    "| --- | --- |\n"
    "| a | 1 |\n\n"
    "```bash\n"
    'echo "hi" && ls -la\n'
    "```\n\n"
    '<svg viewBox="0 0 10 10"><rect width="10" height="10"/></svg>\n\n'
    "---\n"
    "closing line.\n"
)


def hook(payload, raw=None):
    data = raw if raw is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, SCRIPT], input=data, capture_output=True, text=True, timeout=15
    )


def event(widget_code, tool="mcp__visualize__show_widget"):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {
            "widget_code": widget_code,
            "title": "sample_card",
            "loading_messages": ["one"],
        },
    }


class TestConvert(unittest.TestCase):
    def test_blocks_and_inline(self):
        out = card.convert(MD)
        self.assertIn("<h1>" + SALAM + "</h1>", out)
        self.assertIn("<strong>bold</strong>", out)
        self.assertIn("<code>git status</code>", out)
        self.assertIn('<a href="https://example.com/d">docs</a>', out)
        self.assertIn('<a class="u" href="https://github.com/rajool">', out)
        self.assertIn("<ul><li>item one</li><li>item two</li></ul>", out)
        self.assertIn("<ol><li>step one</li><li>step two</li></ol>", out)
        self.assertIn("<blockquote><p>a short quote</p></blockquote>", out)
        self.assertIn("<th>col</th>", out)
        self.assertIn("<td>a</td>", out)
        self.assertIn("&quot;hi&quot; &amp;&amp; ls -la", out)
        self.assertIn('<svg viewBox="0 0 10 10">', out)
        self.assertIn("<hr>", out)
        self.assertIn("<p>closing line.</p>", out)

    def test_text_html_is_escaped(self):
        out = card.convert(MATN + " with <script>alert(1)</script> inside")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_wrap_shell(self):
        out = card.wrap("<p>x</p>")
        self.assertIn('dir="rtl"', out)
        self.assertIn("Vazirmatn", out)
        self.assertIn("unicode-bidi:plaintext", out)
        self.assertTrue(out.startswith('<div id="rtl-card"'))

    def test_sentinel(self):
        self.assertIsNotNone(card.SENTINEL.match("<md>\nhello\n</md>"))
        self.assertIsNotNone(card.SENTINEL.match("  <md> hello </md>  "))
        self.assertIsNone(card.SENTINEL.match("<div>hello</div>"))
        self.assertIsNone(card.SENTINEL.match("<md>unclosed"))


class TestHookContract(unittest.TestCase):
    def test_sentinel_is_rewritten(self):
        proc = hook(event("<md>\n" + MD + "\n</md>"))
        self.assertEqual(proc.returncode, 0)
        out = json.loads(proc.stdout)
        hso = out["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        self.assertEqual(hso["permissionDecision"], "allow")
        code = hso["updatedInput"]["widget_code"]
        self.assertIn('dir="rtl"', code)
        self.assertIn("<h1>" + SALAM + "</h1>", code)
        self.assertNotIn("<md>", code)

    def test_other_input_fields_preserved(self):
        proc = hook(event("<md>\nplain\n</md>"))
        upd = json.loads(proc.stdout)["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(upd["title"], "sample_card")
        self.assertEqual(upd["loading_messages"], ["one"])

    def test_plain_html_passes_through_silently(self):
        proc = hook(event("<div>a normal widget</div>"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_other_tools_are_ignored(self):
        proc = hook(event("<md>\nx\n</md>", tool="Bash"))
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_malformed_stdin_fails_open(self):
        proc = hook(None, raw="not json at all")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout.strip(), "")

    def test_output_is_one_json_line(self):
        proc = hook(event("<md>\nx\n</md>"))
        self.assertEqual(len(proc.stdout.strip().splitlines()), 1)
        json.loads(proc.stdout)

    def test_conversion_failure_denies_with_guidance(self):
        fresh = load("scripts/rtl-card.py", "rtl_card_deny")

        def boom(md):
            raise RuntimeError("boom")

        fresh.convert = boom
        saved_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO(json.dumps(event("<md>\nx\n</md>")))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                fresh.main()
        finally:
            sys.stdin = saved_stdin
        hso = json.loads(buf.getvalue())["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny")
        self.assertIn("HTML card", hso["permissionDecisionReason"])
        self.assertIn('dir="rtl"', hso["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
