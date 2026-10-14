# matchmaker.py

import socket
import json
import threading

# This would run on a cheap VPS (like a $5 DigitalOcean or Linode box)
MATCH_PORT = 9999

class GhostMatchmaker:
    def __init__(self):
        self.rooms = {} # Format: { "room_id": [peer1_info, peer2_info] }

    def start(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', MATCH_PORT))
        server.listen(100)
        print(f"Matchmaker online on port {MATCH_PORT}")

        while True:
            client, addr = server.accept()
            threading.Thread(target=self.handle_client, args=(client, addr)).start()

    def handle_client(self, client, addr):
        try:
            data = client.recv(1024).decode()
            request = json.loads(data)
            room_id = request.get("room_id")
            my_info = {
                "ghost_id": request.get("ghost_id"),
                "ip": addr[0],
                "port": addr[1]
            }

            if room_id not in self.rooms:
                self.rooms[room_id] = [my_info]
                # Wait for a partner to join
                client.send(json.dumps({"status": "waiting"}).encode())
            else:
                # Partner found!
                partner_info = self.rooms[room_id][0]
                client.send(json.dumps({"status": "match", "partner": partner_info}).encode())
                # Clean up the room immediately
                del self.rooms[room_id]

        except Exception as e:
            print(f"Match error: {e}")
        finally:
            client.close()