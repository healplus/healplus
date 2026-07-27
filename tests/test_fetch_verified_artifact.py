from __future__ import annotations

import hashlib
from io import BytesIO

import pytest

import scripts.fetch_verified_artifact as artifact_fetcher
from scripts.fetch_verified_artifact import ArtifactVerificationError, fetch_verified_artifact


def test_fetch_verified_artifact_promotes_synthetic_file_after_checksum(tmp_path):
    source = tmp_path / "synthetic-model.bin"
    source.write_bytes(b"synthetic artifact only\n")
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    destination = tmp_path / "cache" / "model.bin"

    result = fetch_verified_artifact(source.as_uri(), destination, expected, max_bytes=1024)

    assert result == destination.resolve()
    assert destination.read_bytes() == source.read_bytes()
    assert not list(destination.parent.glob("*.part"))


def test_fetch_verified_artifact_rejects_checksum_and_does_not_replace_target(tmp_path):
    source = tmp_path / "synthetic-model.bin"
    source.write_bytes(b"new synthetic artifact\n")
    destination = tmp_path / "cache" / "model.bin"
    destination.parent.mkdir()
    destination.write_bytes(b"known good artifact\n")

    with pytest.raises(ArtifactVerificationError, match="does not match"):
        fetch_verified_artifact(source.as_uri(), destination, "0" * 64)

    assert destination.read_bytes() == b"known good artifact\n"
    assert not list(destination.parent.glob("*.part"))


def test_fetch_verified_artifact_rejects_unsafe_uri_and_size(tmp_path):
    with pytest.raises(ArtifactVerificationError, match="https"):
        fetch_verified_artifact("http://example.org/model.bin", tmp_path / "model.bin", "0" * 64)

    source = tmp_path / "large.bin"
    source.write_bytes(b"12345")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ArtifactVerificationError, match="size limit"):
        fetch_verified_artifact(source.as_uri(), tmp_path / "model.bin", digest, max_bytes=4)


@pytest.mark.parametrize(
    "uri",
    [
        "https://user:secret@example.org/model.bin",
        "https://example.org/model.bin?token=secret",
        "https://example.org/model.bin#fragment",
    ],
)
def test_fetch_verified_artifact_rejects_credentials_query_and_fragment(tmp_path, uri):
    with pytest.raises(ArtifactVerificationError):
        fetch_verified_artifact(uri, tmp_path / "model.bin", "0" * 64)


def test_fetch_verified_artifact_rejects_redirect_to_unsafe_uri(tmp_path, monkeypatch):
    class RedirectedResponse(BytesIO):
        def geturl(self):
            return "http://example.org/model.bin"

    monkeypatch.setattr(artifact_fetcher, "urlopen", lambda *_args, **_kwargs: RedirectedResponse(b"artifact"))

    with pytest.raises(ArtifactVerificationError, match="https"):
        fetch_verified_artifact("https://example.org/model.bin", tmp_path / "model.bin", "0" * 64)
