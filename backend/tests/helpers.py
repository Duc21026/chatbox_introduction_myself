import json
import os
import urllib.request
from types import SimpleNamespace


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
    if expected.casefold() in answer.casefold():
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


def write_text_source(directory, name, content):
    path = os.path.join(str(directory), name)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


class FakeEmbeddings:
    def embed_documents(self, texts):
        return [[float(len(text)), 1.0, 0.0] for text in texts]

    def embed_query(self, text):
        return [float(len(text)), 1.0, 0.0]


class RecordingDB:
    def __init__(self, results):
        self.results = results
        self.queries = []

    def similarity_search_with_score(self, query, k=2):
        self.queries.append((query, k))
        return self.results


class RecordingLLM:
    def __init__(self, content):
        self.content = content
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content=self.content)


class ExplodingDB:
    def similarity_search_with_score(self, query, k=2):
        raise AssertionError("Không được gọi tìm kiếm khi không cần thiết")
