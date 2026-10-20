"""Run bounded local feasibility checks; never print or save database keys."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "desktop"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wechat-root", default="")
    parser.add_argument("--wechat-read", action="store_true")
    parser.add_argument("--adb", default=str(Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe"))
    args = parser.parse_args()
    from src import qqnt_extract, wechat_probe
    from src.collector import inspect_image

    report = {}
    qq = qqnt_extract.get_extract_status()
    report["desktop_qq"] = {"ok": qq["ok"], "accounts": len(qq.get("accounts", []))}
    if qq["ok"]:
        account = qq["accounts"][0]
        folder = Path(qqnt_extract.get_emoji_dir(qq["userdata_save_path"], account["qq"]))
        samples = []
        for path in list(folder.glob("*"))[:12]:
            if path.is_file():
                try:
                    samples.append(inspect_image(path))
                except Exception:
                    pass
        report["desktop_qq"]["samples"] = samples
    env = wechat_probe.inspect_wechat_environment(args.wechat_root or None)
    report["desktop_wechat"] = {
        "status": env["status"], "accounts": len(env.get("accounts", [])),
    }
    if args.wechat_read:
        account = wechat_probe._pick_account(env)
        if account:
            metadata = wechat_probe._load_metadata_for_account(account)
            report["desktop_wechat"]["candidate_count"] = len(metadata)
            if metadata:
                sample = metadata[0]
                payload = wechat_probe._download_sticker(sample["url"], sample.get("aes_key"))
                if payload:
                    folder = ROOT / ".local" / "feasibility"
                    folder.mkdir(parents=True, exist_ok=True)
                    path = folder / "wechat-sample.media"
                    path.write_bytes(payload)
                    report["desktop_wechat"]["sample"] = inspect_image(path)
    if Path(args.adb).is_file():
        def adb(*parts):
            return subprocess.run([args.adb, *parts], capture_output=True, timeout=45)
        release = adb("shell", "getprop", "ro.build.version.release")
        report["android"] = {"release": release.stdout.decode().strip()}
        result = adb("shell", "find /sdcard/Android/data/com.tencent.mobileqq/Tencent/QQ_Favorite -type f")
        files = result.stdout.decode("utf-8", errors="replace").splitlines()
        report["android"]["qq_cache_count"] = len(files) if result.returncode == 0 else 0
        files = [p for p in files if not Path(p).name.startswith(".")]
        if result.returncode == 0 and files:
            folder = ROOT / ".local" / "feasibility"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "phone-sample.media"
            for remote in files[:30]:
                pulled = adb("pull", remote, str(path))
                if pulled.returncode == 0:
                    try:
                        report["android"]["sample"] = inspect_image(path)
                        break
                    except Exception:
                        continue
    output = ROOT / ".local" / "feasibility.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
