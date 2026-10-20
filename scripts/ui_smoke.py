"""Exercise the real WebView2/Vue bridge using an isolated profile and test images."""

import hashlib
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / ".local/ui-smoke"
PROFILE.mkdir(parents=True, exist_ok=True)
os.environ["APPDATA"] = str(PROFILE / "roaming")
os.environ["LOCALAPPDATA"] = str(PROFILE / "local")
sys.path.insert(0, str(ROOT / "apps/desktop"))

import webview
from src.config import get_config
from src.database import get_db
from src.webui import WebUI


def wait_until(callback, timeout=30):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = callback()
        if value:
            return value
        time.sleep(0.2)
    raise RuntimeError("UI smoke test timed out")


cfg = get_config()
source = PROFILE / "source"
account = "777777"
folder = source / account / "nt_qq/nt_data/Emoji/personal_emoji/Ori"
folder.mkdir(parents=True, exist_ok=True)
fixtures = ROOT / "apps/android/app/src/androidTest/assets/collector"
for name in ("animated.gif", "animated.webp"):
    shutil.copy2(fixtures / name, folder / name)
cfg.set("collector_qq_root", str(source))
cfg.set("collector_qq_account", account)
cfg.set("guide", "ok")
cfg.set("show_startup_animation", False)
cfg.save()
ui = WebUI()


def automation():
    report = {"pid": os.getpid(), "ok": False}
    try:
        win = wait_until(lambda: ui._window)
        wait_until(lambda: win.evaluate_js("!!Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='导入')"))
        win.evaluate_js("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='导入').click()")
        wait_until(lambda: win.evaluate_js("!!Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='收集 QQ 表情')"))
        win.evaluate_js("Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='收集 QQ 表情').click()")
        wait_until(lambda: win.evaluate_js("!!document.querySelector('.collector-controls button.btn-primary:not(:disabled)')"))
        win.evaluate_js("document.querySelector('.collector-controls button.btn-primary').click()")
        wait_until(lambda: ui._collector.snapshot()["status"] == "ready")
        wait_until(lambda: win.evaluate_js("document.querySelectorAll('.collector-grid article').length === 2"))
        win.evaluate_js("document.querySelector('.collector-grid input[type=checkbox]').click()")
        wait_until(lambda: win.evaluate_js("!!document.querySelector('.collector-dialog footer button.btn-primary:not(:disabled)')"))
        win.evaluate_js("document.querySelector('.collector-dialog footer button.btn-primary').click()")
        wait_until(lambda: ui._collector.snapshot()["status"] == "done")
        snapshot = ui._collector.snapshot()
        assert snapshot["imported"] + snapshot["duplicates"] == 1
        assert snapshot["failed"] == 0
        assert len(get_db().get_all()) == 1
        row = get_db().get_all()[0]
        saved = cfg.cache_dir / row["filename"]
        assert hashlib.sha256(saved.read_bytes()).hexdigest() == row["file_hash"]
        wait_until(lambda: win.evaluate_js("document.querySelectorAll('.collector-grid article').length === 1"))
        report.update(ok=True, selected_saved=1, unselected_not_saved=True,
                      only_new_hides_saved=True, original_hash_verified=True,
                      screenshot_ready=True)
    except Exception as error:
        report["error"] = str(error)
    (ROOT / ".local/ui-smoke-result.json").write_text(json.dumps(report, indent=2), "utf-8")
    print(json.dumps(report), flush=True)
    if os.environ.get("COLLECTOR_HOLD_UI") == "1":
        end = time.monotonic() + 120
        while time.monotonic() < end and not (ROOT / ".local/ui-smoke-close").exists():
            time.sleep(0.5)
    ui._window.destroy()


threading.Thread(target=automation, daemon=True).start()
ui.start()
