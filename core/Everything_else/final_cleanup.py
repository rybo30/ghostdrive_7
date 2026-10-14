import os
import getpass
from filecrypt import get_fernet, encrypt_file

username = getpass.getuser()  # or pass in GhostDrive login username

def encrypt_memory_file():
    memory_path = os.path.join(os.path.dirname(__file__), "user_memory", "memory.jsonl")
    if not os.path.exists(memory_path):
        print("📭 No memory file found to encrypt.")
        return

    passphrase = getpass.getpass("🔐 Enter passphrase to encrypt memory: ")
    fernet = get_fernet(passphrase, username)

    try:
        encrypt_file(memory_path, fernet)
        print("🧊 Memory file encrypted successfully.")
    except Exception as e:
        print(f"❌ Failed to encrypt memory file: {e}")



def encrypt_chatlogs_folder():
    chatlog_dir = os.path.join(os.path.dirname(__file__), "chatlogs")
    if not os.path.exists(chatlog_dir):
        print("📭 No chat logs folder found.")
        return

    passphrase = getpass.getpass("🔐 Enter master passphrase to encrypt all chat logs: ")
    fernet = get_fernet(passphrase, username)

    count = 0
    skipped = []

    for filename in os.listdir(chatlog_dir):
        if filename.endswith(".txt"):
            full_path = os.path.join(chatlog_dir, filename)
            try:
                encrypt_file(full_path, fernet)
                count += 1
            except PermissionError:
                skipped.append(filename)
            except Exception as e:
                print(f"❌ Failed to encrypt {filename}: {e}")

    print(f"🧊 Encrypted {count} chat log(s) successfully.")
    if skipped:
        print("⚠️ Skipped locked files:")
        for f in skipped:
            print(f" - {f}")

def final_cleanup():
    encrypt_chatlogs_folder()
    encrypt_memory_file()
