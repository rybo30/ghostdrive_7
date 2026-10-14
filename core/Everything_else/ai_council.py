# =============================================================
# AI COUNCIL v8.1 — CHAT HISTORY & DYNAMIC TOKEN BUDGETING
# =============================================================
import json, os, re
from cryptography.fernet import Fernet
from model_registry import load_model_from_config

# --- CONFIGURATION & MAPPING ---
PRETTY_NAMES = {
    "jynx_summarizer": "Summary",
    "jynx_vision": "Vision Expert",
    "jynx_expert_logic": "Logic Expert",
    "jynx_expert_math": "Math Expert",
    "jynx_expert_coding": "Coding Expert",
    "jynx_expert_emotion": "Emotion Expert",
    "jynx_expert_survival": "Survival Expert",
    "jynx_expert_finance": "Finance Expert",
    "jynx_expert_psychology": "Psychology Expert",
    "jynx_expert_medical": "Medical Expert",
    "jynx_expert_cyber": "Cybersecurity Expert",
    "jynx_expert_mental_health": "Mental Health Expert",
    "jynx_expert_history": "History Expert",
    "jynx_expert_politics": "Political Expert",
    "jynx_expert_sarcasm": "People Expert",
    "jynx_expert_conspiracy": "Conspiracy Intelligence Expert",
    "jynx_expert_criminal": "Crime Expert",
    "jynx_expert_business": "Business Strategist Expert",
    "jynx_expert_physics": "Physics Expert",
    "jynx_expert_robotics": "Robotics & Automation Expert",
    "jynx_expert_agriculture": "Agricultural & Homesteading Expert",
    "jynx_expert_advocate": "Devil's Advocate",
    "jynx_expert_quant_finance": "Quantitative Finance Expert",
    "jynx_expert_creative": "Creative Strategy Expert",
    "jynx_expert_astrology": "Systems Metaphysics Expert",
    "jynx_expert_advanced_math": "Advanced Math Expert",
    "jynx_expert_malicious_analysis": "Threat Simulation Expert",
    "jynx_expert_mopey_psych": "Critical Realism Expert",
    "jynx_expert_spiritual": "Philosophy & Spiritual Expert",
    "jynx_expert_systems": "Systems Architecture Expert",
    "jynx_expert_legal": "Legal & Regulatory Expert",
    "jynx_expert_logistics": "Logistics & Operations Expert",
    "jynx_expert_negotiation": "Negotiation & Influence Expert",
    "jynx_expert_futurist": "Macro Futurist Expert",
    "jynx_judge": "Final Verdict",
}

EXPERT_MAP = {
    "logic": "jynx_expert_logic",
    "math": "jynx_expert_math",
    "coding": "jynx_expert_coding",
    "emotion": "jynx_expert_emotion",
    "survival": "jynx_expert_survival",
    "finance": "jynx_expert_finance",
    "psychology": "jynx_expert_psychology",
    "medical": "jynx_expert_medical",
    "cyber": "jynx_expert_cyber",
    "mental health": "jynx_expert_mental_health",
    "history": "jynx_expert_history",
    "politics": "jynx_expert_politics",
    "people": "jynx_expert_sarcasm",
    "conspiracy": "jynx_expert_conspiracy",
    "crime": "jynx_expert_criminal",
    "business": "jynx_expert_business",
    "physics": "jynx_expert_physics",
    "robotics": "jynx_expert_robotics",
    "agriculture": "jynx_expert_agriculture",
    "advocate": "jynx_expert_advocate",
    "quant finance": "jynx_expert_quant_finance",
    "creative": "jynx_expert_creative",
    "astrology": "jynx_expert_astrology",
    "advanced math": "jynx_expert_advanced_math",
    "threat simulation": "jynx_expert_malicious_analysis",
    "critical realism": "jynx_expert_mopey_psych",
    "spiritual": "jynx_expert_spiritual",
    "systems architecture": "jynx_expert_systems",
    "legal": "jynx_expert_legal",
    "logistics": "jynx_expert_logistics",
    "negotiation": "jynx_expert_negotiation",
    "futurist": "jynx_expert_futurist",
}

