"""Verify the user-level installer in a controlled workspace directory, then uninstall."""

import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = (ROOT / ".local/install-smoke").resolve()
if not TARGET.is_relative_to((ROOT / ".local").resolve()):
    raise RuntimeError("安装测试目录超出工作区")
installer = ROOT / "dist/MemeCollector-0.1.0-setup.exe"
report = {}
try:
    subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                    "/NOICONS", "/TASKS=", f"/DIR={TARGET}", f"/LOG={ROOT / '.local/install-smoke.log'}"],
                   check=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
    executable = TARGET / "MemeCollector.exe"
    helper = TARGET / "_internal/src/wechat_keyfinder/wechat_keyfinder.exe"
    assert executable.is_file() and helper.is_file()
    subprocess.run([str(helper), "--help"], check=True, capture_output=True,
                   timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    profile = ROOT / ".local/install-profile"
    env = os.environ | {"APPDATA": str(profile / "roaming"), "LOCALAPPDATA": str(profile / "local")}
    subprocess.run([str(executable), "--help"], env=env, check=True,
                   timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    report.update(installer=True, installed_executable_entry=True, bundled_helper=True)
finally:
    uninstaller = TARGET / "unins000.exe"
    if uninstaller.is_file() and uninstaller.resolve().is_relative_to(TARGET):
        subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                        f"/LOG={ROOT / '.local/uninstall-smoke.log'}"],
                       check=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
    deadline = time.monotonic() + 30
    while (TARGET / "MemeCollector.exe").exists() and time.monotonic() < deadline:
        time.sleep(0.5)
    report["uninstalled"] = not (TARGET / "MemeCollector.exe").exists()
    (ROOT / ".local/package-smoke.json").write_text(json.dumps(report, indent=2), "utf-8")
print(json.dumps(report))
assert report["uninstalled"], "卸载后程序仍存在，请检查 .local/uninstall-smoke.log"
