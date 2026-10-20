import hashlib
import threading

import pytest
from PIL import Image

from src import collector, webui
from src.database import MemeDB


@pytest.fixture
def local_env(monkeypatch, tmp_path):
    class Config:
        cache_dir = tmp_path / "cache"
        data_dir = tmp_path / "data"
        thumbnail_dir = tmp_path / "thumbs"

        def __init__(self):
            self.values = {}
            for path in (self.cache_dir, self.data_dir, self.thumbnail_dir):
                path.mkdir()

        def get(self, name, default=None):
            return self.values.get(name, default)

        def set(self, name, value):
            self.values[name] = value

        def save(self):
            pass

    cfg = Config()
    db = MemeDB(tmp_path / "library.db")
    for module in (collector, webui):
        monkeypatch.setattr(module, "get_config", lambda: cfg)
        monkeypatch.setattr(module, "get_db", lambda: db)
    monkeypatch.setattr(webui, "build_manifest", lambda: None)
    return cfg, db, webui.WebUI()


@pytest.fixture(params=["PNG", "JPEG", "GIF", "WEBP"])
def original_image(request, tmp_path):
    path = tmp_path / "mislabelled.jpg"
    first = Image.new("RGBA", (30, 24), (255, 0, 0, 0))
    second = Image.new("RGBA", (30, 24), (0, 255, 0, 255))
    if request.param in ("GIF", "WEBP"):
        first.save(path, format=request.param, save_all=True, append_images=[second],
                   duration=[60, 120], loop=0, lossless=True)
    else:
        first.convert("RGB").save(path, format=request.param)
    return path, request.param


def test_original_bytes_and_animation_survive(local_env, original_image):
    cfg, db, ui = local_env
    path, image_format = original_image
    payload = path.read_bytes()
    info = collector.inspect_image(path)
    assert info["animated"] == (image_format in ("GIF", "WEBP"))
    result = ui._do_import([str(path)], preserve_original=True)
    assert len(result["ids"]) == 1
    row = db.get_all()[0]
    saved = cfg.cache_dir / row["filename"]
    assert saved.read_bytes() == payload
    assert row["file_hash"] == hashlib.sha256(payload).hexdigest()
    assert saved.suffix == {"PNG": ".png", "JPEG": ".jpg", "GIF": ".gif", "WEBP": ".webp"}[image_format]
    with Image.open(path) as original, Image.open(saved) as output:
        assert getattr(original, "n_frames", 1) == getattr(output, "n_frames", 1)
        for frame in range(getattr(original, "n_frames", 1)):
            original.seek(frame)
            output.seek(frame)
            assert original.convert("RGBA").tobytes() == output.convert("RGBA").tobytes()
            assert original.info.get("duration") == output.info.get("duration")
    assert ui._do_import([str(path)])["skipped_dup"] == 1


def test_invalid_content_is_not_silently_renamed(local_env, tmp_path):
    cfg, db, ui = local_env
    path = tmp_path / "fake.gif"
    path.write_bytes(b"wxgf unsupported private container")
    result = ui._do_import([str(path)])
    assert result["unsupported"] == 1
    assert result["errors"]
    assert not db.get_all()
    assert not list(cfg.cache_dir.iterdir())


@pytest.mark.parametrize("failure", ["copy", "database"])
def test_failure_cleans_partial_without_changing_source(local_env, original_image, monkeypatch, failure):
    import shutil

    cfg, db, ui = local_env
    path, _ = original_image
    payload = path.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("simulated disk/database failure")

    monkeypatch.setattr(shutil if failure == "copy" else db,
                        "copyfile" if failure == "copy" else "add_meme", fail)
    result = ui._do_import([str(path)])
    assert result["errors"]
    assert not result["ids"]
    assert path.read_bytes() == payload
    assert not list(cfg.cache_dir.iterdir())


