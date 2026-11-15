import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import requests


def get_free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_sandbox(target_dir="target"):
    temp_dir = tempfile.mkdtemp(prefix="verity_sandbox_")

    if os.path.exists(target_dir) and os.path.isdir(target_dir):
        for item in os.listdir(target_dir):
            s = os.path.join(target_dir, item)
            d = os.path.join(temp_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, dirs_exist_ok=True)
            else:
                shutil.copy2(s, d)

    db_path = os.path.join(temp_dir, "notes.db")
    port = get_free_port()
    base_url = f"http://127.0.0.1:{port}"

    env = {
        "DATABASE": db_path,
        "PORT": str(port),
        "FLASK_APP": "app",
        "HOME": temp_dir,
        "TMPDIR": temp_dir,
        "PATH": os.defpath,
        "PYTHONNOUSERSITE": "1",
    }

    # 1. Run target/seed.py if it exists in the target directory
    seed_script = os.path.join(temp_dir, "seed.py")
    if os.path.exists(seed_script):
        subprocess.run(
            [sys.executable, seed_script],
            cwd=temp_dir,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    # 2. Launch Flask using the exact command structure from target/Dockerfile
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "flask",
            "--app",
            "app",
            "run",
            "--host=127.0.0.1",
            f"--port={port}",
        ],
        cwd=temp_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    # 3. Wait until the server is up and accepting connections
    for _ in range(30):
        if process.poll() is not None:
            _, err = process.communicate()
            print(f"[Sandbox Crash Error]:\n{err}")
            break
        try:
            res = requests.get(f"{base_url}/admin/users", timeout=0.5)
            if res.status_code < 500:
                break
        except requests.exceptions.RequestException:
            time.sleep(0.2)

    def stop():
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
        shutil.rmtree(temp_dir, ignore_errors=True)

    return base_url, temp_dir, stop