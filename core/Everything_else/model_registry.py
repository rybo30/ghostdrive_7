# [model_registry.py]
import os
import sys
import gc
import yaml
import time
import base64
import subprocess
import ctypes

# 1. IMPORT PATHS FIRST
from core.paths import MODELS_DIR, EVERYTHING_ELSE, BASE_PATH

# 2. THE DLL SHIELD (Must run BEFORE the llama_cpp import)
def setup_sovereign_dlls():
    if getattr(sys, 'frozen', False):
        bundle_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        llama_path = os.path.join(bundle_dir, "llama_cpp")
    else:
        llama_path = os.path.join(BASE_PATH, "Windows", "_internal", "llama_cpp")

    if os.path.exists(llama_path):
        os.environ['PATH'] = llama_path + os.pathsep + os.environ['PATH']
        try:
            os.add_dll_directory(llama_path)
        except (AttributeError, OSError):
            pass
    return llama_path

# Execute the shield
setup_sovereign_dlls()

# 3. NOW PERFORM THE IMPORT
try:
    from llama_cpp import Llama
    from llama_cpp.llama_chat_format import MoondreamChatHandler
except Exception as e:
    print(f"[FATAL] ENGINE IMPORT ERROR: {e}")
    time.sleep(5)
    sys.exit(1)


# --- 1. CORE UTILITIES ---

def get_model_config(model_id):
    """Safely retrieves model settings from the YAML config."""
    config_path = os.path.join(MODELS_DIR, "models.yaml")
    try:
        with open(config_path, "r") as f:
            all_configs = yaml.safe_load(f).get("models", {})
        if model_id not in all_configs:
            raise ValueError(f"Model '{model_id}' not found in {config_path}")
        return all_configs[model_id]
    except Exception as e:
        print(f"[Jynx] Config Error: {e}")
        return {}

def get_all_model_configs():
    """Retrieves the entire dictionary mapping from models.yaml without needing an ID."""
    config_path = os.path.join(MODELS_DIR, "models.yaml")
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f).get("models", {})
    except Exception as e:
        print(f"[Jynx] Config Error loading all items: {e}")
        return {}

def get_stop_sequence(model_id):
    return ["</s>", "User:", "Assistant:"]

def encode_image(image_path):
    try:
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"[Jynx] Image error: {e}")
        return None

# --- 2. LIFECYCLE MANAGEMENT ---

ACTIVE_LLM = None
ACTIVE_MODEL_ID = None

def unload_previous_model():
    global ACTIVE_LLM, ACTIVE_MODEL_ID
    if ACTIVE_LLM is not None:
        try:
            ACTIVE_LLM.close()
        except: pass
        ACTIVE_LLM = None
        ACTIVE_MODEL_ID = None
    gc.collect()
    time.sleep(0.1)

# --- ARCHITECTURE WORKFLOW SPECIFICATIONS ---

class LlamaWorkflow:
    @staticmethod
    def format_prompt(prompt):
        return f"User: {prompt}\nAssistant:"

    @staticmethod
    def get_stop_sequences(model_id):
        return ["</s>", "User:", "Assistant:"]

    @staticmethod
    def extract_token(chunk):
        if 'choices' in chunk and len(chunk['choices']) > 0:
            choice = chunk['choices'][0]
            if 'delta' in choice and 'content' in choice['delta']:
                return choice['delta']['content']
            elif 'text' in choice:
                return choice['text']
        return ""


class QwenWorkflow:
    @staticmethod
    def format_prompt(prompt):
        # Native ChatML framing required to properly drive Qwen's attention layers
        return f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

    @staticmethod
    def get_stop_sequences(model_id):
        return ["<|im_end|>", "<|im_start|>", "<|endoftext|>"]

    @staticmethod
    def extract_token(chunk):
        if 'choices' in chunk and len(chunk['choices']) > 0:
            choice = chunk['choices'][0]
            # Symmetrically check both properties to survive low-level C-binding format drift
            if 'text' in choice and choice['text']:
                return choice['text']
            elif 'delta' in choice and 'content' in choice['delta']:
                return choice['delta']['content']
        return ""


