from pathlib import Path
import os
import subprocess
import time
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent.parent
URL = 'http://127.0.0.1:8765/'
def ready():
    try:
        with urllib.request.urlopen(URL, timeout=1) as response:
            return response.status == 200
    except OSError:
        return False

if not ready():
    env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
    subprocess.Popen([str(ROOT / '.venv' / 'Scripts' / 'python.exe'), str(ROOT / 'web' / 'server.py'), '--no-browser'], cwd=str(ROOT), env=env, creationflags=subprocess.CREATE_NO_WINDOW)
    for _ in range(20):
        if ready():
            break
        time.sleep(0.25)
webbrowser.open(URL)
