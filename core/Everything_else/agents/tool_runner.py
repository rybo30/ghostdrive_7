# tool_runner.py

import os
import sys
import json
import re
import logging
import importlib.util
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from core.paths import AGENT_TOOLS_DIR, USB_TOOLS_DIR, EVERYTHING_ELSE, HOST_HIDDEN_DIR
from core.Everything_else.agents.ram_manager import RAMManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ToolRunner")


class ToolRegistry:
    """Dynamically loads and manages executable python tools directly from host storage."""
    def __init__(self, tools_dir: Optional[str] = None):
        self.tools_dir = tools_dir or AGENT_TOOLS_DIR
        self.usb_tools_dir = USB_TOOLS_DIR
        self.tools: Dict[str, Any] = {}
        self.load_tools()

    def load_tools(self):
        """Scans unique tool directories and registers available modules with TOOL_SPEC."""
        directories_to_scan = list(set([
            os.path.abspath(self.tools_dir),
            os.path.abspath(self.usb_tools_dir)
        ]))
        
        for search_dir in directories_to_scan:
            if not os.path.exists(search_dir):
                continue

            for filename in os.listdir(search_dir):
                if filename.endswith(".py") and not filename.startswith("__"):
                    module_name = filename[:-3]
                    file_path = os.path.join(search_dir, filename)
                    
                    try:
                        spec = importlib.util.spec_from_file_location(module_name, file_path)
                        if spec and spec.loader:
                            mod = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(mod)
                            
                            run_fn = getattr(mod, "run", getattr(mod, "execute", None))
                            
                            if hasattr(mod, "TOOL_SPEC") and run_fn is not None:
                                tool_name = mod.TOOL_SPEC["name"]
                                if tool_name not in self.tools:
                                    self.tools[tool_name] = {
                                        "spec": mod.TOOL_SPEC,
                                        "run": run_fn,
                                        "file_path": file_path
                                    }
                                    logger.info(f"[ToolRegistry] Loaded tool: {tool_name}")
                    except Exception as e:
                        logger.error(f"[ToolRegistry] Failed loading tool {filename}: {e}")

    def get_tool_specs(self) -> List[Dict[str, Any]]:
        """Returns OpenAPI-style JSON specs for all registered tools."""
        return [tool_data["spec"] for tool_data in self.tools.values()]

    def execute_tool(self, tool_name: str, **kwargs) -> str:
        """Executes a loaded tool by name with provided parameters."""
        if tool_name not in self.tools:
            return f"Error: Tool '{tool_name}' is not registered."
        
        try:
            return str(self.tools[tool_name]["run"](**kwargs))
        except Exception as e:
            logger.error(f"[ToolRegistry] Execution error in {tool_name}: {e}")
            return f"Error executing tool '{tool_name}': {str(e)}"

    def get_tool_summaries(self) -> List[Dict[str, str]]:
        """Returns a lightweight name/description list for Stage 1 system prompts."""
        return [
            {
                "name": data["spec"].get("name", ""),
                "description": data["spec"].get("description", "")
            }
            for data in self.tools.values()
        ]


