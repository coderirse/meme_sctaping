"""Test the actual Android/Windows encrypted bridge via a temporary ADB TCP tunnel."""

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".local/lan-smoke" / uuid.uuid4().hex
os.environ["APPDATA"] = str(PROFILE / "roaming")
os.environ["LOCALAPPDATA"] = str(PROFILE / "local")
env = os.environ.copy()
env.setdefault("JAVA_HOME", "D:/Android-studio_/jbr")
env.setdefault("ANDROID_HOME", str(Path.home() / "AppData/Local/Android/Sdk"))
adb = str(Path(env["ANDROID_HOME"]) / "platform-tools/adb.exe")
app = ROOT / "apps/android"
subprocess.run(["cmd.exe", "/c", "gradlew.bat", ":app:assembleDebugAndroidTest", "--console=plain"],
               cwd=app, env=env, check=True, timeout=1200)
subprocess.run([adb, "install", "-r", str(app / "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk")],
               check=True, timeout=180)
sys.path.insert(0, str(ROOT / "apps/desktop"))
from src import lan
from src.config import get_config
from src.database import get_db
from src.webui import WebUI

fixtures = app / "app/src/androidTest/assets/collector"
webui = WebUI()
seed = webui._do_import([str(fixtures / "animated.webp")], preserve_original=True)
assert len(seed["ids"]) == 1
secret = secrets.token_hex(32)
with socket.socket() as reserve:
    reserve.bind(("127.0.0.1", 0))
    port = reserve.getsockname()[1]
lan.set_confirm_callback(lambda device: lan.confirm_device(device.get("name") == "MemeCollectorTest"))
assert lan.start(port, secret)
try:
    subprocess.run([adb, "reverse", f"tcp:{port}", f"tcp:{port}"], check=True, timeout=15)
    result = subprocess.run([adb, "shell", "am", "instrument", "--user", "0", "-w", "-r",
                             "-e", "class", "com.ohmymeme.app.LanBridgeTest",
                             "-e", "collector_port", str(port), "-e", "collector_secret", secret,
                             "com.shang.memecollector.debug.test/androidx.test.runner.AndroidJUnitRunner"],
                            capture_output=True, text=True, timeout=180)
    log = result.stdout + result.stderr
    (ROOT / ".local/lan-device-test.txt").write_text(log, "utf-8")
    assert result.returncode == 0 and "OK (1 test)" in log and "STATUS_CODE: -4" not in log, log
    expected = (fixtures / "animated.gif").read_bytes()
    row = get_db().get_by_hash(hashlib.sha256(expected).hexdigest())
    assert row and (get_config().cache_dir / row["filename"]).read_bytes() == expected
    assert len(get_db().get_all()) == 2
    report = {"transport": "ADB TCP tunnel", "encrypted_handshake": True,
              "device_confirmation": True, "desktop_to_android_webp": True,
              "android_to_desktop_gif": True, "bytes_preserved": True, "duplicate_push_deduplicated": True}
    (ROOT / ".local/lan-smoke-result.json").write_text(json.dumps(report, indent=2), "utf-8")
    print(json.dumps(report))
finally:
    lan.stop()
    subprocess.run([adb, "reverse", "--remove", f"tcp:{port}"], capture_output=True, timeout=15)
