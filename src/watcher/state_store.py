"""직전 빈자리 상태를 JSON 파일로 저장/로드."""
import json
import os


def load_state(path: str) -> dict:
    """저장된 상태를 로드. 파일 없거나 손상되면 빈 dict."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path: str, state: dict) -> None:
    """상태를 JSON으로 저장 (원자적 쓰기)."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, path)