FIELD_DESCRIPTIONS = {
    "jynx_vision": "describing images and identifying what is seen",
    "jynx_expert_logic": "solving logic puzzles and finding logical flaws",
    "jynx_expert_math": "basic math, calculations, and word problems",
    "jynx_expert_coding": "writing code, fixing bugs, and software design",
    "jynx_expert_emotion": "offering comfort, empathy, and listening warmly",
    "jynx_expert_survival": "wilderness survival, off-grid living, and home defense",
    "jynx_expert_finance": "personal finance, business money management, and economy",
    "jynx_expert_psychology": "understanding human behavior and mental habits",
    "jynx_expert_medical": "first aid, emergency care, and how the body works",
    "jynx_expert_cyber": "digital security, firewall setups, and online safety",
    "jynx_expert_mental_health": "stress relief, coping skills, and emotional well-being",
    "jynx_expert_history": "historical facts, wars, and military history",
    "jynx_expert_politics": "political strategy, government, and opposing views",
    "jynx_expert_sarcasm": "understanding crowd behavior and people's motives",
    "jynx_expert_conspiracy": "spy tactics, government agencies, and hidden events",
    "jynx_expert_criminal": "crime investigation, clues, and detective work",
    "jynx_expert_business": "business plans, marketing, and company strategy",
    "jynx_expert_physics": "laws of motion, gravity, forces, and physical science",
    "jynx_expert_robotics": "building robots, motors, circuits, and automation",
    "jynx_expert_agriculture": "farming, raising animals, and gardening from scratch",
    "jynx_expert_advocate": "playing devil's advocate and finding holes in arguments",
    "jynx_expert_quant_finance": "advanced financial data, trading, and risk models",
    "jynx_expert_creative": "brainstorming unique ideas and outside-the-box thinking",
    "jynx_expert_astrology": "astrology charts, star patterns, and macro trends",
    "jynx_expert_advanced_math": "complex math proofs, calculus, and advanced statistics",
    "jynx_expert_malicious_analysis": "thinking like a hacker to test for system gaps",
    "jynx_expert_mopey_psych": "unfiltered, brutally realistic views on life and habits",
    "jynx_expert_spiritual": "ancient philosophy, stoicism, and finding peace of mind",
    "jynx_expert_systems": "networking, computer servers, and data pipeline setup",
    "jynx_expert_legal": "reading contracts, business laws, and avoiding lawsuits",
    "jynx_expert_logistics": "managing supply lines, timelines, and step-by-step projects",
    "jynx_expert_negotiation": "bargaining, persuasion, and dealing with partnerships",
    "jynx_expert_futurist": "predicting tech trends and future advancements",
}

def estimate_tokens(text: str) -> int:
    """Approximates standard LLM token counts based on a 4 char/token standard."""
    return len(text) // 4

def format_chat_log(chat_history: list) -> str:
    """Converts raw chat log sequences into a legible transcript block."""
    transcript = []
    for msg in chat_history:
        role = msg.get("role", "Unknown")
        content = msg.get("content", "").strip()
        # Strip internal UI HTML rendering tags if present
        content = re.sub(r"<[^>]*>", "", content)
        if content:
            sender = "Operator" if role.lower() == "you" else role
            transcript.append(f"{sender}: {content}")
    return "\n".join(transcript)

def get_user_profile_context(username, fernet):
    """Retrieves and formats the full 5W+H Neural Map."""
    try:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        vault_path = os.path.join(base_dir, "Everything_else", "vault", f"{username}_profile.enc")
        if not os.path.exists(vault_path):
            vault_path = os.path.join(base_dir, "core", "Everything_else", "vault", f"{username}_profile.enc")

        if os.path.exists(vault_path):
            with open(vault_path, "rb") as f:
                decrypted = fernet.decrypt(f.read())
                data = json.loads(decrypted)
                h = data.get("heuristics", {})
                
                map_fields = {
                    "WHO": ["callsign", "identity", "values", "inner_circle", "social_iq"],
                    "WHAT": ["vocation", "projects", "tech_stack", "limitations", "habits"],
                    "WHERE": ["region", "workspace", "travel", "digital_loc"],
                    "WHEN": ["peak_performance", "deadlines", "timeline", "history"],
                    "WHY": ["motivations", "fear", "ghostdrive_why", "victory_condition"],
                    "HOW": ["logic", "learning_pref", "decision_engine", "tone_pref"]
                }

                context = "\n[OPERATOR PERSONALITY MAP]\n"
                found_data = False
                for category, keys in map_fields.items():
                    category_text = ""
                    for k in keys:
                        val = h.get(k)
                        if val and str(val).strip():
                            label = k.replace("_", " ").title()
                            category_text += f"  - {label}: {val}\n"
                    
                    if category_text:
                        context += f"[{category}]\n{category_text}"
                        found_data = True
                
                return context if found_data else f"\n[OPERATOR PERSONALITY MAP]\nCallsign: {username}\n"
    except Exception: pass
    return f"\n[OPERATOR PERSONALITY MAP]\nCallsign: {username}\n"


