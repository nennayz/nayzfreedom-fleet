from __future__ import annotations


def get_tool_definitions() -> list[dict]:
    return [
        {
            "name": "run_mia",
            "description": "Research current trends relevant to the brief using Brave Search. Call this first.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_zoe",
            "description": "Generate 5-7 content ideas based on Mia's trend research.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_bella",
            "description": "Write the Reels script for the selected idea.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_lila",
            "description": "Generate the visual prompt and create the key image for the Reel.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_nora",
            "description": "QA review the script and visual. Returns pass/fail with optional feedback.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_roxy",
            "description": "Generate hashtags, caption, and optimal posting time.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "run_emma",
            "description": "Prepare FAQ markdown with pre-written community responses.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "request_checkpoint",
            "description": (
                "Pause pipeline and ask the user for input or approval. "
                "Use at: (1) after Zoe to pick idea, (2) after Bella+Lila to review content, "
                "(3) after Nora QA, (4) before publishing."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string", "description": "Checkpoint name, e.g. 'idea_selection'"},
                    "summary": {"type": "string", "description": "What to show the user"},
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Numbered options to present (optional)",
                    },
                },
                "required": ["stage", "summary"],
            },
        },
    ]
