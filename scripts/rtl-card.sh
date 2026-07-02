#!/usr/bin/env bash
# rtl-card: entry point for the PreToolUse(mcp__visualize__show_widget) hook.
# Rewrites an <md>...</md> widget_code into a styled RTL HTML card via
# hookSpecificOutput.updatedInput, so the fixed template costs zero model tokens.
# Widget calls without the <md> sentinel pass through untouched.
# fail-open: no python3 or any error means exit 0 (the tool call proceeds untouched).
# Deliberate bypass (rare): RTL_CARD=off
set -u
[ "${RTL_CARD:-}" = "off" ] && exit 0
command -v python3 >/dev/null 2>&1 || exit 0
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/rtl-card.py"
