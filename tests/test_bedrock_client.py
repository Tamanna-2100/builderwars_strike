import json
from unittest.mock import Mock

import pytest

import bedrock_client


def response(text):
    return {"output": {"message": {"content": [{"text": text}]}}}


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SCANNER_MODEL_ID", "test-model")
    monkeypatch.delenv("USE_CACHE_ONLY", raising=False)
    client = Mock()
    factory = Mock(return_value=client)
    monkeypatch.setattr(bedrock_client.boto3, "client", factory)
    return client, factory


def test_converse_and_cache(client, monkeypatch):
    runtime, factory = client
    runtime.converse.return_value = response('```json\n{"ok": true}\n```')
    assert bedrock_client.ask("scanner", "system", "user") == {"ok": True}
    factory.assert_called_once_with("bedrock-runtime", region_name=bedrock_client.os.getenv("AWS_REGION"))
    runtime.converse.assert_called_once_with(
        modelId="test-model",
        system=[{"text": "system"}],
        messages=[{"role": "user", "content": [{"text": "user"}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 4096},
    )
    monkeypatch.setenv("USE_CACHE_ONLY", "true")
    assert bedrock_client.ask("scanner", "system", "user") == {"ok": True}
    factory.assert_called_once()


def test_invalid_json_retries_once(client):
    runtime, _ = client
    runtime.converse.side_effect = [response("invalid"), response('```\n[1, 2]\n```')]
    assert bedrock_client.ask("scanner", "system", "user") == [1, 2]
    assert runtime.converse.call_count == 2


def test_invalid_json_fails_without_caching(client, tmp_path):
    runtime, _ = client
    runtime.converse.return_value = response("invalid")
    with pytest.raises(json.JSONDecodeError):
        bedrock_client.ask("scanner", "system", "user")
    assert runtime.converse.call_count == 2
    assert not (tmp_path / ".cache").exists()


def test_cache_only_miss_never_creates_client(client, monkeypatch):
    _, factory = client
    monkeypatch.setenv("USE_CACHE_ONLY", "1")
    with pytest.raises(FileNotFoundError):
        bedrock_client.ask("scanner", "system", "user")
    factory.assert_not_called()


def test_cache_key_distinguishes_inputs(client, monkeypatch):
    runtime, _ = client
    runtime.converse.return_value = response("null")
    for system, user in [("ab", "c"), ("a", "bc"), ("other", "c")]:
        assert bedrock_client.ask("scanner", system, user) is None
    monkeypatch.setenv("SCANNER_MODEL_ID", "other-model")
    assert bedrock_client.ask("scanner", "ab", "c") is None
    assert runtime.converse.call_count == 4


def test_uses_configured_aws_region(client, monkeypatch):
    runtime, factory = client
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    runtime.converse.return_value = response("null")
    assert bedrock_client.ask("scanner", "system", "user") is None
    factory.assert_called_once_with("bedrock-runtime", region_name="us-east-2")