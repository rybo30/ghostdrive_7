# tool_runner.py

import os
import sys
import json
import re
import logging
import importlib.util
from datetime import datetime
from typing import Dict, Any, List, Optional, Union

from core.paths import AGENT_TOOLS_DIR, USB_TOOLS_DIR, EVERYTHING_ELSE
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

    def process_proactive_pulse(
        self, 
        chat_history: List[Dict[str, str]], 
        user_profile: Dict[str, Any],
        active_projects: List[str],
        model_filename: Optional[str] = None,
        system_prompt: str = "",
        allowed_tools: Optional[List[str]] = None
    ) -> Optional[str]:
        """Algorithm 2: Independent proactive algorithm for autonomous background outreach."""
        current_time_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        self.registry.load_tools()

        # Step 1: Evaluates projects, profile, and context to construct a proactive goal
        intent_data = self._stage_1_proactive_intent(
            chat_history=chat_history,
            user_profile=user_profile,
            active_projects=active_projects,
            current_time_str=current_time_str,
            model_filename=model_filename
        )

        # Forced execution: Extract intent or fallback to default thoughtful check-in
        intent = intent_data.get("intent") or "Provide a thoughtful status check-in based on user goals and active projects."
        target_tools = intent_data.get("tools", [])
    
        if allowed_tools is not None:
            target_tools = [t for t in target_tools if t in allowed_tools and t in self.registry.tools]

        # Step 2: Determine tool execution vs direct ping
        if target_tools:
            raw_output = self._stage_2_tool_workflow(
                prompt=intent,
                tools=target_tools,
                intent=intent,
                model_filename=model_filename,
                current_time_str=current_time_str
            )
        else:
            raw_output = self._stage_2_direct_response_workflow(
                prompt=intent,
                intent=intent,
                system_prompt=system_prompt,
                model_filename=model_filename,
                current_time_str=current_time_str
            )

        # Step 3: Persona proofreader & message partitioning
        final_responses = self._stage_3_proofread_and_split(
            prompt=intent,
            draft_response=raw_output,
            system_prompt=system_prompt,
            model_filename=model_filename
        )

        return "\n\n".join(final_responses) if final_responses else "Autonomous system check-in completed."

    def _stage_1_proactive_intent(
        self, 
        chat_history: List[Dict[str, str]], 
        user_profile: Dict[str, Any], 
        active_projects: List[str], 
        current_time_str: str,
        model_filename: Optional[str]
    ) -> Dict[str, Any]:
        """Gives the AI full autonomous freedom to decide what proactive action to take for the user."""
        prompt = f"""You are a fully autonomous AI agent. You have total creative freedom to decide what helpful, interesting, or valuable action to take for your user right now. 
Do not feel constrained by projects or profiles. You can search the web for fascinating news, look up technology trends, check weather, analyze systems, draft documents, or research anything you believe would delight, inform, or assist the user.

Current Date/Time: {current_time_str}

Recent Conversation History:
{json.dumps(chat_history[-6:] if chat_history else [], indent=2)}

Available Tools:
{json.dumps(self.registry.get_tool_summaries(), indent=2)}

Instructions:
1. Think of a creative, useful, or interesting task or research objective you want to execute right now.
2. Select any tool from your available tools if needed, or formulate a brilliant proactive check-in.
3. Formulate your clear task description ("intent") and list any required tools.

Respond STRICTLY in JSON:
```json
{{
  "intent": "Detailed description of the autonomous task, research query, or action you want to take",
  "tools": ["tool_name"]
}}
```"""

        try:
            response = self.ram_manager.generate_response(
                prompt=prompt,
                model_filename=model_filename,
                max_tokens=384
            )
            parsed = self._parse_json_action(response)
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            logger.error(f"[Proactive Pulse] Stage 1 Error: {e}")

        return {"intent": "Provide a thoughtful update, interesting insight, or helpful check-in for the user.", "tools": []}



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