# --- THE MAIN UPDATED STREAM WORKFLOW ---
def run_council_streaming(user_prompt, image_path=None, username="Operator", fernet=None, chat_history=None):
    previous_notes = ""
    full_neural_map = get_user_profile_context(username, fernet) if fernet else f"\n[OPERATOR PERSONALITY MAP]\nCallsign: {username}\n"
    
    # 1. Parse and copy history safely so we don't truncate user logs on disk
    if chat_history is None:
        chat_history = []
    working_history = list(chat_history)
    
    # Extract the real context capability from your judge configuration profile
    _, judge_config = load_model_from_config("jynx_judge")
    MAX_CONTEXT_WINDOW = judge_config.get("actual_ctx_window", 4096)
    MAX_RESPONSE_RESERVE = 1024 
    
    # Calculate fixed overhead bounds
    neural_overhead = estimate_tokens(full_neural_map)
    prompt_overhead = estimate_tokens(user_prompt)
    
    # SLIDING WINDOW SLIDER: Evict oldest turns until the transcript fits safely
    while working_history:
        full_chat_log_block = "\n[CONVERSATION HISTORY LOG]\n" + format_chat_log(working_history)
        chat_overhead = estimate_tokens(full_chat_log_block)
        
        total_footprint = neural_overhead + chat_overhead + prompt_overhead + MAX_RESPONSE_RESERVE
        if total_footprint <= MAX_CONTEXT_WINDOW:
            break
            
        working_history.pop(0)  # Evict oldest entry from memory stack
        
    # Re-finalize the context string using the safely minimized timeline history
    full_chat_log_block = "\n[CONVERSATION HISTORY LOG]\n" + format_chat_log(working_history)
    chat_overhead = estimate_tokens(full_chat_log_block)
    
    # Recalculate dynamic budget boundaries
    allowed_notes_budget = MAX_CONTEXT_WINDOW - (neural_overhead + chat_overhead + prompt_overhead + MAX_RESPONSE_RESERVE)
    if allowed_notes_budget < 500:
        allowed_notes_budget = 500

    # === 0. VISION ===
    if image_path:
        yield ("expert_start", "Vision Expert")
        vision_prompt = f"{full_neural_map}\n{full_chat_log_block}\nAnalyze visual data for: {user_prompt}"
        try:
            llm_fn, _ = load_model_from_config("jynx_vision")
            vision_buffer = ""
            for token in llm_fn(vision_prompt, image_path=image_path, stream_override=True):
                if token:
                    vision_buffer += token
                    yield ("expert_token", "Vision Expert", token)
            previous_notes += f"Vision Analysis: {vision_buffer}\n\n"
            yield ("expert_done", "Vision Expert", vision_buffer)
        except Exception as e:
            previous_notes += f"Vision Error: {str(e)}\n"

    # === 1. SUMMARIZER, ROUTING & NEURAL FILTERING ===
    summarizer_prompt = f"""
{full_neural_map}
{full_chat_log_block}

TASK: Analyze the "Current Input" given the conversation context.
1. Provide a 1-sentence summary of the user's current intent.
2. Select the 3 most relevant experts from the ALLOWED list.
3. Identify which Personality Map categories (WHO, WHAT, WHERE, WHEN, WHY, HOW) are essential for this specific request.

ALLOWED EXPERTS: Logic, Math, Coding, Emotion, Survival, Finance, Psychology, Medical, Cyber, History, People, Politics, Mental Health, Crime, Conspiracy, Business, Physics, Robotics, Agriculture, Advocate, Quant Finance, Creative, Astrology, Advanced Math, Threat Simulation, Critical Realism, Spiritual, Systems Architecture, Legal, Logistics, Negotiation, Futurist.

EXACT OUTPUT FORMAT:
SUMMARY: <brief summary>
EXPERTS: <list of experts>
PERSONALITY MAP: <list of categories>

Current Input: "{user_prompt}"
Response:"""

    llm_fn, _ = load_model_from_config("jynx_summarizer")
    summary_buffer = ""

    for token in llm_fn(
        summarizer_prompt, 
        stream_override=True, 
        max_tokens=200, 
        temperature=0.1,
        stop=["---", "Operator:", "User:", "TASK:"]
    ):
        if token:
            summary_buffer += token
            if "TASK:" in summary_buffer:
                break  # Hard crash out if model attempts to repeat instructions
                
            display_token = token.replace("SUMMARY:", "**Target:**").replace("EXPERTS:", "\n**Experts:**")
            yield ("summary", display_token)
            
    yield ("summary_done", summary_buffer)

    # === 2. EXTRACT RELEVANT EXPERTS & CONTEXT ===
    expert_ids = []
    search_text = summary_buffer.lower()
    for keyword, model_id in EXPERT_MAP.items():
        if keyword in search_text.split("relevant_map:")[0]:
            expert_ids.append(model_id)
    expert_ids = list(dict.fromkeys(expert_ids))[:3]
    if not expert_ids:
        expert_ids = ["jynx_expert_logic", "jynx_expert_psychology"]

    active_categories = []
    map_search = summary_buffer.upper().split("RELEVANT_MAP:")[-1]
    for cat in ["WHO", "WHAT", "WHERE", "WHEN", "WHY", "HOW"]:
        if cat in map_search:
            active_categories.append(cat)
    
    filtered_context = "[OPERATOR PERSONALITY MAP (Active Context Only)]\n"
    if active_categories:
        for cat in active_categories:
            start_tag = f"[{cat}]"
            if start_tag in full_neural_map:
                part = full_neural_map.split(start_tag)[1].split("[")[0]
                filtered_context += f"{start_tag}{part}"
    else:
        filtered_context = full_neural_map

    # === 3. SEQUENTIAL EXPERT LOOP ===
    for expert_id in expert_ids:
        expert_name = PRETTY_NAMES.get(expert_id, expert_id)
        field = FIELD_DESCRIPTIONS.get(expert_id, "expertise")
        yield ("expert_start", expert_name)

        # Dynamic Window Guard Formula
        notes_lines = previous_notes.strip().split("\n\n")
        while notes_lines and estimate_tokens("\n\n".join(notes_lines)) > allowed_notes_budget:
            notes_lines.pop(0) 
        budgeted_notes = "\n\n".join(notes_lines)

        expert_prompt = f"""{filtered_context}
{full_chat_log_block}

Persona: You are the {expert_name}, an expert in {field}. 

Previous Insights from Council Members: 
{budgeted_notes or "You are the lead expert for this turn."}

User Request: "{user_prompt}"

Task:
1. Provide a direct, short perspective from your unique expertise in {field}. 
2. Address the user naturally. Do NOT quote, list, or repeat any tags/content from the Personality Map or Chat Logs.
3. Provide your analysis immediately. Do NOT include headers, meta-commentary, or introductory remarks.

Response:"""

        llm_fn, _ = load_model_from_config(expert_id)
        expert_buffer = ""
        
        for token in llm_fn(
            expert_prompt, 
            stream_override=True, 
            max_tokens=400, 
            temperature=0.7, 
            stop=["User:", "You:", "Operator:", "[OPERATOR", "\n[", "[PREVIOUS", "Previous Insights:"]
        ):
            if token:
                expert_buffer += token
                
                # Double guard check to instantly crash out if a structural tag slips through
                if "[OPERATOR" in expert_buffer or "[WHAT]" in expert_buffer or "[WHY]" in expert_buffer:
                    break
                    
                yield ("expert_token", expert_name, token)
        
        clean_buffer = expert_buffer.split("[OPERATOR")[0].split("\n[")[0].strip()
        previous_notes += f"[{expert_name}]: {clean_buffer}\n\n"
        yield ("expert_done", expert_name, clean_buffer)

    # === 4. FINAL VERDICT ===
    yield ("verdict_start", "")
    
    notes_lines = previous_notes.strip().split("\n\n")
    while notes_lines and estimate_tokens("\n\n".join(notes_lines)) > allowed_notes_budget:
        notes_lines.pop(0)
    budgeted_notes = "\n\n".join(notes_lines)

    verdict_prompt = f"""{filtered_context}
{full_chat_log_block}

Review the Council's notes alongside the multi-turn exchange history and provide a final synthesis.

Notes:
{budgeted_notes}

Format:
**Final Verdict:** [1-2 concise paragraphs]
**Actionable Takeaways:**
- [Step]
- [Step]
- [Step]

Verdict:"""
    
    llm_fn, _ = load_model_from_config("jynx_judge")
    for token in llm_fn(verdict_prompt, stream_override=True, max_tokens=800, temperature=0.2):
        if token:
            yield ("verdict_token", token)
            
    yield ("done", "")