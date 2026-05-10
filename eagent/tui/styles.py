"""Style definitions for full-screen eagent TUI."""

from prompt_toolkit.styles import Style

TUI_STYLE = Style.from_dict(
    {
        "status": "bg:#1f2a44 #f2f6ff",
        "status.running": "bg:#1b4332 #e9ffef",
        "status.error": "bg:#5c1d1d #ffecec",
        "brand.rte": "#99f6e4",
        "brand.hyphen": "#99f6e4",
        "brand.ai": "bold #ffffff",
        "logo.subtitle": "#8ea0bc",
        "title": "bold #f3f7ff",
        "meta": "#d7e3ff",
        "input": "bg:#0f172a #f8fafc",
        "hint": "bg:#111827 #cbd5e1",
        "hint.text": "#cbd5e1",
        "activity": "bg:#0f1724 #9fb0c8",
        "activity.empty": "bg:#0f1724 #7d8ea8",
        "activity.running": "bg:#0f1724 #99a9bf",
        "activity.shine": "bg:#0f1724 #d9e3f2 bold",
        "activity.done": "bg:#0f1724 #7f8fa5",
        "activity.error": "bg:#201616 #ffcaca",
        "activity.ai_streaming": "bg:#0f1724 #22d3ee bold",
        "toolpanel": "bg:#101828 #d8e3ff",
        "toolpanel.empty": "bg:#101828 #8ea0c2",
        "toolpanel.summary": "bg:#101828 #d8e3ff",
        "toolpanel.detail": "bg:#0d1428 #c6d4f5",
        "toolpanel.error": "bg:#2b1a1a #ffcccc",
        "transcript": "bg:#0b1020 #e6edf7",
        "transcript.streaming_cursor": "#22d3ee nounderline blink",
        "transcript.system": "#6b7a90",
        "transcript.ai_idle_prompt": "#8ecbff blink",
        "user": "#8ecbff",
        "assistant.pending": "#74869f",
        "assistant": "#f8fafc",
        "tool": "#facc15",
        "error": "bold #f87171",
        "dim": "#94a3b8",
    }
)
