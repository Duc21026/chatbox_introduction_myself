import json
import urllib.request


def _model_present(model, installed):
    if model in installed:
        return True
    base = model.split(":", 1)[0]
    for name in installed:
        if name == model or name.startswith(model + "-"):
            return True
        if ":" not in model and name.split(":", 1)[0] == base:
            return True
    return False


def ollama_ready(answer_model, embedding_model, base_url, timeout=2):
    try:
        url = base_url.rstrip("/") + "/api/tags"
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except Exception:
        return False
    installed = {item.get("name", "") for item in payload.get("models", [])}
    return _model_present(answer_model, installed) and _model_present(
        embedding_model, installed
    )


def contains_answer(answer, expected):
    if expected is None:
        return False
    if expected in answer:
        return True
    try:
        expected_number = float(expected)
    except ValueError:
        return False
    for token in answer.replace(",", ".").split():
        try:
            if abs(float(token) - expected_number) < 1e-9:
                return True
        except ValueError:
            continue
    return False