def scan_qq(ui, tmp_path, originals):
    root = tmp_path / "qq"
    folder = root / "12345/nt_qq/nt_data/Emoji/personal_emoji/Ori"
    folder.mkdir(parents=True, exist_ok=True)
    for number, payload in enumerate(originals):
        (folder / str(number)).write_bytes(payload)
    service = ui._collector
    assert service.scan("qq", str(root), "12345")["ok"]
    service.thread.join(5)
    assert not service.thread.is_alive()
    return service


def test_selected_only_incremental_and_no_private_metadata(local_env, tmp_path):
    import io

    _, db, ui = local_env
    image = io.BytesIO()
    Image.new("RGB", (8, 8), "red").save(image, "PNG")
    other = io.BytesIO()
    Image.new("RGB", (8, 8), "blue").save(other, "PNG")
    service = scan_qq(ui, tmp_path, [image.getvalue(), other.getvalue(), b"wxgf"])
    snapshot = service.snapshot()
    assert len(snapshot["items"]) == 3
    assert sum(bool(i["error"]) for i in snapshot["items"]) == 1
    assert all("metadata" not in item and "path" not in item for item in snapshot["items"])
    chosen = next(i["id"] for i in snapshot["items"] if not i["error"])
    assert service.save(snapshot["session"], [chosen])["ok"]
    service.thread.join(5)
    assert service.snapshot()["imported"] == 1
    assert len(db.get_all()) == 1
    service = scan_qq(ui, tmp_path, [image.getvalue(), other.getvalue(), b"wxgf"])
    assert sum(i["duplicate"] for i in service.snapshot()["items"]) == 1
    assert not service.save("stale-session", [chosen])["ok"]
    assert service.preview(service.session, "../../private") is None


def test_cancel_scan_and_reject_concurrent_scan(local_env, tmp_path, monkeypatch):
    _, _, ui = local_env
    entered, release = threading.Event(), threading.Event()

    def blocked(path):
        entered.set()
        release.wait(5)
        raise ValueError("test")

    monkeypatch.setattr(collector, "inspect_image", blocked)
    root = tmp_path / "qq"
    folder = root / "123/nt_qq/nt_data/Emoji/personal_emoji/Ori"
    folder.mkdir(parents=True)
    (folder / "sample").write_bytes(b"test")
    service = ui._collector
    assert service.scan("qq", str(root), "123")["ok"]
    assert entered.wait(5)
    assert not service.scan("qq", str(root), "123")["ok"]
    service.cancel()
    release.set()
    service.thread.join(5)
    assert service.snapshot()["status"] == "cancelled"


def test_wechat_download_is_lazy_and_failure_retryable(local_env, tmp_path, monkeypatch):
    import io

    _, _, ui = local_env
    buffer = io.BytesIO()
    Image.new("RGB", (16, 16), "green").save(buffer, "PNG")
    data = buffer.getvalue()
    meta = {"md5": hashlib.md5(data).hexdigest(), "url": "https://private", "aes_key": "secret"}
    account = {"id": "test", "path": "test", "status": "supported", "db_path": "db"}
    monkeypatch.setattr(collector.wechat_probe, "inspect_wechat_environment", lambda root: {
        "status": "supported", "root": "root", "accounts": [account]})
    monkeypatch.setattr(collector.wechat_probe, "_read_plaintext_metadata", lambda path: [meta])
    calls = []

    def download(*args):
        calls.append(args)
        return None if len(calls) == 1 else data

    monkeypatch.setattr(collector.wechat_probe, "_download_sticker", download)
    service = ui._collector
    assert service.scan("wechat", "root", "test")["ok"]
    service.thread.join(5)
    assert not calls
    item = service.snapshot()["items"][0]
    assert "secret" not in str(service.snapshot())
    assert service.preview(service.session, item["id"]) is None
    assert service.retry(item["id"])
    saved = service.preview(service.session, item["id"])
    assert saved and collector.Path(saved).read_bytes() == data
    assert not list(service.stage.glob("*.part"))
