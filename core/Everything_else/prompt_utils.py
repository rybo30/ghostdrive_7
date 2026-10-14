from prompt_builder import build_dynamic_system_prompt

TRIGGER_INSTRUCTION = (
    "### TOOL USE RULES ###\n"
    "When taking an action would help, write this exact phrase on its own line:\n"
    "Activating <protocol> protocol\n"
    "(use one at a time)\n"
)

def build_system_prompt(context_data, topic_context, mode_desc, current_user_prompt=None):
    base = build_dynamic_system_prompt(context_data, topic_context, mode_desc, current_user_prompt)
    return base.strip() + "\n\n" + TRIGGER_INSTRUCTION

def remove_forced_endings(text):
    endings = [
        "do you understand?",
        "does that make sense?",
        "do you understand, commander?",
    ]
    for end in endings:
        if text.lower().strip().endswith(end):
            return text[: -len(end)].rstrip(" .,?!") + "."
    return text
