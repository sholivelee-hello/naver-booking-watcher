from watcher.state_store import load_state, save_state


def test_load_missing_file_returns_empty(tmp_path):
    path = tmp_path / "state.json"
    assert load_state(str(path)) == {}


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / "state.json"
    data = {"2026-06-20": 3, "2026-06-21": 1}
    save_state(str(path), data)
    assert load_state(str(path)) == data


def test_load_corrupt_file_returns_empty(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("not json{{{")
    assert load_state(str(path)) == {}
