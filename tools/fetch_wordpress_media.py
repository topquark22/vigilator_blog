#!/usr/bin/env python3
"""Download original WordPress media listed in a reviewed manifest.

Requires network access, writes no files outside the requested checkout, and
does not publish anything to WordPress. Uses ordinary Git blobs, not Git LFS.
"""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ALLOWED_HOSTS = {
    "topquark22.wordpress.com",
    "topquark22.files.wordpress.com",
    "vigilator.blog",
}
MAX_BYTES = 50 * 1024 * 1024


def download_asset(asset, checkout):
    media_id = asset["wordpress_media_id"]
    if not isinstance(media_id, int) or media_id <= 0:
        raise ValueError("Invalid WordPress media ID")
    filename = asset["original_filename"]
    if Path(filename).name != filename or filename in ("", ".", ".."):
        raise ValueError("Unsafe filename")
    url = asset["source_url"]
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS:
        raise ValueError("Unapproved media URL")
    expected_size = asset["expected_size_bytes"]
    if not isinstance(expected_size, int) or not (0 < expected_size <= MAX_BYTES):
        raise ValueError("Invalid expected size")

    dest = checkout / "media" / ("wp-" + str(media_id)) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        data = dest.read_bytes()
    else:
        request = Request(url, headers={"User-Agent": "vigilator-blog-media-import/1.0", "Accept": asset["mime_type"]})
        with urlopen(request, timeout=60) as response:
            if urlsplit(response.geturl()).hostname not in ALLOWED_HOSTS:
                raise ValueError("Unexpected redirect host")
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Asset exceeds maximum size")
    if len(data) != expected_size:
        raise ValueError(f"Size mismatch for WordPress media {media_id}: got {len(data)}, expected {expected_size}")
    mime = asset["mime_type"]
    if mime == "image/png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("File is not a PNG")
    if mime == "image/webp" and not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        raise ValueError("File is not a WebP image")
    if not dest.exists():
        dest.write_bytes(data)

    sha256 = hashlib.sha256(data).hexdigest()
    record = dict(asset)
    record.pop("expected_size_bytes", None)
    record["file_size_bytes"] = len(data)
    record["sha256"] = sha256
    (dest.parent / "metadata.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"wp-{media_id}/{filename}: {len(data)} bytes, SHA-256 {sha256}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, default=Path("."))
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    for asset in manifest["assets"]:
        download_asset(asset, checkout)


if __name__ == "__main__":
    main()
