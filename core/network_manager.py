import socket
import threading
import os
import time
import json
import base64
from cryptography.fernet import Fernet
from core.paths import EVERYTHING_ELSE
from core.peers_manager import load_peers
from core.identity import derive_shared_secret

GHOST_PORT = 5555 

class GhostNetwork:
    def __init__(self, username, fernet, ghost_id, sync_priv_key):
        self.username = username
        self.fernet = fernet 
        self.ghost_id = ghost_id
        self.sync_priv_key = sync_priv_key
        self.running = True
        self.discovered_peers = {} 

    def get_public_ip(self):
        """Fetches the WAN IP so the user can share it."""
        try:
            # Using a simple web-based resolver for 100% reliability over STUN
            import urllib.request
            return urllib.request.urlopen('https://ident.me').read().decode('utf8')
        except:
            try:
                # Fallback to socket method
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
            except:
                return "127.0.0.1"

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            server.bind(('0.0.0.0', GHOST_PORT))
            while self.running:
                data, addr = server.recvfrom(65535)
                threading.Thread(target=self.handle_incoming_udp, args=(data, addr)).start()
        except Exception as e:
            print(f"Server error: {e}")

    def handle_incoming_udp(self, data, addr):
        try:
            # 1. Check for Hole Punch
            if data == b"PUNCH": return

            sender_id = data[:32].decode().strip()
            header_json = data[32:160].decode().strip()
            header = json.loads(header_json)
            encrypted_payload = data[160:]

            peers = load_peers(self.username, self.fernet)
            target_peer = next((p for p in peers.values() if p.get("ghost_id") == sender_id), None)

            if not target_peer: return 

            shared_secret = derive_shared_secret(self.sync_priv_key, target_peer.get("public_key"))
            sync_fernet = Fernet(base64.urlsafe_b64encode(shared_secret[:32]))

            decrypted_data = sync_fernet.decrypt(encrypted_payload)
            filename = header.get("filename", "sync_file.enc")
            save_path = os.path.join(EVERYTHING_ELSE, "projects", self.username, filename)
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "wb") as f:
                f.write(decrypted_data)
            print(f"[SUCCESS] Received {filename}")
        except Exception as e:
            print(f"Transfer error: {e}")

    def send_file(self, target_ip, file_path, recipient_sync_hex, progress_callback=None):
        """Direct P2P Transmission with Progress Tracking."""
        try:
            shared_secret = derive_shared_secret(self.sync_priv_key, recipient_sync_hex)
            sync_fernet = Fernet(base64.urlsafe_b64encode(shared_secret[:32]))

            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            filename = os.path.basename(file_path)
            
            with open(file_path, "rb") as f:
                raw_data = f.read()
            
            encrypted_data = sync_fernet.encrypt(raw_data)
            header_data = json.dumps({"filename": filename}).ljust(128).encode()
            id_prefix = f"{self.ghost_id:<32}".encode()
            
            full_packet = id_prefix + header_data + encrypted_data
            total_size = len(full_packet)
            
            # Send Hole Punch
            sock.sendto(b"PUNCH", (target_ip, GHOST_PORT))
            time.sleep(0.1)

            # Chunked Send (Reliability for larger files)
            chunk_size = 8192
            for i in range(0, total_size, chunk_size):
                chunk = full_packet[i:i + chunk_size]
                sock.sendto(chunk, (target_ip, GHOST_PORT))
                if progress_callback:
                    progress_callback(int((i / total_size) * 100))
            
            if progress_callback: progress_callback(100)
            return True
        except Exception as e:
            print(f"Sync failed: {e}")
            return False

    def start_broadcast(self):
        broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        message = f"GHOST_DISCOVERY:{self.ghost_id}".encode()
        while self.running:
            try: broadcast_sock.sendto(message, ('<broadcast>', 5556))
            except: pass
            time.sleep(10)

    def listen_for_peers(self):
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        listen_sock.bind(('', 5556))
        while self.running:
            data, addr = listen_sock.recvfrom(1024)
            msg = data.decode()
            if msg.startswith("GHOST_DISCOVERY:"):
                peer_id = msg.split(":")[1]
                self.discovered_peers[peer_id] = addr[0]