# --- THE LOADER & INTERFACE ROUTER ---

def load_model_from_config(model_id):
    global ACTIVE_LLM, ACTIVE_MODEL_ID
    
    config = get_model_config(model_id)
    clip_path = config.get("clip_path")
    abs_clip_path = os.path.join(MODELS_DIR, clip_path) if clip_path else None

    # 1. Check if already loaded
    if ACTIVE_LLM is not None and ACTIVE_MODEL_ID == model_id:
        llm = ACTIVE_LLM
    else:
        # 2. New Model: Purge and Load
        unload_previous_model()
        model_path = os.path.join(MODELS_DIR, config.get("path", ""))
        
        chat_handler = MoondreamChatHandler(clip_model_path=abs_clip_path) if abs_clip_path else None
        raw_ctx = config.get("max_tokens", "native")
        
        # Determine n_ctx value
        if "whisper" in model_id:
            model_defined_ctx = 512
            config["arch_type"] = "whisper"
        elif str(raw_ctx).lower() in ["0", "-1", "native"]:
            # Setting n_ctx=0 tells llama_cpp to read native context directly from GGUF metadata
            model_defined_ctx = 0 
            
            # Inspect architecture flag
            try:
                metadata_reader = Llama(model_path=model_path, vocab_only=True, verbose=False)
                arch = metadata_reader.metadata.get("general.architecture", "llama")
                config["arch_type"] = str(arch).lower()
                del metadata_reader
                gc.collect()
            except Exception as e:
                print(f"[Jynx] Metadata architecture inspection note: {e}")
                config["arch_type"] = "llama"
        else:
            try:
                model_defined_ctx = int(raw_ctx)
            except (ValueError, TypeError):
                model_defined_ctx = 4096
            config["arch_type"] = "llama"

        llm = Llama(
            model_path=model_path,
            chat_handler=chat_handler,
            n_ctx=model_defined_ctx, 
            n_gpu_layers=config.get("n_gpu_layers", 0),
            flash_attn=False,
            verbose=False
        )
        
        config["actual_ctx_window"] = llm.n_ctx()
        ACTIVE_LLM = llm
        ACTIVE_MODEL_ID = model_id

    # 3. ROUTER SELECTION
    arch_type = config.get("arch_type", "llama")
    if "qwen" in arch_type:
        workflow = QwenWorkflow
    else:
        workflow = LlamaWorkflow

    # 4. Define Single Clean Inference Closure
    def call(prompt, stream_override=None, image_path=None, **kwargs):
        stream = config.get("stream", True) if stream_override is None else stream_override
        # Honor max_tokens passed or fall back to model config / safe default
        m_tokens = kwargs.get("max_tokens", config.get("max_tokens", 4096))
        if isinstance(m_tokens, str):
            m_tokens = 4096

        # Vision Path (Kept uniform for Moondream bindings)
        if image_path and abs_clip_path:
            b64_data = encode_image(image_path)
            if b64_data:
                response = llm.create_chat_completion(
                    messages=[{"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_data}"}}
                    ]}],
                    stream=stream,
                    max_tokens=m_tokens
                )
                if stream:
                    def vision_stream():
                        for chunk in response:
                            if 'choices' in chunk and len(chunk)['choices'] > 0:
                                content = chunk['choices'][0].get('delta', {}).get('content', '')
                                if content: yield content
                    return vision_stream()
                return response['choices'][0]['message']['content']

        # Dedicated Text Flow via Selected Workflow
        formatted_prompt = workflow.format_prompt(prompt)
        stops = workflow.get_stop_sequences(model_id)

        response = llm(
            prompt=formatted_prompt, 
            stream=stream, 
            stop=stops,
            max_tokens=m_tokens,
            temperature=kwargs.get("temperature", config.get("temperature", 0.7))
        )

        if stream:
            def clean_text_stream():
                for chunk in response:
                    token = workflow.extract_token(chunk)
                    if token:
                        yield token
            return clean_text_stream()
            
        # Synchronous string handling extraction fallback
        if isinstance(response, dict) and 'choices' in response:
            choice = response['choices'][0]
            if 'message' in choice and 'content' in choice['message']:
                return choice['message']['content']
            elif 'text' in choice:
                return choice['text']
        return str(response)

    return call, config


