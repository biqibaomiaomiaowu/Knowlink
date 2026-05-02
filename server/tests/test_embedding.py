import json

import pytest

from server.ai.embedding import VivoEmbeddingClient, get_configured_embedding_client


def test_configured_embedding_client_requires_enable_flag_and_app_key(monkeypatch):
    monkeypatch.delenv("KNOWLINK_ENABLE_VIVO_EMBEDDING", raising=False)
    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "fake-key")
    assert get_configured_embedding_client() is None

    monkeypatch.setenv("KNOWLINK_ENABLE_VIVO_EMBEDDING", "true")
    monkeypatch.delenv("KNOWLINK_VIVO_APP_KEY", raising=False)
    assert get_configured_embedding_client() is None

    monkeypatch.setenv("KNOWLINK_VIVO_APP_KEY", "fake-key")
    monkeypatch.setenv("KNOWLINK_VIVO_EMBEDDING_MODEL", "bge-test")
    assert isinstance(get_configured_embedding_client(), VivoEmbeddingClient)


def test_vivo_embedding_client_posts_batch_endpoint_headers_and_sentence_order(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps({"code": 0, "data": {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}}).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = VivoEmbeddingClient(
        app_key="fake-key",
        base_url="https://example.invalid/v1",
        model="m3e-base",
        timeout_sec=7,
    )

    vectors = client.embed_texts(["第一句", "第二句"])

    assert captured["url"].startswith("https://example.invalid/embedding-model-api/predict/batch?requestId=")
    assert captured["headers"]["Authorization"] == "Bearer fake-key"
    assert captured["headers"]["Content-type"] == "application/json; charset=utf-8"
    assert captured["body"]["model_name"] == "m3e-base"
    assert captured["body"]["sentences"] == ["第一句", "第二句"]
    assert captured["timeout"] == 7
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]


def test_embedding_empty_input_does_not_send_request(monkeypatch):
    def fail_urlopen(request, timeout):
        raise AssertionError("urlopen should not be called")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)
    client = VivoEmbeddingClient(app_key="fake-key", base_url="https://example.invalid", model="bge")

    assert client.embed_texts([]) == []


def test_embedding_blank_sentence_raises_without_sending_request(monkeypatch):
    def fail_urlopen(request, timeout):
        raise AssertionError("urlopen should not be called")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)
    client = VivoEmbeddingClient(app_key="fake-key", base_url="https://example.invalid", model="m3e-base")

    with pytest.raises(ValueError, match="sentence at index 0 is empty"):
        client.embed_texts(["", "有效文本"])


def test_embedding_count_mismatch_raises(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self):
            return json.dumps({"code": 0, "embeddings": [[0.1, 0.2]]}).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout: FakeResponse())
    client = VivoEmbeddingClient(app_key="fake-key", base_url="https://example.invalid", model="bge")

    with pytest.raises(RuntimeError, match="returned 1 vectors for 2 sentences"):
        client.embed_texts(["第一句", "第二句"])
