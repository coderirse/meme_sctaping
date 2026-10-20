"""Build the customized Windows application or independently signed Android APK."""

import argparse
import importlib.util
import json
import os
import secrets
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"


def run(command, cwd, env=None, timeout=1800):
    subprocess.run([str(x) for x in command], cwd=cwd, env=env, check=True, timeout=timeout)


def windows_sdk():
    import winreg

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows Kits\Installed Roots") as key:
        folder = Path(winreg.QueryValueEx(key, "KitsRoot10")[0])
    versions = [p.name for p in (folder / "Include").iterdir()
                if (p / "ucrt/corecrt.h").is_file() and (p / "um/Windows.h").is_file()]
    if not versions:
        raise RuntimeError("没有完整的 Windows SDK，请安装 Visual Studio C++ Build Tools")
    return max(versions, key=lambda s: tuple(int(n) for n in s.split(".")))


def desktop(args):
    app = ROOT / "apps/desktop"
    build = app / "build/collector-helper"
    # All upstream cleanup targets must remain within this checkout.
    for path in (app / "dist/MemeCollector", app / "build/MemeCollector"):
        if not path.resolve().is_relative_to(app.resolve()):
            raise RuntimeError("构建输出目录超出工程范围")
    run(["cmake", "-S", app / "src/wechat_keyfinder", "-B", build,
         "-G", "Visual Studio 17 2022", "-A", "x64,version=" + windows_sdk(),
         "-DWKF_ENABLE_TEST_KEY=OFF", "-DWKF_BUILD_TESTS=ON"], app)
    run(["cmake", "--build", build, "--config", "Release", "--parallel", "4"], app)
    run(["ctest", "--test-dir", build, "-C", "Release", "--output-on-failure"], app)
    helper = app / "src/wechat_keyfinder/wechat_keyfinder.exe"
    shutil.copy2(build / "Release/wechat_keyfinder.exe", helper)
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("请安装 Node.js 和 npm")
    if not (app / "node_modules").is_dir():
        run([npm, "ci"], app)
    run([npm, "run", "build"], app)
    spec = importlib.util.spec_from_file_location("collector_build", app / "scripts/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.pin_keyfinder_hash(helper)
    try:
        module.build_pyinstaller(target="Windows")
        if not module.verify_keyfinder_bundle():
            raise RuntimeError("打包后的微信辅助程序校验失败")
        shutil.copy2(app / "LICENSE", app / "dist/MemeCollector/LICENSE.txt")
        if not args.portable_only:
            if not module.find_iscc():
                raise RuntimeError("已生成可运行目录，但缺少 Inno Setup；设置 ISCC_DIR 后重试，或使用 --portable-only")
            module.build_windows_installers("0.1.0", "0.1.0")
            installer = app / "dist/MemeCollector-0.1.0-setup.exe"
            if not installer.is_file():
                raise RuntimeError("安装包未生成")
            shutil.copy2(installer, DIST / installer.name)
        shutil.make_archive(str(DIST / "MemeCollector-Windows-0.1.0"), "zip", app / "dist", "MemeCollector")
    finally:
        module.unpin_keyfinder_hash(original)


def android(args):
    app = ROOT / "apps/android"
    env = os.environ.copy()
    java = Path(args.java_home or env.get("JAVA_HOME", ""))
    if not (java / "bin/java.exe").is_file():
        candidate = Path("D:/Android-studio_/jbr")
        if (candidate / "bin/java.exe").is_file():
            java = candidate
        else:
            raise RuntimeError("请设置 JAVA_HOME 为 JDK 17 或以上版本")
    env["JAVA_HOME"] = str(java)
    sdk = args.android_sdk or env.get("ANDROID_HOME") or str(Path.home() / "AppData/Local/Android/Sdk")
    env["ANDROID_HOME"] = sdk
    props = app / "keystore.properties"
    if not props.exists():
        folder = app / "keystore"
        folder.mkdir(exist_ok=True)
        key = folder / "memecollector-release.jks"
        if key.exists():
            raise RuntimeError("签名文件已存在但缺少 keystore.properties，请恢复原密码；不会覆盖现有密钥")
        password = secrets.token_urlsafe(32)
        key_env = env | {"COLLECTOR_KEY_PASS": password}
        run([java / "bin/keytool.exe", "-genkeypair", "-noprompt", "-keystore", key,
             "-storepass:env", "COLLECTOR_KEY_PASS", "-keypass:env", "COLLECTOR_KEY_PASS",
             "-alias", "memecollector", "-keyalg", "RSA", "-keysize", "3072", "-validity", "10000",
             "-dname", "CN=MemeCollector, OU=Personal, O=MemeCollector, C=CN"], app, key_env)
        props.write_text("KEYSTORE_PATH=keystore/memecollector-release.jks\n"
                         f"KEYSTORE_STORE_PASSWORD={password}\nKEYSTORE_KEY_ALIAS=memecollector\n"
                         f"KEYSTORE_KEY_PASSWORD={password}\n", "utf-8")
    run(["cmd.exe", "/c", "gradlew.bat", ":app:testDebugUnitTest", ":app:assembleRelease",
         "--console=plain"], app, env)
    for apk in (app / "app/build/outputs/apk/release").glob("*.apk"):
        shutil.copy2(apk, DIST / apk.name)


def source_archive():
    # Include modified source and notices, never local signing keys or personal samples.
    with zipfile.ZipFile(DIST / "MemeCollector-Source-0.1.0.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name in ("desktop", "android"):
            app = ROOT / "apps" / name
            result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                                    cwd=app, capture_output=True, check=True)
            for relative in result.stdout.decode("utf-8").split("\0"):
                if not relative:
                    continue
                path = app / relative
                if path.is_file():
                    archive.write(path, "apps/" + name + "/" + relative)
        for folder in (ROOT / "scripts", ROOT / "docs"):
            if folder.is_dir():
                for path in folder.rglob("*"):
                    if path.is_file() and "__pycache__" not in path.parts:
                        archive.write(path, str(path.relative_to(ROOT)))
        for name in ("README.md", "LICENSE", "upstream-lock.json", ".gitignore"):
            if (ROOT / name).is_file():
                archive.write(ROOT / name, name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=["desktop", "android", "all", "source"])
    parser.add_argument("--portable-only", action="store_true")
    parser.add_argument("--java-home")
    parser.add_argument("--android-sdk")
    args = parser.parse_args()
    DIST.mkdir(exist_ok=True)
    if args.target in ("desktop", "all"):
        desktop(args)
    if args.target in ("android", "all"):
        android(args)
    source_archive()
    import hashlib

    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in DIST.iterdir() if p.is_file() and p.suffix in (".zip", ".apk", ".exe")}
    (DIST / "SHA256SUMS.json").write_text(json.dumps(checksums, indent=2), "utf-8")


if __name__ == "__main__":
    main()