def get_visual_description(image_path):
    """Helper for internal description requests."""
    try:
        vision_fn, _ = load_model_from_config("jynx_vision")
        return vision_fn("Describe this image.", image_path=image_path, stream_override=False)
    except Exception as e:
        return f"Vision Error: {e}"


def transcribe_audio(audio_path):
    """Uses the 'ollie_whisper' config to transcribe audio via whisper-cli."""
    config = get_model_config("ollie_whisper")
    if not config:
        return "[Jynx] Error: Whisper configuration not found."

    model_path = os.path.join(MODELS_DIR, config["path"])
    
    try:
        command = [
            "whisper-cli", 
            "-m", model_path, 
            "-f", audio_path, 
            "-nt", 
            "-otxt"
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Transcription Error: {result.stderr}"
    except FileNotFoundError:
        return "Error: 'whisper-cli' not found in PATH. Please install whisper.cpp bindings."
    except Exception as e:
        return f"Unexpected Vision/Voice Error: {e}"


#####################################
# PDF Text Extraction
#####################################

def extract_text_from_pdf(pdf_path):
    """Extracts text content from a local PDF file completely offline."""
    import pypdf
    try:
        text_content = []
        with open(pdf_path, "rb") as f:
            reader = pypdf.PdfReader(f)
            for page_num, page in enumerate(reader.pages):
                page_text = page.extract_text()
                if page_text:
                    text_content.append(f"--- PAGE {page_num + 1} ---\n{page_text}")
        return "\n\n".join(text_content)
    except Exception as e:
        return f"Error extracting PDF text: {str(e)}"


#####################################
# New Model Sync-Up
#####################################

def sync_unregistered_models():
    """Scans the models directory for unregistered GGUF files and auto-registers them in models.yaml."""
    yaml_path = os.path.join(MODELS_DIR, "models.yaml")
    if not os.path.exists(yaml_path):
        return

    try:
        # Load existing config keys and paths
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw_content = f.read()
            
        existing_configs = yaml.safe_load(raw_content) or {}
        models_dict = existing_configs.get("models", {})
        
        # Gather all model paths already configured
        registered_paths = {cfg.get("path") for cfg in models_dict.values() if isinstance(cfg, dict)}

        # Find any GGUF files in MODELS_DIR that aren't registered
        new_entries = []
        for file in os.listdir(MODELS_DIR):
            if file.endswith(".gguf") and file not in registered_paths:
                # Generate clean key and display name
                clean_name = file.replace(".gguf", "").replace("-", " ").replace("_", " ")
                if len(clean_name) > 30:
                    clean_name = clean_name[:27] + "..."
                    
                config_key = "user_download_" + file.lower().replace(".gguf", "").replace("-", "_").replace(".", "_")

                # Skip if key already exists
                if config_key in models_dict:
                    continue

                new_entries.append(f"""  {config_key}:
    name: "{clean_name}"
    path: "{file}"
    system_prompt: |
      You are a helpful AI assistant running locally via GhostDrive.
    temperature: 0.5
    max_tokens: 4096
    stream: true

""")

        # Append new model blocks to models.yaml if any were found
        if new_entries:
            combined_entries = "".join(new_entries)
            if "models:" in raw_content:
                parts = raw_content.split("models:", 1)
                updated_content = f"models:\n\n{combined_entries}{parts[1]}"
            else:
                updated_content = f"models:\n\n{combined_entries}{raw_content}"

            with open(yaml_path, "w", encoding="utf-8") as f:
                f.write(updated_content)
                f.flush()
                os.fsync(f.fileno())
                
            print(f"✅ Auto-registered {len(new_entries)} model(s) into models.yaml.")

    except Exception as e:
        print(f"❌ Failed during auto model sync: {str(e)}")