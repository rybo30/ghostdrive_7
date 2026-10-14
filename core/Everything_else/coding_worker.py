# [coding_worker.py]

from PySide6.QtCore import QThread, Signal
from .model_registry import load_model_from_config

class CodingWorker(QThread):
    chunk_received = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, code, instruction, model_id="jynx_expert_coding"):
        super().__init__()
        self.code = code
        self.instruction = instruction
        self.model_id = model_id

    def run(self):
        try:
            # Load from model_registry.py
            call_fn, config = load_model_from_config(self.model_id)
            
            prompt = (
                "SYSTEM: You are an expert Python developer. Fix the user's code. "
                "Output the corrected code inside triple backticks first, then explain why.\n\n"
                f"INSTRUCTION: {self.instruction}\n\n"
                f"CODE:\n{self.code}\n\n"
                "SOLUTION:"
            )

            # Use the call_fn returned by your registry
            response_gen = call_fn(prompt, stream_override=True, max_tokens=2048)
            
            for chunk in response_gen:
                # Handle the llama-cpp dictionary structure
                if isinstance(chunk, dict) and 'choices' in chunk:
                    content = chunk['choices'][0].get('text', '')
                    if content: self.chunk_received.emit(content)
                elif isinstance(chunk, str):
                    self.chunk_received.emit(chunk)

            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))