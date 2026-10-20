"""Verify selection, byte preservation and incremental filtering in the real Android UI."""

import hashlib
import argparse
import io
import json
import re
import sqlite3
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADB = str(Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe")
parser = argparse.ArgumentParser()
parser.add_argument("--package", choices=["com.shang.memecollector.debug", "com.shang.memecollector"], default="com.shang.memecollector.debug")
PACKAGE = parser.parse_args().package
LOCAL = ROOT / ".local/phone-ui"
LOCAL.mkdir(parents=True, exist_ok=True)


def adb(*args):
    return subprocess.run([ADB, *args], capture_output=True, check=True, timeout=25).stdout


def snapshot():
    adb("shell", "uiautomator", "dump", "/data/local/tmp/memecollector-ui.xml")
    return list(ET.fromstring(adb("exec-out", "cat", "/data/local/tmp/memecollector-ui.xml")).iter("node"))


def tap(node):
    coords = list(map(int, re.findall(r"\d+", node.get("bounds"))))
    adb("shell", "input", "tap", str((coords[0] + coords[2]) // 2), str((coords[1] + coords[3]) // 2))


def wait_for(predicate, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        nodes = snapshot()
        result = predicate(nodes)
        if result:
            return nodes, result
        time.sleep(0.4)
    raise RuntimeError("等待手机界面超时")


def candidate_count(nodes):
    node = next((n for n in nodes if n.get("resource-id") == PACKAGE + ":id/qq_sel_count"), None)
    return int(re.search(r"候选\s*(\d+)", node.get("text")).group(1)) if node is not None else None


nodes, count = wait_for(lambda nodes: candidate_count(nodes))
row = next(n for n in nodes if n.get("package") == PACKAGE
           and re.match(r"^[a-zA-Z0-9_.-]+\.(jpg|png|gif|webp)（", n.get("text", ""), re.I))
name = row.get("text").split("（")[0]
payload = adb("exec-out", "cat", "/sdcard/Android/data/com.tencent.mobileqq/Tencent/QQ_Favorite/" + name)
original_hash = hashlib.sha256(payload).hexdigest()
tap(row)
nodes = snapshot()
assert any("已选 1" in n.get("text", "") for n in nodes)
button = next(n for n in nodes if n.get("package") == PACKAGE
              and n.get("resource-id") == "android:id/button1" and n.get("text") == "导入")
tap(button)
nodes, _ = wait_for(lambda nodes: any(n.get("text") == "保存结果" for n in nodes))
message = "\n".join(n.get("text", "") for n in nodes if n.get("package") == PACKAGE)
assert "成功 1" in message or "重复 1" in message, message
tap(next(n for n in nodes if n.get("resource-id") == "android:id/button1" and n.get("text") == "知道了"))
base = "/sdcard/Android/data/" + PACKAGE + "/files/"
database = LOCAL / "library.db"
database.write_bytes(adb("exec-out", "cat", base + "memes.db"))
wal = subprocess.run([ADB, "exec-out", "cat", base + "memes.db-wal"], capture_output=True, timeout=20)
if wal.returncode == 0 and wal.stdout:
    database.with_name(database.name + "-wal").write_bytes(wal.stdout)
with sqlite3.connect(database) as connection:
    record = connection.execute("SELECT filename FROM memes WHERE file_hash=?", (original_hash,)).fetchone()
assert record, "保存后的内容哈希未在表情库找到"
stored = adb("exec-out", "cat", base + "cache/" + record[0])
assert payload == stored, "保存后原文件字节发生变化"
adb("shell", "am", "start", "--user", "0", "-n", PACKAGE + "/com.ohmymeme.app.MainActivity", "--ez", "collector_qq", "true")
nodes, updated = wait_for(lambda nodes: candidate_count(nodes))
assert updated == count - 1, (count, updated)
tap(next(n for n in nodes if n.get("resource-id") == "android:id/button2" and n.get("text") == "取消"))
report = {"selected": 1, "original_bytes_preserved": True, "sha256_verified": True,
          "candidates_before": count, "candidates_after": updated, "incremental_filter": True}
from PIL import Image

with Image.open(io.BytesIO(stored)) as image:
    report["saved_image"] = {"format": image.format, "frames": getattr(image, "n_frames", 1)}
report["package"] = PACKAGE
(ROOT / ".local/phone-ui-result.json").write_text(json.dumps(report, indent=2), "utf-8")
print(json.dumps(report))
