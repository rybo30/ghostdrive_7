# core/Everything_else/agents/telegram_bot.py


import os
import sys
import time
import json
import re
import html
import sqlite3
import threading
import logging
import socket
import shutil
import signal
import urllib.error
import urllib.request
import urllib.parse
from typing import Optional, Callable, Dict, Any, List

from core.paths import AGENT_CONFIGS_DIR, EVERYTHING_ELSE, HOST_HIDDEN_DIR
from core.Everything_else.agents.ram_manager import RAMManager

USER_HOME = os.path.expanduser("~")
AGENTS_DIR = os.path.abspath(os.path.join(USER_HOME, ".ghostdrive", "agents"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramBotGateway")


class TelegramQueueDB:
    def __init__(self, db_path: str):
        self.db_path = os.path.abspath(db_path)
        db_dir = os.path.dirname(self.db_path)

        # --- DIAGNOSTIC PRINTS ---
        print(f"\n================ SYSTEM PATH DIAGNOSTICS ================")
        print(f"RAW DB PATH:          {db_path}")
        print(f"ABSOLUTE DB PATH:     {self.db_path}")
        print(f"TARGET DIRECTORY:     {db_dir}")
        print(f"DIRECTORY EXISTS?     {os.path.exists(db_dir)}")
        print(f"FILE EXISTS?          {os.path.exists(self.db_path)}")
        
        # Test directory creation explicitly
        try:
            os.makedirs(db_dir, exist_ok=True)
            print(f"DIRECTORY CREATED/VERIFIED: SUCCESS")
        except Exception as e:
            print(f"DIRECTORY CREATION FAILED: {e}")

        # Test physical file write permissions without SQLite
        touch_test_file = os.path.join(db_dir, ".perm_test")
        try:
            with open(touch_test_file, "w") as f:
                f.write("test")
            os.remove(touch_test_file)
            print(f"FILE WRITE PERMISSION TEST: PASSED")
        except Exception as e:
            print(f"FILE WRITE PERMISSION TEST: FAILED ({e})")
        print(f"==========================================================\n")
        # -------------------------

        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS message_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    user_name TEXT,
                    message_text TEXT NOT NULL,
                    status TEXT DEFAULT 'PENDING',
                    response_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def enqueue_message(self, chat_id: int, message_id: int, user_name: str, message_text: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO message_queue (chat_id, message_id, user_name, message_text, status)
                VALUES (?, ?, ?, ?, 'PENDING')
            """, (chat_id, message_id, user_name, message_text))
            conn.commit()
            return cursor.lastrowid

    def fetch_next_pending(self) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM message_queue WHERE status = 'PENDING' ORDER BY id ASC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def update_status(self, task_id: int, status: str, response_text: str = ""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE message_queue 
                SET status = ?, response_text = ?
                WHERE id = ?
            """, (status, response_text, task_id))
            conn.commit()

    def mark_old_shutdowns_cleared(self):
        """Marks stale pending /shutdown tasks as SKIPPED so they don't stop process startup."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE message_queue
                SET status = 'SKIPPED', response_text = 'Ignored historical shutdown command.'
                WHERE status = 'PENDING' AND TRIM(message_text) = '/shutdown'
            """)
            conn.commit()

    def reset_stuck_tasks(self):
        """Resets hanging PROCESSING tasks back to FAILED on process startup."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE message_queue
                SET status = 'FAILED', response_text = 'Reset on system restart.'
                WHERE status = 'PROCESSING'
            """)
            conn.commit()


    def get_recent_user_messages(self, chat_id: int, current_task_id: int, limit: int = 2) -> List[str]:
        """Retrieves up to `limit` prior user messages for a given chat_id excluding the active task."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT message_text FROM message_queue 
                WHERE chat_id = ? AND id < ?
                ORDER BY id DESC LIMIT ?
            """, (chat_id, current_task_id, limit))
            rows = cursor.fetchall()
            # Reverse order so messages flow chronologically (oldest to newest)
            return [row["message_text"] for row in reversed(rows)]


    def close(self):
        """Explicitly closes background DB connections if open."""
        try:
            # Force sqlite3 connection cache clean
            sqlite3.connect(self.db_path).close()
        except Exception:
            pass

    def get_recent_history(self, chat_id: int, limit: int = 5) -> List[Dict[str, str]]:
        """Retrieves up to `limit` prior user/agent exchanges for context."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_name, message_text, response_text 
                FROM message_queue 
                WHERE chat_id = ? AND status = 'COMPLETED'
                ORDER BY id DESC LIMIT ?
            """, (chat_id, limit))
            rows = cursor.fetchall()
        
            history = []
            for row in reversed(rows):
                history.append({"role": "user", "text": row["message_text"]})
                if row["response_text"]:
                    history.append({"role": "assistant", "text": row["response_text"]})
            return history


    def get_last_active_chat_id(self) -> Optional[int]:
        """Retrieves the most recent chat_id from the queue database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM message_queue ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            return row[0] if row else None


class TelegramBotGateway:
    def __init__(
        self, 
        bot_token: str, 
        ram_manager: RAMManager, 
        task_processor: Optional[Callable] = None,
        db_name: str = "agent_state.db",
        shutdown_callback: Optional[Callable] = None
    ):
        self.bot_token = bot_token
        self.ram_manager = ram_manager
        self.task_processor = task_processor
        self.shutdown_callback = shutdown_callback
        self.default_chat_id: Optional[int] = None
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Ensure directory is absolute and created explicitly
        abs_agents_dir = os.path.abspath(AGENTS_DIR)
        os.makedirs(abs_agents_dir, exist_ok=True)
        
        self.db_path = os.path.abspath(os.path.join(abs_agents_dir, db_name))
        self.db = TelegramQueueDB(self.db_path)
        
        self.last_update_id = 0
        self.is_running = False
        self.start_timestamp = time.time()
        self._polling_thread: Optional[threading.Thread] = None
        self._worker_thread: Optional[threading.Thread] = None

    def start(self):
        if not self.bot_token:
            logger.error("Telegram bot token missing. Gateway aborted.")
            return

        self.db.mark_old_shutdowns_cleared()
        self.db.reset_stuck_tasks()
        self.is_running = True
        self.start_timestamp = time.time()
        
        self._polling_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._polling_thread.start()
        
        self._worker_thread = threading.Thread(target=self._process_queue_loop, daemon=True)
        self._worker_thread.start()
        
        logger.info("Telegram Bot Gateway running.")

    def stop(self):
        self.is_running = False
        logger.info("Telegram Bot Gateway stopping...")

    def send_message(self, chat_id: int, text: str) -> bool:
        """Sends messages to Telegram with automatic 4096-char chunking and HTML/Plaintext fallback."""
        if not text or not str(text).strip():
            return False

        url = f"{self.api_url}/sendMessage"
        max_length = 4000  # Safe chunk size under Telegram's 4096 limit
    
        # Split long responses into chunks
        chunks = [text[i:i + max_length] for i in range(0, len(text), max_length)]
        success = True

        for chunk in chunks:
            # Escape HTML entities so symbols like '<' and '>' in market text don't trigger API syntax errors
            safe_chunk = html.escape(chunk)

            payload = json.dumps({
                "chat_id": chat_id,
                "text": safe_chunk,
                "parse_mode": "HTML"
            }).encode('utf-8')

            req = urllib.request.Request(
                url, 
                data=payload, 
                headers={'Content-Type': 'application/json'}
            )
        
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status != 200:
                        success = False
            except Exception as e:
                logger.warning(f"HTML parse failed for Telegram chunk, falling back to Plain Text: {e}")
                plain_payload = json.dumps({
                    "chat_id": chat_id,
                    "text": chunk
                }).encode('utf-8')
            
                plain_req = urllib.request.Request(
                    url, 
                    data=plain_payload, 
                    headers={'Content-Type': 'application/json'}
                )
                try:
                    with urllib.request.urlopen(plain_req, timeout=10) as resp:
                        if resp.status != 200:
                            success = False
                except Exception as ex:
                    logger.error(f"Failed to send raw text chunk to Telegram: {ex}")
                    success = False

        return success

    def _download_telegram_file(self, file_id: str, file_name: str) -> Optional[str]:
        """Downloads attachment files into host temporary runtime storage."""
        try:
            get_file_url = f"{self.api_url}/getFile?file_id={file_id}"
            req = urllib.request.Request(get_file_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                file_info = json.loads(resp.read().decode('utf-8'))

            if not file_info.get("ok"):
                return None

            remote_file_path = file_info["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{self.bot_token}/{remote_file_path}"

            temp_dir = os.path.join(AGENT_CONFIGS_DIR, "..", "temp_files")
            os.makedirs(temp_dir, exist_ok=True)
            local_path = os.path.join(temp_dir, file_name)

            urllib.request.urlretrieve(download_url, local_path)
            return local_path
        except Exception as e:
            logger.error(f"Failed downloading file from Telegram: {e}")
            return None

    def _poll_loop(self):
        # Flush outdated messages on boot
        try:
            flush_url = f"{self.api_url}/getUpdates?offset=-1"
            req = urllib.request.Request(flush_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get("ok") and data.get("result"):
                    self.last_update_id = data["result"][-1]["update_id"]
        except Exception as e:
            logger.warning(f"Could not initialize update offset: {e}")

        while self.is_running:
            try:
                # Match urllib read timeout (15s) to long-polling server wait time (5s)
                url = f"{self.api_url}/getUpdates?offset={self.last_update_id + 1}&timeout=5"
                req = urllib.request.Request(url)
            
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                
                    if data.get("ok"):
                        for update in data.get("result", []):
                            self.last_update_id = update["update_id"]
                            self._handle_update(update)

            except (urllib.error.URLError, socket.timeout) as e:
                # Normal network/poll timeout when no messages arrive; ignore silently
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Polling exception: {e}")
                time.sleep(2)

    def _handle_update(self, update: dict):
        if "message" in update:
            msg = update["message"]
            chat_id = msg["chat"]["id"]
            self.default_chat_id = chat_id  # Track default chat ID for autonomous background pings
            
            message_id = msg["message_id"]
            msg_date = msg.get("date", 0)
            user_name = msg.get("from", {}).get("first_name", "User")
            
            text = msg.get("text", msg.get("caption", "")).strip()

            # Handle attachments automatically
            if "document" in msg:
                doc = msg["document"]
                file_name = doc.get("file_name", "attached_doc.bin")
                file_id = doc.get("file_id")

                ext = os.path.splitext(file_name)[1].lower()
                supported_exts = [".pdf", ".docx", ".csv", ".tsv", ".txt", ".md", ".json", ".log"]

                if ext in supported_exts:
                    self.send_message(chat_id, f"📥 *Downloading document:* `{file_name}`...")
                    local_file_path = self._download_telegram_file(file_id, file_name)

                    if local_file_path:
                        extracted_content = ""
                        try:
                            import document_reader_tool
                            extracted_content = document_reader_tool.run(file_path=local_file_path)
                        except Exception as e:
                            extracted_content = f"Could not parse document: {e}"

                        try:
                            if os.path.exists(local_file_path):
                                os.remove(local_file_path)
                        except Exception:
                            pass

                        file_context = (
                            f"=== ATTACHED DOCUMENT CONTEXT ({file_name}) ===\n"
                            f"{extracted_content}\n"
                            f"=== END DOCUMENT CONTEXT ===\n\n"
                        )
                        text = f"{file_context}User Query: {text if text else 'Summarize or extract key points.'}"

            if not text:
                return

            logger.info(f"Received message from {user_name} ({chat_id}): '{text[:60]}...'")
            
            # System controls
            if text == "/ping":
                self.send_message(chat_id, "PONG :: Agent Online and Active.")
                return

            if text == "/shutdown":
                if msg_date >= (self.start_timestamp - 5):
                    self.send_message(chat_id, "SHUTDOWN :: Terminating host process.")
                    if self.shutdown_callback:
                        self.shutdown_callback()
                return

            if text == "/kill":
                if msg_date >= (self.start_timestamp - 5):
                    self._execute_kill_switch(chat_id)
                return

            task_id = self.db.enqueue_message(chat_id, message_id, user_name, text)
            logger.info(f"Task queued with ID #{task_id}")



    def _process_queue_loop(self):
        while self.is_running:
            task = self.db.fetch_next_pending()
            if not task:
                time.sleep(2)
                continue

            task_id = task["id"]
            chat_id = task["chat_id"]
            message_text = task["message_text"]

            if message_text.strip() == "/shutdown":
                self.db.update_status(task_id, "SKIPPED", "Ignored shutdown command.")
                continue

            logger.info(f"Processing Task #{task_id} for Chat {chat_id}...")
            self.db.update_status(task_id, "PROCESSING")

            if hasattr(self.ram_manager, 'model_instance') and self.ram_manager.model_instance is None:
                self.send_message(chat_id, "⏳ Agent model initializing into host RAM...")

            try:
                # Retrieve up to 2 prior user messages for context
                recent_user_history = self.db.get_recent_user_messages(
                    chat_id=chat_id, 
                    current_task_id=task_id, 
                    limit=2
                )

                if self.task_processor:
                    raw_response = self.task_processor(
                        prompt=message_text, 
                        chat_id=chat_id, 
                        user_history=recent_user_history
                    )
                else:
                    raw_response = f"Received: '{message_text}'."

                logger.info(f"[Gateway] Dispatching response for Task #{task_id} to Chat {chat_id}...")

                if isinstance(raw_response, list):
                    sent_any = False
                    for msg in raw_response:
                        cleaned_msg = str(msg).strip()
                        if cleaned_msg:
                            success = self.send_message(chat_id, cleaned_msg)
                            logger.info(f"[Gateway] Telegram send_message status: {success}")
                            sent_any = True
                            time.sleep(0.5)
                    db_response_text = "\n\n---\n\n".join(str(m) for m in raw_response)
                else:
                    db_response_text = str(raw_response).strip()
                    success = self.send_message(chat_id, db_response_text)
                    logger.info(f"[Gateway] Telegram send_message status: {success}")

                self.db.update_status(task_id, "COMPLETED", db_response_text)

            except Exception as e:
                logger.error(f"Error on Task #{task_id}: {e}", exc_info=True)
                error_msg = f"Error executing task: {str(e)}"
                self.send_message(chat_id, error_msg)
                self.db.update_status(task_id, "FAILED", error_msg)



    def _execute_kill_switch(self, chat_id: int):
        """Notifies user, releases DB connection locks, and triggers daemon kill switch."""
        try:
            self.send_message(chat_id, "🚨 KILL SWITCH TRIGGERED :: Initiating full purge and self-destruct...")
            time.sleep(1)
        except Exception as e:
            logger.error(f"Failed to send killswitch confirmation: {e}")

        self.is_running = False

        # Close DB handle explicitly
        try:
            if hasattr(self, 'db') and self.db:
                self.db.close()
                self.db = None
        except Exception as e:
            logger.error(f"Error closing DB handle: {e}")

        # Trigger daemon kill switch
        if self.shutdown_callback:
            try:
                self.shutdown_callback(kill_switch=True)
            except TypeError:
                self.shutdown_callback()


    def send_proactive_message(self, text: str, chat_id: Optional[int] = None) -> bool:
        """Dispatches a proactive message to the last known chat or specified chat ID."""
        target_chat = chat_id or self.default_chat_id
        if not target_chat:
            logger.warning("[Gateway] Cannot send proactive message: No target chat_id available.")
            return False
        return self.send_message(target_chat, text)



    def get_fallback_chat_id(self) -> Optional[int]:
        """Recovers default_chat_id from memory or SQLite queue DB."""
        if self.default_chat_id:
            return self.default_chat_id
        
        recovered_id = self.db.get_last_active_chat_id()
        if recovered_id:
            self.default_chat_id = recovered_id
        return recovered_id