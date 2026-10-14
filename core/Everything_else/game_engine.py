# [core/Everything_else/game_engine.py]

import subprocess
import os
import sys
from core.paths import GAMES_DIR

class GameEngine:
    def __init__(self):
        self.root_arcade = GAMES_DIR
        self.active_game = None # Keep a reference so it doesn't get garbage collected

    def launch_game(self, game_id):
        if game_id == "stk":
            self._run_external(os.path.join("supertuxkart", "supertuxkart.exe"))
        
        elif game_id == "bvz":
            self._run_proprietary_bvz()
        
        elif game_id == "zero_ad":
            self._run_external(os.path.join("0ad", "binaries", "system", "0ad.exe"))

        elif game_id == "xonotic":
            self._run_external(os.path.join("Xonotic", "xonotic.exe"))
        
        elif game_id == "endless_sky":
            self._run_external(os.path.join("EndlessSky", "Endless Sky.exe"))
        
        elif game_id == "blockout":
            self._run_external(os.path.join("BlockOut", "BlockOut.exe"))

        else:
            print(f"ERROR: Protocol for {game_id} not initialized.")

    def _run_external(self, relative_path):
        full_path = os.path.join(self.root_arcade, relative_path)
        if os.path.exists(full_path):
            print(f"ARCADE // EXECUTION COMMENCED: {full_path}")
            subprocess.Popen([full_path], shell=True, cwd=os.path.dirname(full_path))
        else:
            print(f"ARCADE // ERROR: Binary not found at {full_path}")


    def _run_proprietary_bvz(self):
        print("ARCADE // INITIALIZING PROPRIETARY ASSET: BVZ")
        try:
            # --- THE FIX: FORCE THE PATH ---
            # Get the directory where this file (game_engine.py) lives
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            # Also ensure the project root is there for 'core' imports
            project_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
            if project_root not in sys.path:
                sys.path.insert(0, project_root)

            # Now perform the import
            from core.Everything_else.bvz_game import GameEngine as BVZGame
            
            self.active_game = BVZGame()
            self.active_game.show()
            print("ARCADE // BVZ CORE ONLINE.")
            
        except Exception as e:
            self.active_game = None 
            import traceback
            print("ARCADE // CRITICAL INITIALIZATION FAILURE:")
            traceback.print_exc()