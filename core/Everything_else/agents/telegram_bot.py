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
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from cryptography.fernet import Fernet

from core.paths import AGENT_CONFIGS_DIR, EVERYTHING_ELSE, HOST_HIDDEN_DIR
from core.Everything_else.agents.ram_manager import RAMManager

USER_HOME = os.path.expanduser("~")
AGENTS_DIR = os.path.abspath(os.path.join(USER_HOME, ".ghostdrive", "agents"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramBotGateway")


class TelegramQueueDB:
    def __init__(self, db_path: str, key_path: Optional[str] = None):
        # Force the database storage to strictly use .enc instead of .db
        base_path = Path(db_path).with_suffix("")
        self.enc_path = Path(str(base_path) + ".enc")
        
        # Clean up any leftover legacy unencrypted .db files from previous runs
        legacy_db_path = Path(str(base_path) + ".db")
        if legacy_db_path.exists():
            try:
                os.remove(legacy_db_path)
                logger.info(f"[DB] Removed legacy unencrypted database file: {legacy_db_path.name}")
            except Exception:
                pass

        if key_path:
            self.key_path = Path(key_path)
        else:
            self.key_path = self.enc_path.with_suffix(".key")

        self.conn = sqlite3.connect(":memory:")
        self._load_and_decrypt_or_initialize()

    def _get_connection(self):
        return self.conn

    def _load_and_decrypt_or_initialize(self):
        try:
            if self.enc_path.exists() and self.key_path.exists():
                # Decrypt existing encrypted state into RAM
                with open(self.key_path, "rb") as k_file:
                    key_bytes = k_file.read().strip()
                
                with open(self.enc_path, "rb") as e_file:
                    encrypted_data = e_file.read()
                
                fernet = Fernet(key_bytes)
                decrypted_bytes = fernet.decrypt(encrypted_data)
                
                temp_conn = sqlite3.connect(":memory:")
                temp_conn.deserialize(decrypted_bytes)
                self.conn = temp_conn
                logger.info(f"[DB] Successfully decrypted and loaded conversation state from {self.enc_path.name}")
            else:
                # Fully encrypted from launch: Create fresh schema and immediately write encrypted .enc to disk
                logger.info(f"[DB] Initializing fresh encrypted conversation state at launch: {self.enc_path.name}")
                self._init_schema()
                self.save_and_encrypt()
        except Exception as e:
            logger.warning(f"[DB] Failed to decrypt state database, initializing fresh encrypted DB: {e}")
            self._init_schema()
            self.save_and_encrypt()

    def _init_schema(self):
        cursor = self.conn.cursor()
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
        self.conn.commit()

    def save_and_encrypt(self):
        if not self.key_path.exists():
            return
        try:
            with open(self.key_path, "rb") as k_file:
                key_bytes = k_file.read().strip()
            
            # Serialize in-memory database bytes and encrypt with Fernet
            serialized_data = self.conn.serialize()
            fernet = Fernet(key_bytes)
            encrypted_data = fernet.encrypt(serialized_data)
            
            # Write strictly to the encrypted .enc file
            with open(self.enc_path, "wb") as f:
                f.write(encrypted_data)
            logger.info(f"[DB] Successfully encrypted and saved conversation state to {self.enc_path.name}")
        except Exception as e:
            logger.error(f"[DB] Failed to encrypt and save state database: {e}")

    def enqueue_message(self, chat_id: int, message_id: int, user_name: str, message_text: str) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO message_queue (chat_id, message_id, user_name, message_text, status)
                VALUES (?, ?, ?, ?, 'PENDING')
            """, (chat_id, message_id, user_name, message_text))
            conn.commit()
            task_id = cursor.lastrowid
        
        # Re-encrypt immediately when a message is received and queued
        self.save_and_encrypt()
        return task_id

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
            
        # Re-encrypt immediately after a message/response is fully processed and sent
        self.save_and_encrypt()

    def mark_old_shutdowns_cleared(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE message_queue
                SET status = 'SKIPPED', response_text = 'Ignored historical shutdown command.'
                WHERE status = 'PENDING' AND TRIM(message_text) = '/shutdown'
            """)
            conn.commit()
        self.save_and_encrypt()

    def reset_stuck_tasks(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE message_queue
                SET status = 'FAILED', response_text = 'Reset on system restart.'
                WHERE status = 'PROCESSING'
            """)
            conn.commit()
        self.save_and_encrypt()

    def get_recent_user_messages(self, chat_id: int, current_task_id: int, limit: int = 2) -> List[str]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT message_text FROM message_queue 
                WHERE chat_id = ? AND id < ?
                ORDER BY id DESC LIMIT ?
            """, (chat_id, current_task_id, limit))
            rows = cursor.fetchall()
            return [row["message_text"] for row in reversed(rows)]

    def close(self):
        try:
            self.save_and_encrypt()
            if self.conn:
                self.conn.close()
        except Exception:
            pass

    def get_recent_history(self, chat_id: int, limit: int = 5) -> List[Dict[str, str]]:
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
        key_path: Optional[str] = None,
        shutdown_callback: Optional[Callable] = None
    ):
        self.bot_token = bot_token
        self.ram_manager = ram_manager
        self.task_processor = task_processor
        self.shutdown_callback = shutdown_callback
        self.default_chat_id: Optional[int] = None
        
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        abs_agents_dir = os.path.abspath(AGENTS_DIR)
        os.makedirs(abs_agents_dir, exist_ok=True)
        
        self.db_path = os.path.abspath(os.path.join(abs_agents_dir, db_name))
        self.db = TelegramQueueDB(self.db_path, key_path=key_path)
        
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

                    if local_file_path and os.path.exists(local_file_path):
                        # Give the agent the clean absolute file path to read using its tool
                        file_context = (
                            f"=== ATTACHED DOCUMENT PATH ({file_name}) ===\n"
                            f"File is saved locally at: {os.path.abspath(local_file_path)}\n"
                            f"=== END DOCUMENT PATH ===\n\n"
                        )
                        text = f"{file_context}User Query: {text if text else 'Please use the document_reader_tool on the provided path to read and summarize this file.'}"

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
                self.send_message(chat_id, "⏳ Loading Agent")

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