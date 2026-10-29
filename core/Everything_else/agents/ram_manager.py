# ram_manager.py

import os
import time
import gc
import threading
from llama_cpp import Llama

from core.paths import HOST_MODELS_DIR, MODELS_DIR

IDLE_TIMEOUT_SECONDS = 600  # 10 minutes


class RAMManager:
    def __init__(self, idle_timeout: int = IDLE_TIMEOUT_SECONDS, **kwargs):
        self.idle_timeout = idle_timeout
        self.current_model_name = None
        self.configured_model_path = None
        self.model_instance = None
        self.last_activity_time = 0.0
        self._lock = threading.Lock()
        self._timer_thread = None
        self._running = False

    @property
    def is_loaded(self) -> bool:
        with self._lock:
            return self.model_instance is not None

    def configure_model(self, model_path: str):
        with self._lock:
            if model_path:
                self.configured_model_path = os.path.basename(model_path)
            else:
                self.configured_model_path = None

    def _resolve_model_path(self, model_filename: str) -> str:
        filename_only = os.path.basename(model_filename)
        host_path = os.path.join(HOST_MODELS_DIR, filename_only)

        if os.path.exists(host_path):
            return host_path

        raise FileNotFoundError(f"Model file '{filename_only}' not found in host runtime: {host_path}")

    def _load_model_unsafe(self, target_filename: str):
        """Internal loader executed strictly under self._lock."""
        if self.current_model_name == target_filename and self.model_instance is not None:
            self.last_activity_time = time.time()
            return

        if self.model_instance is not None:
            print(f"[*] Swapping model in RAM from '{self.current_model_name}' to '{target_filename}'...")
            self._unload_model_unsafe()

        resolved_path = self._resolve_model_path(target_filename)
        print(f"[*] Loading new model into RAM: {resolved_path}...")

        self.model_instance = Llama(
            model_path=resolved_path,
            n_ctx=4096,
            n_threads=os.cpu_count() or 4,
            verbose=False
        )
        self.current_model_name = target_filename
        self.last_activity_time = time.time()
        print(f"[+] Model '{target_filename}' successfully loaded into RAM.")

    def load_model(self, model_filename: str = None):
        """Public loader thread-safe wrapper."""
        target_path = model_filename or self.configured_model_path
        if not target_path:
            raise ValueError("No model path provided or configured.")
        target_filename = os.path.basename(target_path)

        with self._lock:
            self._load_model_unsafe(target_filename)

    def generate_response(self, prompt: str, model_filename: str = None, max_tokens: int = 512) -> str:
        """
        Strictly sequential generation: Loads the model and runs inference 
        under a single uninterrupted lock to prevent race conditions and RAM spikes.
        """
        target_path = model_filename or self.configured_model_path
        if not target_path:
            raise ValueError("No model path provided or configured.")
        target_filename = os.path.basename(target_path)

        with self._lock:
            # Load or verify model inside the same atomic lock block
            self._load_model_unsafe(target_filename)

            self.last_activity_time = time.time()
            output = self.model_instance(
                prompt,
                max_tokens=max_tokens,
                stop=["User:"],
                echo=False
            )
            response_text = output["choices"][0]["text"].strip()
            self.last_activity_time = time.time()
            return response_text

    def _unload_model_unsafe(self):
        """Purges llama_cpp instance and forces Python/C++ memory release under lock."""
        if self.model_instance is not None:
            print(f"[*] Purging model '{self.current_model_name}' from memory...")
            
            if hasattr(self.model_instance, "close"):
                try:
                    self.model_instance.close()
                except Exception as e:
                    print(f"[!] Warning closing llama instance: {e}")

            del self.model_instance
            self.model_instance = None
            self.current_model_name = None
            
            gc.collect()
            print("[+] Model successfully purged from RAM.")

    def unload_model(self):
        with self._lock:
            self._unload_model_unsafe()

    def start_monitoring(self):
        if self._running:
            return

        self._running = True

        def monitor():
            while self._running:
                time.sleep(15)
                with self._lock:
                    if self.model_instance is not None:
                        elapsed = time.time() - self.last_activity_time
                        if elapsed >= self.idle_timeout:
                            self._unload_model_unsafe()

        self._timer_thread = threading.Thread(target=monitor, daemon=True)
        self._timer_thread.start()

    def stop_monitoring(self):
        self._running = False
        self.unload_model()

    def shutdown(self):
        self.stop_monitoring()