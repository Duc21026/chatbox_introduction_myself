from backend import embedding_provider


def test_none_provider_makes_no_network_call(monkeypatch):
    monkeypatch.setenv("CHATBOT_EMBEDDING_PROVIDER", "none")

    def fail(*args, **kwargs):
        raise AssertionError("không được gọi mạng")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    assert embedding_provider.provider_status()["name"] == "none"
    assert embedding_provider.embed_texts(["a"]) is None
    assert embedding_provider.embed_query("a") is None
