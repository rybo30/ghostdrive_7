import os
import shutil
import time
import subprocess
import sys
import platform

# Universal Paths
STAGING = ".shadow_staging"
CORE = "core"
READY_FLAG = ".update_ready"

def get_executable_name():
    """Detects the OS and returns the likely executable name."""
    system = platform.system()
    if system == "Windows":
        return "Jynx_Operator.exe"
    elif system == "Darwin": # MacOS
        return "Jynx_Operator.app"
    else: # Linux
        return "Jynx_Operator"

def perform_surgery():
    if not os.path.exists(READY_FLAG):
        return 

    # 1. Surgical Pause
    time.sleep(3) 

    try:
        # 2. Universal File Swap
        for item in os.listdir(STAGING):
            s = os.path.join(STAGING, item)
            d = os.path.join(CORE, item)
            
            if os.path.isdir(s):
                if os.path.exists(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)

        # 3. Finalize
        new_version = "1.0.1"
        with open(READY_FLAG, "r") as f: new_version = f.read().strip()
        with open("version.txt", "w") as f: f.write(new_version)
        
        shutil.rmtree(STAGING)
        os.remove(READY_FLAG)

        # 4. OS-Specific Restart Logic
        exe_name = get_executable_name()
        
        if os.path.exists(exe_name):
            if platform.system() == "Darwin": # Mac requires 'open'
                subprocess.Popen(["open", exe_name])
            elif platform.system() == "Linux": # Linux requires permissions
                subprocess.run(["chmod", "+x", exe_name]) # Ensure it's executable
                subprocess.Popen(["./" + exe_name])
            else: # Windows
                subprocess.Popen([exe_name])
        else:
            # Fallback to python script
            subprocess.Popen([sys.executable, "jynx_operator_ui.py"])

    except Exception as e:
        with open("bootstrapper_fail.log", "a") as f:
            f.write(f"{time.ctime()}: {platform.system()} Surgery failed: {e}\n")
    
    sys.exit()

if __name__ == "__main__":
    perform_surgery()