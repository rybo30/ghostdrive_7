# prompt_builder.py
def filter_training_by_prompt(prompt, training_data, max_lines=8):
    filtered = []
    prompt_lower = prompt.lower()

    for tag, lines in training_data.items():
        if tag in prompt_lower:
            for line in lines:
                filtered.append(f"- ({tag}) {line}")

    return filtered[:max_lines]  # Limit to avoid overfitting the prompt

def filter_memory_by_prompt(prompt, memory_entries, max_lines=5):
    prompt_lower = prompt.lower()
    results = []

    for entry in memory_entries:
        tags = entry.get("tags", [])
        if any(tag.lower() in prompt_lower for tag in tags):
            results.append(f"- {entry['text']}")

    return results[:max_lines]


def build_dynamic_system_prompt(context_data, topic_context="", mode_desc="", user_prompt=""):
    sections = []

    def format_kv_block(title, data):
        if not isinstance(data, dict):
            return f"### {title.upper()}\n{str(data).strip()}"
        lines = [f"- {k}: {v}" for k, v in data.items()]
        return f"### {title.upper()}\n" + "\n".join(lines)

    # 1. Soul – inject everything in soul.json
    soul_data = context_data.get("soul", {})
    if soul_data:
        sections.append(format_kv_block("soul", soul_data))

    # 2. Topic context (optional)
    if topic_context:
        sections.append(f"### TOPIC CONTEXT\n{topic_context.strip()}")

    # 3. Memory – inject relevant facts based on user prompt
    memory_entries = context_data.get("memory", [])
    if memory_entries and user_prompt:
        filtered_memory = filter_memory_by_prompt(user_prompt, memory_entries)
        if filtered_memory:
            sections.append("### MEMORY\n" + "\n".join(filtered_memory))


    # 4. Training – inject only matching tagged training lines
    training_data = context_data.get("training", {})
    if training_data and user_prompt:
        filtered_training = filter_training_by_prompt(user_prompt, training_data)
        if filtered_training:
            sections.append("### TRAINING\n" + "\n".join(filtered_training))


    # 5. Situation
    situation_data = context_data.get("situation", {})
    if situation_data:
        sections.append(format_kv_block("situation", situation_data))

    # 6. Backstory
    backstory_data = context_data.get("backstory", {})
    if backstory_data:
        sections.append(format_kv_block("backstory", backstory_data))

    # 7. Mode
    if mode_desc:
        sections.append(f"### MODE\n{mode_desc.strip()}")

    # Final system prompt
    return "\n\n".join(sections).strip()