class AgentToolRunner:
    """Multi-stage orchestration engine supporting Intent Analysis, Tool Branching, and Response Proofreading."""
    def __init__(self, ram_manager: RAMManager, max_tokens: int = 1536):
        self.ram_manager = ram_manager
        self.registry = ToolRegistry()
        self.max_tokens = max_tokens

    def process_task(
        self, 
        prompt: str, 
        model_filename: Optional[str] = None, 
        system_prompt: str = "", 
        user_history: Optional[List[str]] = None,
        allowed_tools: Optional[List[str]] = None
    ) -> Union[str, List[str]]:
        """Algorithm 1: Reactive algorithm for handling user prompts."""
        current_time_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

        self.registry.load_tools()

        if allowed_tools is not None:
            active_tools = [t for t in allowed_tools if t in self.registry.tools]
        else:
            active_tools = list(self.registry.tools.keys())

        deterministic_tools = self._smart_tool_fallback(prompt, active_tools)

        stage1_meta = self._stage_1_intent_and_tool_classification(
            prompt=prompt, 
            model_filename=model_filename, 
            current_time_str=current_time_str, 
            user_history=user_history, 
            active_tools=active_tools
        )
    
        model_tools = stage1_meta.get("tools", [])
        if not isinstance(model_tools, list):
            model_tools = []

        combined_tools = list(dict.fromkeys(model_tools + deterministic_tools))
        valid_tools = [t for t in combined_tools if t in active_tools]

        needs_tools = len(valid_tools) > 0 or (stage1_meta.get("needs_tools", False) and len(valid_tools) > 0)
        intent = stage1_meta.get("intent", prompt)

        logger.info(f"[Agent] Stage 1 Final Decision -> needs_tools: {needs_tools}, tools: {valid_tools}")

        if needs_tools and valid_tools:
            logger.info(f"[Agent] Stage 2: Executing Multi-Tool Workflow -> {valid_tools}")
            draft_response = self._stage_2_tool_workflow(prompt, valid_tools, intent, model_filename, current_time_str, user_history)
            return [self._clean_response_string(draft_response)]
        else:
            logger.info("[Agent] Stage 2: Executing Direct Response Branch")
            draft_response = self._stage_2_direct_response_workflow(prompt, intent, system_prompt, model_filename, current_time_str, user_history)

        logger.info("[Agent] Stage 3: Proofreading and Partitioning Output...")
        final_responses = self._stage_3_proofread_and_split(prompt, draft_response, system_prompt, model_filename)

        return final_responses



    def process_autonomous_workshop(
        self, 
        chat_history: List[Dict[str, str]], 
        user_profile: Dict[str, Any],
        active_projects: List[str],
        model_filename: Optional[str] = None,
        system_prompt: str = "",
        allowed_tools: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        6-Stage Proactive Autonomous Pipeline:
        1. Load Projects & Past Proactive Memory (State Cycling)
        2. Synthesize Recent Conversation Context
        3. Strategic Action & Tool Decision
        4. Tool Execution
        5. Proofread & Format Output
        6. Persist Session State for Next Cycle
        """
        current_time_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        self.registry.load_tools()

        host_projects_dir = getattr(
            __import__("core.paths", fromlist=["HOST_PROJECTS_DIR"]),
            "HOST_PROJECTS_DIR",
            os.path.join(HOST_HIDDEN_DIR, "projects")
        )

        # --- STAGE 1: STATE & PROJECT INVENTORY (INCLUDING PAST PROACTIVE MEMORY) ---
        logger.info("[Proactive Pipeline] Stage 1: Loading projects and past memory...")
        projects_data = {}
        if os.path.exists(host_projects_dir):
            for entry in os.listdir(host_projects_dir):
                proj_path = os.path.join(host_projects_dir, entry)
                if os.path.isdir(proj_path):
                    meta_file = os.path.join(proj_path, "project.json")
                    memory_file = os.path.join(proj_path, "proactive_memory.json")
                    
                    proj_info = {}
                    if os.path.exists(meta_file):
                        try:
                            with open(meta_file, "r", encoding="utf-8") as f:
                                proj_info["meta"] = json.load(f)
                        except Exception:
                            pass
                    
                    # Load past proactive cycle memory for continuity (Stage 6 link)
                    if os.path.exists(memory_file):
                        try:
                            with open(memory_file, "r", encoding="utf-8") as f:
                                proj_info["past_memory"] = json.load(f)
                        except Exception:
                            pass
                    
                    projects_data[entry] = proj_info

        # --- STAGE 2: CONTEXT & HISTORY SYNTHESIS ---
        logger.info("[Proactive Pipeline] Stage 2: Synthesizing conversation context...")
        history_str = "\n".join([f"- {msg.get('role', 'user').capitalize()}: {msg.get('text', '')}" for msg in chat_history]) if chat_history else "No recent chat history."
        
        context_prompt = f"""You are analyzing recent user interactions to determine potential needs.
Recent Chat History:
{history_str}

Provide a concise 2-sentence summary of the user's recent momentum, focus areas, and open loops."""
        
        try:
            conversation_insight = self.ram_manager.generate_response(
                prompt=context_prompt,
                model_filename=model_filename,
                max_tokens=256
            ).strip()
        except Exception:
            conversation_insight = "User is maintaining standard operational workflow."

        # --- STAGE 3: STRATEGY & TOOL SELECTION ---
        logger.info("[Proactive Pipeline] Stage 3: Determining strategy and required tools...")
        available_specs = [t for t in self.registry.get_tool_summaries() if not allowed_tools or t["name"] in allowed_tools]

        strategy_prompt = f"""You are the Strategic Decision Engine for an autonomous AI partner.
Current Time: {current_time_str}
Active Projects & Past Memory: {json.dumps(projects_data, indent=2)}
User Context Insight: {conversation_insight}

Available Tools:
{json.dumps(available_specs, indent=2)}

INSTRUCTIONS:
Determine what proactive action should be taken right now to assist the user or advance their projects.
If a tool is needed, specify the `tool_name` and exact `tool_args`. If no tool is needed, set `tool_name` to null.

Respond STRICTLY in JSON:
```json
{{
  "thought": "Reasoning for the proactive step",
  "target_project": "project_name_if_applicable",
  "tool_name": "tool_name_or_null",
  "tool_args": {{}},
  "briefing_focus": "Key points to present to the user"
}}
```"""

        try:
            strategy_res = self.ram_manager.generate_response(
                prompt=strategy_prompt,
                model_filename=model_filename,
                max_tokens=512
            )
            strategy = self._parse_json_action(strategy_res) or {}
        except Exception as e:
            logger.error(f"[Proactive Pipeline] Stage 3 error: {e}")
            strategy = {}

        tool_name = strategy.get("tool_name")
        tool_args = strategy.get("tool_args", {})
        target_project = strategy.get("target_project", "")
        briefing_focus = strategy.get("briefing_focus", "Routine system and project check-in.")

        # --- STAGE 4: EXECUTION ---
        tool_output = "No tool executed."
        if tool_name and tool_name in self.registry.tools:
            logger.info(f"[Proactive Pipeline] Stage 4: Executing tool '{tool_name}' with args {tool_args}")
            try:
                tool_output = self.registry.execute_tool(tool_name, **tool_args)
            except Exception as e:
                tool_output = f"Tool execution failed: {str(e)}"

        # --- STAGE 5: PROOFREADING & FORMATTING ---
        logger.info("[Proactive Pipeline] Stage 5: Proofreading briefing for user...")
        draft_prompt = f"""Synthesize a crisp, high-signal proactive briefing for the user based on the workshop execution.

Briefing Focus: {briefing_focus}
Tool Execution Result: {tool_output}
Project States: {json.dumps(projects_data, indent=2)}

STRICT RULES:
- Zero motivational filler or fluff.
- Focus strictly on facts, project status updates, and valuable insights.
- Format cleanly for Telegram messaging.

Briefing:"""

        try:
            draft_text = self.ram_manager.generate_response(
                prompt=draft_prompt,
                model_filename=model_filename,
                max_tokens=self.max_tokens
            ).strip()

            final_responses = self._stage_3_proofread_and_split(
                prompt="Proactive autonomous briefing",
                draft_response=draft_text,
                system_prompt=system_prompt,
                model_filename=model_filename
            )
            final_message = "\n\n".join(final_responses)
        except Exception as e:
            logger.error(f"[Proactive Pipeline] Stage 5 error: {e}")
            return None

        # --- STAGE 6: STATE PERSISTENCE & CYCLING ---
        logger.info("[Proactive Pipeline] Stage 6: Saving session state for next cycle...")
        if target_project:
            slug = re.sub(r'[-\s]+', '_', re.sub(r'[^\w\s-]', '', target_project.lower()).strip())
            proj_folder = os.path.join(host_projects_dir, slug)
            if os.path.exists(proj_folder):
                memory_file = os.path.join(proj_folder, "proactive_memory.json")
                session_record = {
                    "timestamp": current_time_str,
                    "focus": briefing_focus,
                    "tool_used": tool_name,
                    "tool_output": tool_output,
                    "summary": final_message
                }
                try:
                    history_log = []
                    if os.path.exists(memory_file):
                        with open(memory_file, "r", encoding="utf-8") as f:
                            history_log = json.load(f)
                    history_log.append(session_record)
                    # Keep last 5 sessions for continuous rolling memory
                    history_log = history_log[-5:]
                    with open(memory_file, "w", encoding="utf-8") as f:
                        json.dump(history_log, f, indent=2)
                    logger.info(f"[Proactive Pipeline] Stage 6 complete: Saved memory to {slug}/proactive_memory.json")
                except Exception as ex:
                    logger.error(f"[Proactive Pipeline] Stage 6 save error: {ex}")

        return final_message




    def _stage_1_intent_and_tool_classification(
        self,
        prompt: str,
        model_filename: Optional[str],
        current_time_str: str,
        user_history: Optional[List[str]],
        active_tools: List[str]
    ) -> Dict[str, Any]:
        """Evaluates incoming user prompts for standard reactive handling."""
        available_specs = [
            t for t in self.registry.get_tool_summaries()
            if t["name"] in active_tools
        ]
        history_str = self._format_user_history(user_history)

        eval_prompt = f"""You are an Intent Analysis Engine. Analyze the user's request and determine if external tools are required.
Current Date: {current_time_str}

{history_str}Available Tools:
{json.dumps(available_specs, indent=2)}

User Request: "{prompt}"

Output STRICTLY JSON:
```json
{{
  "needs_tools": true,
  "intent": "Core request summary",
  "tools": ["tool_name"]
}}
```"""
        try:
            raw_res = self.ram_manager.generate_response(
                prompt=eval_prompt,
                model_filename=model_filename,
                max_tokens=256
            )
            parsed = self._parse_json_action(raw_res)
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            logger.error(f"Stage 1 Classification Error: {e}")

        return {"needs_tools": False, "intent": prompt, "tools": []}

    def _format_user_history(self, user_history: Optional[List[str]]) -> str:
        if not user_history:
            return ""
        formatted = "\n".join([f"- Previous User Input: \"{msg}\"" for msg in user_history])
        return f"Recent Conversation Context:\n{formatted}\n\n"

    def _stage_2_tool_workflow(
        self, 
        prompt: str, 
        tools: List[str], 
        intent: str, 
        model_filename: Optional[str], 
        current_time_str: str,
        user_history: Optional[List[str]] = None
    ) -> str:
        aggregated_outputs = []
        history_str = self._format_user_history(user_history)

        for tool_name in tools:
            if tool_name not in self.registry.tools:
                continue
            tool_spec = self.registry.tools[tool_name]["spec"]
            
            param_prompt = f"""You are a Tool Parameter Extractor for `{tool_name}`.
Current Date: {current_time_str}

{history_str}Tool Specification:
{json.dumps(tool_spec, indent=2)}

Task/Request: "{prompt}"

Extract keyword arguments matching the Tool Specification schema.
Output STRICTLY JSON:
```json
{{
  "kwargs": {{}}
}}
```"""

            try:
                param_raw = self.ram_manager.generate_response(
                    prompt=param_prompt,
                    model_filename=model_filename,
                    max_tokens=256
                )
                parsed_params = self._parse_json_action(param_raw)
                kwargs = parsed_params.get("kwargs", {}) if isinstance(parsed_params, dict) else {}

                if isinstance(parsed_params, dict) and "kwargs" not in parsed_params:
                    kwargs = parsed_params

                if not kwargs:
                    parameters_schema = tool_spec.get("parameters", {}).get("properties", {})
                    required_params = tool_spec.get("parameters", {}).get("required", [])
                    
                    for req_param in required_params:
                        param_type = parameters_schema.get(req_param, {}).get("type", "string")
                        if param_type == "string":
                            kwargs[req_param] = prompt
                        elif param_type == "array":
                            kwargs[req_param] = [prompt]

                for k, v in kwargs.items():
                    if isinstance(v, str) and "," in v:
                        param_schema = tool_spec.get("parameters", {}).get("properties", {}).get(k, {})
                        if param_schema.get("type") == "array":
                            kwargs[k] = [item.strip() for item in v.split(",") if item.strip()]

                logger.info(f"[Agent] Executing {tool_name} with parameters: {kwargs}")
                raw_output = self.registry.execute_tool(tool_name, **kwargs)
                aggregated_outputs.append(f"=== TOOL OUTPUT ({tool_name}) ===\n{raw_output}")

            except Exception as e:
                logger.error(f"Stage 2 Tool Execution Error ({tool_name}): {e}")
                aggregated_outputs.append(f"=== TOOL OUTPUT ({tool_name}) ===\nError executing tool: {str(e)}")

        combined_tool_context = "\n\n".join(aggregated_outputs)

        extracted_urls = []
        raw_urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', combined_tool_context)
        for u in raw_urls:
            clean_u = u.rstrip('.,);]')
            if clean_u not in extracted_urls and not clean_u.endswith(("N/A", "N/A/")):
                extracted_urls.append(clean_u)

        synthesis_prompt = f"""Synthesize a complete and helpful response based strictly on the tool execution outputs.
CRITICAL INSTRUCTIONS:
- Do NOT include inline URLs inside your core narrative text.
- Rely on the facts present in the Tool Outputs.

Current Date: {current_time_str}
{history_str}Task: {prompt}

{combined_tool_context}

Synthesis Response:"""

        try:
            synthesized_text = self.ram_manager.generate_response(
                prompt=synthesis_prompt,
                model_filename=model_filename,
                max_tokens=self.max_tokens
            ).strip()

            if extracted_urls:
                sources_block = "\n\n**Sources:**\n" + "\n".join([f"• {url}" for url in extracted_urls[:5]])
                synthesized_text += sources_block

            return synthesized_text

        except Exception as e:
            logger.error(f"Stage 2 Multi-Tool Synthesis Error: {e}")
            return f"Error synthesizing tool outputs: {str(e)}\n\nRaw Outputs:\n{combined_tool_context}"

    def _stage_2_direct_response_workflow(
        self, 
        prompt: str, 
        intent: str, 
        system_prompt: str, 
        model_filename: Optional[str], 
        current_time_str: str,
        user_history: Optional[List[str]] = None
    ) -> str:
        history_str = self._format_user_history(user_history)

        direct_prompt = f"""System Persona & Directives:
{system_prompt if system_prompt else "You are a helpful AI assistant."}

Today's Date: {current_time_str}
Intent: {intent}

{history_str}Task / Request: {prompt}

Response:"""
        try:
            return self.ram_manager.generate_response(
                prompt=direct_prompt,
                model_filename=model_filename,
                max_tokens=self.max_tokens
            ).strip()
        except Exception as e:
            logger.error(f"Stage 2 Direct Response Error: {e}")
            return f"Error generating response: {str(e)}"

    def _clean_response_string(self, text: str) -> str:
        if not isinstance(text, str):
            text = str(text)

        cleaned = text.strip()
        while (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()

        cleaned = cleaned.replace('\\"', '"').replace("\\'", "'")
        return cleaned.strip()

    def _stage_3_proofread_and_split(
        self, 
        prompt: str, 
        draft_response: str, 
        system_prompt: str, 
        model_filename: Optional[str]
    ) -> List[str]:
        if draft_response.startswith("{") and draft_response.endswith("}"):
            parsed = self._parse_json_action(draft_response)
            if isinstance(parsed, dict):
                draft_response = self._extract_text_from_dict(parsed)

        persona_directives = system_prompt if system_prompt and system_prompt.strip() else "You are a helpful AI assistant."

        proofread_prompt = f"""System Persona & Directives:
{persona_directives}

Format the draft into clean plain text for messaging while adhering strictly to the System Persona & Directives.

STRICT RULES:
1. Maintain the specified persona, tone, vocabulary, and response style.
2. Return a JSON array containing between 1 AND 2 plain text message strings.
3. Preserve all URLs and source references.

Task Context: "{prompt}"

Draft Response:
{draft_response}

Output format:
```json
[
  "First message block...",
  "Second message block..."
]
```"""

        try:
            raw_proof = self.ram_manager.generate_response(
                prompt=proofread_prompt,
                model_filename=model_filename,
                max_tokens=self.max_tokens
            )
            parsed = self._parse_json_action(raw_proof)
            if isinstance(parsed, list) and len(parsed) > 0:
                cleaned = []
                for item in parsed[:2]:
                    raw_str = self._extract_text_from_dict(item) if isinstance(item, dict) else str(item)
                    cleaned_str = self._clean_response_string(raw_str)
                    if cleaned_str:
                        cleaned.append(cleaned_str)
                return cleaned if cleaned else [self._clean_response_string(draft_response)]
        except Exception as e:
            logger.error(f"Stage 3 Proofread Error: {e}")

        return [self._clean_response_string(draft_response)]

    def _extract_text_from_dict(self, data: Dict[str, Any]) -> str:
        parts = []
        for k, v in data.items():
            if k in ["message", "response", "text", "content"] and isinstance(v, str):
                parts.append(v)
            elif isinstance(v, dict):
                parts.append(self._extract_text_from_dict(v))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        parts.append(self._extract_text_from_dict(item))
                    else:
                        parts.append(str(item))
            else:
                parts.append(f"{k}: {v}")
        return "\n".join(parts)

    def _smart_tool_fallback(self, prompt: str, active_tools: List[str]) -> List[str]:
        clean_prompt = prompt.lower()
        matched = []

        trigger_phrases = {
            "web_search_tool": ["search the web", "search for", "google", "look up", "find news", "news stories", "take a look"],
            "weather_tool": ["weather", "temperature", "forecast"],
            "market_data_tool": ["stock price", "market news", "ticker", "shares", "stock market", "stocks"],
            "system_health_tool": ["system health", "cpu load", "ram usage", "disk space"]
        }

        for tool_name, phrases in trigger_phrases.items():
            if tool_name in active_tools:
                if any(phrase in clean_prompt for phrase in phrases):
                    matched.append(tool_name)

        return matched

    def _parse_json_action(self, text: str) -> Optional[Union[Dict[str, Any], List[Any]]]:
        clean_text = text.strip()
        if "```json" in clean_text:
            clean_text = clean_text.split("```json")[1].split("```")[0]
        elif "```" in clean_text:
            clean_text = clean_text.split("```")[1].split("```")[0]
        clean_text = clean_text.strip()

        dict_start = clean_text.find("{")
        list_start = clean_text.find("[")

        if list_start != -1 and (dict_start == -1 or list_start < dict_start):
            list_end = clean_text.rfind("]")
            if list_end > list_start:
                try:
                    return json.loads(clean_text[list_start:list_end + 1])
                except Exception:
                    pass

        if dict_start != -1:
            dict_end = clean_text.rfind("}")
            if dict_end > dict_start:
                try:
                    return json.loads(clean_text[dict_start:dict_end + 1])
                except Exception:
                    pass

        return None