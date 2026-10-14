import pytest

from lumalock.core.exceptions import Cancelled, UserError
from lumalock.core.model_transfer import receive_file


class Response:
    def __init__(self, status, chunks, headers=None):
        self.status_code, self.chunks, self.headers = status, chunks, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        pass

    def iter_content(self, **kwargs):
        yield from self.chunks


ITEM = {"repo": "test/model", "file": "model.gguf", "revision": "pinned", "size": 6}


def test_resume_appends_only_valid_range(tmp_path, monkeypatch):
    target = tmp_path / "model.gguf"
    target.with_suffix(".gguf.part").write_bytes(b"abc")
    calls = []

    def request(url, **kwargs):
        calls.append(kwargs["headers"].get("Range"))
        return Response(206, [b"def"], {"Content-Range": "bytes 3-5/6"})

    monkeypatch.setattr("requests.get", request)
    receive_file(ITEM, target, lambda: False, lambda *args: None)
    assert calls == ["bytes=3-"]
    assert target.with_suffix(".gguf.part").read_bytes() == b"abcdef"
    assert not target.exists()  # Only checksum verification may publish the final file.


def test_ignored_range_restarts_without_corrupt_append(tmp_path, monkeypatch):
    target = tmp_path / "model.gguf"
    target.with_suffix(".gguf.part").write_bytes(b"bad")
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Response(200, [b"abcdef"]))
    receive_file(ITEM, target, lambda: False, lambda *args: None)
    assert target.with_suffix(".gguf.part").read_bytes() == b"abcdef"


def test_pause_retains_bytes_and_never_publishes_file(tmp_path, monkeypatch):
    target = tmp_path / "model.gguf"
    checks = iter([False, False, True])
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: Response(200, [b"abc", b"def"]))
    with pytest.raises(Cancelled):
        receive_file(ITEM, target, lambda: next(checks), lambda *args: None)
    assert target.with_suffix(".gguf.part").read_bytes() == b"abc"
    assert not target.exists()


def test_incorrect_range_is_rejected(tmp_path, monkeypatch):
    target = tmp_path / "model.gguf"
    target.with_suffix(".gguf.part").write_bytes(b"abc")
    monkeypatch.setattr(
        "requests.get",
        lambda *args, **kwargs: Response(206, [b"def"], {"Content-Range": "bytes 0-2/6"}),
    )
    with pytest.raises(UserError, match="range"):
        receive_file(ITEM, target, lambda: False, lambda *args: None)
    assert target.with_suffix(".gguf.part").read_bytes() == b"abc"
