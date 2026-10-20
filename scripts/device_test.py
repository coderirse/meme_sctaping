"""Build/install test APKs without uninstalling the Shizuku-authorized target app."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
env = os.environ.copy()
env.setdefault("JAVA_HOME", "D:/Android-studio_/jbr")
env.setdefault("ANDROID_HOME", str(Path.home() / "AppData/Local/Android/Sdk"))
adb = str(Path(env["ANDROID_HOME"]) / "platform-tools/adb.exe")
app = ROOT / "apps/android"
subprocess.run(["cmd.exe", "/c", "gradlew.bat", ":app:assembleDebug", ":app:assembleDebugAndroidTest",
                "--console=plain"], cwd=app, env=env, check=True, timeout=1200)
for relative in ("app/build/outputs/apk/debug/app-debug.apk",
                 "app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk"):
    subprocess.run([adb, "install", "-r", str(app / relative)], check=True, timeout=180)
if "--install-only" in sys.argv:
    raise SystemExit(0)
result = subprocess.run([adb, "shell", "am", "instrument", "--user", "0", "-w", "-r",
                         "-e", "class", "com.ohmymeme.app.CollectorImportTest,com.ohmymeme.app.ExampleInstrumentedTest",
                         "com.shang.memecollector.debug.test/androidx.test.runner.AndroidJUnitRunner"],
                        capture_output=True, text=True, timeout=600)
log = result.stdout + result.stderr
(ROOT / ".local/device-test-result.txt").write_text(log, "utf-8")
print(log)
if (result.returncode or "FAILURES!!!" in log or "INSTRUMENTATION_FAILED" in log
        or "OK (" not in log or "INSTRUMENTATION_STATUS_CODE: -4" in log):
    raise SystemExit(1)
