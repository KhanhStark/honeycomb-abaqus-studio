import json

import pytest

from honeycomb_studio import store


def sharing_violation():
    error = PermissionError("Windows reader has the destination open")
    error.winerror = 32
    return error


def test_json_write_recovers_from_windows_reader_lock(tmp_path, monkeypatch):
    target = tmp_path / "status.json"
    target.write_text('{"status": "old"}')
    original_replace = store.os.replace
    calls = []

    def replace(source, destination):
        calls.append(source)
        if len(calls) == 1:
            raise sharing_violation()
        original_replace(source, destination)

    monkeypatch.setattr(store.os, "replace", replace)
    monkeypatch.setattr(store.time, "sleep", lambda _: None)
    store.write_json(target, {"status": "solving"})

    assert json.loads(target.read_text()) == {"status": "solving"}
    assert len(calls) == 2
    assert list(tmp_path.iterdir()) == [target]


def test_persistent_lock_preserves_previous_status(tmp_path, monkeypatch):
    target = tmp_path / "status.json"
    target.write_text('{"status": "old"}')

    def replace(source, destination):
        raise sharing_violation()

    monkeypatch.setattr(store.os, "replace", replace)
    monkeypatch.setattr(store.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        store.write_json(target, {"status": "new"})

    assert json.loads(target.read_text()) == {"status": "old"}
    assert list(tmp_path.iterdir()) == [target]
