"""Custom user-created tools for Assistant-Bird (鸟助手).

Place your own @tool functions in this directory. They are kept separate from
the built-in tools/ directory so you can freely experiment without touching core code.

📖 **Full guide**: Read `CUSTOM_TOOLS.md` in this directory for step-by-step
instructions, code templates, and best practices. Everything you need to add
new capabilities to the assistant without reading the entire project.

Quick start (3 steps):
    1. Create `<name>.py` with a @tool-decorated function
    2. Register in `tools/registry.py`
    3. Assign to the appropriate agent in `agents/`

Reference implementation: `github_trending.py` — a complete working example
of a web-scraping tool with language filtering and time range selection.
"""
