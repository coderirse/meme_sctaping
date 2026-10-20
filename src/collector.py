import hashlib
import json
import os
import shutil
import threading
import uuid
from pathlib import Path

from PIL import Image

from . import qqnt_extract, wechat_probe
from .config import get_config
from .database import get_db

_FORMATS = {"PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "WEBP": ".webp"}


# 校验真实图片内容，完整解码动图而不重编码原文件。
def inspect_image(path):
    with Image.open(path) as image:
        ext = _FORMATS.get(image.format)
        if not ext:
            raise ValueError("不支持的表情格式，仅支持 PNG、JPEG、GIF、WebP")
        width, height = image.size
        frames = getattr(image, "n_frames", 1)
        if width <= 0 or height <= 0 or width * height > 40_000_000:
            raise ValueError("图片尺寸无效或过大")
        if frames > 3000:
            raise ValueError("动画帧数过多")
        for frame in range(frames):
            image.seek(frame)
            image.load()
    return {
        "ext": ext,
        "width": width,
        "height": height,
        "animated": frames > 1,
        "frames": frames,
    }


# 独立任务保存候选与临时原文件，前端只持有随机标识。
class Collector:
    def __init__(self, webui):
        self.webui = webui
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.thread = None
        self.session = ""
        self.items = {}
        self.state = {"status": "idle", "error": "", "done": 0, "total": 0}
        self.stage = None

    # 返回采集入口状态；账号和目录选择记入本机配置。
    def environment(self, source, root=""):
        cfg = get_config()
        root = root or cfg.get("collector_" + source + "_root", "")
        if source == "qq":
            result = qqnt_extract.get_extract_status(userdata_save_path=root or None)
            return {
                "ok": result["ok"],
                "message": result.get("message", ""),
                "root": result.get("userdata_save_path", root),
                "accounts": [
                    {"id": a["qq"], "label": a["qq"]}
                    for a in result.get("accounts", [])
                ],
                "selected": cfg.get("collector_qq_account", ""),
            }
        if source != "wechat":
            return {"ok": False, "message": "未知来源", "accounts": []}
        result = wechat_probe.inspect_wechat_environment(root or None)
        return {
            "ok": result["status"] in wechat_probe._PROCEEDABLE,
            "message": {
                "not_found": "找不到微信数据目录，请选择 xwechat_files 文件夹",
                "unsupported_version": "需要 Windows 微信 4.x",
                "no_database": "请登录微信并打开添加的表情面板，再刷新",
                "no_accounts": "目录中没有可用账号",
            }.get(result["status"], ""),
            "root": result.get("root", root),
            "accounts": [
                {"id": a["id"], "label": a["id"]}
                for a in result.get("accounts", [])
                if a["status"] in wechat_probe._PROCEEDABLE
            ],
            "selected": cfg.get("collector_wechat_account", ""),
        }

    # 不允许活动任务被另一任务覆盖。
    def scan(self, source, root, account):
        with self.lock:
            if self.thread and self.thread.is_alive():
                return {"ok": False, "error": "已有采集任务，请等待或取消"}
            env = self.environment(source, root)
            if not env["ok"]:
                return {"ok": False, "error": env["message"]}
            if account not in {a["id"] for a in env["accounts"]}:
                return {"ok": False, "error": "请选择可用账号"}
            self._cleanup()
            self.session = uuid.uuid4().hex
            self.stage = get_config().data_dir / "collector" / self.session
            self.stage.mkdir(parents=True, exist_ok=True)
            self.cancelled.clear()
            self.items = {}
            self.state = {
                "status": "scanning",
                "error": "",
                "done": 0,
                "total": 0,
                "source": source,
                "session": self.session,
            }
            cfg = get_config()
            cfg.set("collector_" + source + "_root", env["root"])
            cfg.set("collector_" + source + "_account", account)
            cfg.save()
            self.thread = threading.Thread(
                target=self._scan_worker,
                args=(source, env["root"], account),
                daemon=True,
            )
            self.thread.start()
            return {"ok": True}

    # QQ 读取本地原文件；微信只读取候选清单，预览和保存时才下载。
    def _scan_worker(self, source, root, account):
        try:
            if source == "qq":
                folder = Path(qqnt_extract.get_emoji_dir(root, account))
                entries = [
                    {"path": str(p), "name": p.name}
                    for p in folder.rglob("*")
                    if p.is_file()
                ]
            else:
                env = wechat_probe.inspect_wechat_environment(root)
                selected = wechat_probe._pick_account(env, account)
                if not selected:
                    raise ValueError("微信账号已不可用，请重新检测")
                if selected["status"] == "supported":
                    entries = wechat_probe._read_plaintext_metadata(selected["db_path"])
                else:
                    binary = wechat_probe.ensure_wechat_keyfinder()
                    if not binary:
                        raise ValueError("微信辅助程序缺失或校验失败，请重新安装")
                    result = wechat_probe._run_keyfinder(binary, selected["db_path"])
                    if not result.get("ok"):
                        raise ValueError(
                            "无法读取微信表情密钥，请登录并打开表情面板后重试"
                        )
                    entries = wechat_probe._load_sticker_metadata(
                        selected["db_path"], result["key"]
                    )
                    if not entries:
                        raise ValueError("表情清单为空或当前微信数据库格式尚未适配")
            index = self._read_index()
            with self.lock:
                self.state["total"] = len(entries)
            for number, entry in enumerate(entries):
                if self.cancelled.is_set():
                    break
                token = uuid.uuid4().hex
                key = (
                    source
                    + ":"
                    + account
                    + ":"
                    + entry.get("md5", entry.get("path", ""))
                )
                item = {
                    "id": token,
                    "key": key,
                    "name": entry.get("name", entry.get("md5", token)),
                    "path": entry.get("path", ""),
                    "metadata": entry,
                    "duplicate": False,
                    "error": "",
                    "size": 0,
                    "lock": threading.Lock(),
                }
                try:
                    if item["path"]:
                        item.update(inspect_image(item["path"]))
                        item["size"] = os.path.getsize(item["path"])
                        item["hash"] = self._hash(item["path"])
                    else:
                        item["hash"] = index.get(key, "")
                    item["duplicate"] = bool(
                        item.get("hash") and get_db().get_by_hash(item["hash"])
                    )
                except Exception:
                    item["error"] = "文件不完整或格式不支持"
                with self.lock:
                    self.items[token] = item
                    self.state["done"] = number + 1
            with self.lock:
                self.state["status"] = (
                    "cancelled" if self.cancelled.is_set() else "ready"
                )
        except Exception as error:
            with self.lock:
                self.state.update(status="failed", error=str(error))

    # 任务状态不包含本地路径、CDN 地址或密钥。
    def snapshot(self):
        with self.lock:
            result = dict(self.state)
            result["items"] = [
                {
                    k: v
                    for k, v in item.items()
                    if k
                    in {
                        "id",
                        "name",
                        "duplicate",
                        "error",
                        "size",
                        "animated",
                        "ext",
                    }
                }
                for item in self.items.values()
            ]
            result["storage"] = str(get_config().cache_dir)
            return result

    # 仅解析当前任务内的标识，下载后验证原格式和内容哈希。
    def preview(self, session, token):
        with self.lock:
            if session != self.session or token not in self.items:
                return None
            item = self.items[token]
            stage = self.stage
        with item["lock"]:
            if item["error"]:
                return None
            if item["path"]:
                return item["path"]
            try:
                meta = item["metadata"]
                data = wechat_probe._download_sticker(meta["url"], meta.get("aes_key"))
                if not data:
                    raise ValueError("下载失败，请刷新表情或检查网络后重试")
                if hashlib.md5(data).hexdigest() != meta["md5"]:
                    raise ValueError("表情原文件校验失败")
                path = stage / (token + ".part")
                try:
                    path.write_bytes(data)
                    info = inspect_image(path)
                    final = path.with_suffix(info["ext"])
                    os.replace(path, final)
                finally:
                    path.unlink(missing_ok=True)
                with self.lock:
                    if session != self.session:
                        final.unlink(missing_ok=True)
                        return None
                    item.update(info, path=str(final), size=len(data))
                    item["hash"] = hashlib.sha256(data).hexdigest()
                    item["duplicate"] = bool(get_db().get_by_hash(item["hash"]))
                return str(final)
            except Exception as error:
                with self.lock:
                    item["error"] = str(error)
                return None

    # 已失败候选可主动重试，避免自动下载循环。
    def retry(self, token):
        with self.lock:
            item = self.items.get(token)
            if item and not item["path"]:
                item["error"] = ""
                return True
        return False

    # 只导入明确选择的候选；已有任务时拒绝并发提交。
    def save(self, session, tokens):
        with self.lock:
            if session != self.session:
                return {"ok": False, "error": "候选列表已失效，请重新扫描"}
            if self.thread and self.thread.is_alive():
                return {"ok": False, "error": "已有采集任务"}
            selected = list(dict.fromkeys(tokens))
            if not selected or any(token not in self.items for token in selected):
                return {"ok": False, "error": "请选择有效表情"}
            self.cancelled.clear()
            self.state.update(
                status="saving",
                done=0,
                total=len(selected),
                imported=0,
                duplicates=0,
                failed=0,
                errors=[],
                error="",
            )
            self.thread = threading.Thread(
                target=self._save_worker, args=(session, selected), daemon=True
            )
            self.thread.start()
        return {"ok": True}

    # 导入复用原有数据库和 manifest，失败不登记为已收集。
    def _save_worker(self, session, tokens):
        index = self._read_index()
        try:
            for token in tokens:
                if self.cancelled.is_set():
                    break
                item = self.items[token]
                path = self.preview(session, token)
                try:
                    if not path:
                        raise ValueError(item["error"] or "文件不可读取")
                    result = self.webui._do_import(
                        [path], [item["name"]], preserve_original=True
                    )
                    if result.get("errors") or result.get("rejected"):
                        raise ValueError("文件不支持、超过限制或无法写入保存目录")
                    count = len(result["ids"])
                    duplicate = result.get("skipped_dup", 0)
                    if not count and not duplicate:
                        raise ValueError("文件未能保存，请检查目录空间与权限")
                    with self.lock:
                        self.state["imported"] += count
                        self.state["duplicates"] += duplicate
                        item["duplicate"] = True
                    index[item["key"]] = item["hash"]
                except Exception as error:
                    with self.lock:
                        self.state["failed"] += 1
                        self.state["errors"].append(
                            {"name": item["name"], "error": str(error)}
                        )
                finally:
                    with self.lock:
                        self.state["done"] += 1
            self._write_index(index)
            with self.lock:
                self.state["status"] = (
                    "cancelled" if self.cancelled.is_set() else "done"
                )
        except Exception as error:
            with self.lock:
                self.state.update(status="failed", error=str(error))

    # 请求取消；已完成保存的原文件仍保留。
    def cancel(self):
        self.cancelled.set()
        return True

    # 增量索引仅保存内容哈希，写入失败不会破坏已有索引。
    def _read_index(self):
        try:
            value = json.loads(
                (get_config().data_dir / "collector-index.json").read_text("utf-8")
            )
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    # 原子替换采集索引。
    def _write_index(self, value):
        path = get_config().data_dir / "collector-index.json"
        temp = path.with_suffix(".tmp")
        try:
            temp.write_text(json.dumps(value), "utf-8")
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    # 上一轮临时文件仅在其所有预览结束后清理。
    def _cleanup(self):
        stage, items = self.stage, list(self.items.values())

        # 不持有任务锁等待网络预览，避免与下载完成回调互锁。
        def cleanup():
            for item in items:
                with item["lock"]:
                    pass
            if stage:
                shutil.rmtree(stage, ignore_errors=True)

        threading.Thread(target=cleanup, daemon=True).start()

    # 计算原文件完整内容哈希。
    @staticmethod
    def _hash(path):
        with open(path, "rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
