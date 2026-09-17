"""Fetch a non-clinical artifact and promote it only after SHA-256 verification."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import os
import tempfile
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlparse
from urllib.request import urlopen


class ArtifactVerificationError(RuntimeError):
    """Raised when an artifact cannot be fetched or verified safely."""


def _validate_source_uri(uri: str, *, allow_file: bool) -> None:
    parsed = urlparse(uri)
    if parsed.username or parsed.password:
        raise ArtifactVerificationError("credentials are not allowed in artifact URIs")
    if parsed.query or parsed.fragment:
        raise ArtifactVerificationError("query strings and fragments are not allowed in artifact URIs")
    allowed_schemes = {"https", "file"} if allow_file else {"https"}
    if parsed.scheme not in allowed_schemes:
        raise ArtifactVerificationError("artifact URI must use https:// or file://")


def _open_source(uri: str) -> BinaryIO:
    parsed = urlparse(uri)
    _validate_source_uri(uri, allow_file=True)
    if parsed.scheme == "https":
        response = urlopen(uri, timeout=30)  # noqa: S310 - HTTPS is enforced above.
        final_uri = response.geturl()
        try:
            _validate_source_uri(final_uri, allow_file=False)
        except ArtifactVerificationError:
            response.close()
            raise
        return response
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path.lstrip("/"))) if os.name == "nt" else Path(unquote(parsed.path))
        return path.open("rb")
    raise AssertionError("source URI scheme was validated but not handled")


def fetch_verified_artifact(
    uri: str,
    destination: str | Path,
    expected_sha256: str,
    *,
    max_bytes: int = 2 * 1024 * 1024 * 1024,
) -> Path:
    expected = expected_sha256.strip().lower()
    if len(expected) != 64 or any(character not in "0123456789abcdef" for character in expected):
        raise ArtifactVerificationError("expected SHA-256 must contain 64 hexadecimal characters")
    if max_bytes <= 0:
        raise ArtifactVerificationError("max_bytes must be positive")

    target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    total = 0
    temporary_path: Path | None = None

    try:
        with _open_source(uri) as source, tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".part",
            dir=target.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise ArtifactVerificationError("artifact exceeds the configured size limit")
                digest.update(chunk)
                temporary.write(chunk)

        actual = digest.hexdigest()
        if not hmac.compare_digest(actual, expected):
            raise ArtifactVerificationError("artifact SHA-256 does not match the manifest")
        os.replace(temporary_path, target)
        temporary_path = None
        return target
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri", required=True, help="HTTPS or file URI without embedded credentials")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024 * 1024)
    args = parser.parse_args()

    fetch_verified_artifact(args.uri, args.output, args.sha256, max_bytes=args.max_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
