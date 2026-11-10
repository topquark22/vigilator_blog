#!/usr/bin/env python3
"""Guarded content-only publisher for the vigilator.blog WordPress site.

No WordPress write occurs unless --apply and --confirm-id are both supplied.
Both source and baseline are read from immutable Git commits, never from
uncommitted working-tree files. Requires WORDPRESS_ACCESS_TOKEN in the
environment (WordPress.com OAuth2 bearer token).
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

SITE_ID = 228574095
API_ORIGIN = "https://public-api.wordpress.com"
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
DATE_DIR_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class PublishError(Exception):
    """Expected failure that must prevent publication."""


class SameOriginRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        parts = urlsplit(newurl)
        if parts.scheme != "https" or parts.hostname != "public-api.wordpress.com":
            raise PublishError("WordPress API redirected outside its trusted origin")
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class WordPressClient:
    def __init__(self, token):
        if not token or not token.strip():
            raise PublishError("WORDPRESS_ACCESS_TOKEN is required")
        self.token = token.strip()
        self.opener = build_opener(SameOriginRedirects())

    def request(self, kind, post_id, *, content=None):
        if kind not in ("post", "page") or not isinstance(post_id, int) or post_id < 1:
            raise PublishError("Invalid WordPress resource")
        collection = "posts" if kind == "post" else "pages"
        url = f"{API_ORIGIN}/wp/v2/sites/{SITE_ID}/{collection}/{post_id}?context=edit"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        data = None
        method = "GET"
        if content is not None:
            method = "POST"
            headers["Content-Type"] = "application/json; charset=utf-8"
            data = json.dumps({"content": content}, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=30) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise PublishError(f"WordPress API returned HTTP {exc.code}") from None
        except URLError as exc:
            raise PublishError(f"Cannot reach WordPress API: {exc.reason}") from None
        if len(payload) > MAX_RESPONSE_BYTES:
            raise PublishError("WordPress API response exceeded the maximum size")
        try:
            result = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            raise PublishError("WordPress API returned invalid JSON") from None
        if not isinstance(result, dict):
            raise PublishError("Unexpected WordPress API response")
        return result


def run_git(root, *arguments):
    result = subprocess.run(
        ["git", *arguments], cwd=root, capture_output=True, check=False
    )
    if result.returncode:
        raise PublishError(f"Git command failed: {arguments[0]}")
    return result.stdout


def validate_path(source_path):
    path = PurePosixPath(source_path)
    parts = path.parts
    if (
        path.is_absolute()
        or len(parts) != 3
        or parts[0] not in ("articles", "pages")
        or not DATE_DIR_PATTERN.fullmatch(parts[1])
        or not parts[2].endswith(".wp.html")
        or any(part in (".", "..") for part in parts)
        or "\\" in source_path
    ):
        raise PublishError("Expected articles/YYYY-MM-DD/name.wp.html or pages/YYYY-MM-DD/name.wp.html")
    return path


def validate_commit(commit):
    if not COMMIT_PATTERN.fullmatch(commit):
        raise PublishError("Use a full 40-character lowercase Git commit SHA")


def git_text(root, commit, path):
    return run_git(root, "show", f"{commit}:{path}").decode("utf-8")


def load_snapshot(root, commit, source_path):
    validate_commit(commit)
    path = validate_path(source_path)
    meta_path = str(path)[:-len(".wp.html")] + ".json"
    try:
        content = git_text(root, commit, source_path)
        metadata = json.loads(git_text(root, commit, meta_path))
    except (UnicodeError, ValueError) as exc:
        raise PublishError(f"Invalid committed article source or metadata: {exc}") from None
    if not isinstance(metadata, dict):
        raise PublishError("Metadata sidecar must be a JSON object")
    kind = "post" if path.parts[0] == "articles" else "page"
    if (
        metadata.get("wordpress_site_id") != SITE_ID
        or metadata.get("type") != kind
        or metadata.get("status") != "publish"
        or metadata.get("content_format") != "wordpress-block-html"
        or metadata.get("original_publication_date") != path.parts[1]
        or not isinstance(metadata.get("wordpress_id"), int)
        or metadata["wordpress_id"] < 1
        or not isinstance(metadata.get("wordpress_modified_at"), str)
    ):
        raise PublishError("Metadata does not match the expected published WordPress source")
    return content, metadata


def raw_content(remote):
    content = remote.get("content")
    if not isinstance(content, dict) or not isinstance(content.get("raw"), str):
        raise PublishError("WordPress did not return content.raw (check edit authorization)")
    return content["raw"]


def verify_remote_identity(remote, metadata):
    if remote.get("id") != metadata["wordpress_id"]:
        raise PublishError("WordPress post ID mismatch")
    if remote.get("type") != metadata["type"]:
        raise PublishError("WordPress post type mismatch")
    if remote.get("status") != metadata["status"]:
        raise PublishError("WordPress status changed since import")
    if remote.get("slug") != metadata.get("slug"):
        raise PublishError("WordPress slug changed since import")
    if remote.get("date") != metadata.get("published_at_local"):
        raise PublishError("WordPress original publication date changed since import")
    if remote.get("featured_media") != metadata.get("featured_media_id", 0):
        raise PublishError("WordPress featured image changed since import")


def plan_update(client, baseline_content, metadata, target_content):
    remote = client.request(metadata["type"], metadata["wordpress_id"])
    verify_remote_identity(remote, metadata)
    current = raw_content(remote)
    if current != baseline_content:
        raise PublishError(
            "WordPress content diverges from the baseline Git commit. Import and reconcile it first."
        )
    if remote.get("modified") != metadata["wordpress_modified_at"]:
        raise PublishError(
            "WordPress modification timestamp differs from the baseline. Inspect and reconcile first."
        )
    return current, target_content


def apply_update(client, metadata, target_content):
    kind, post_id = metadata["type"], metadata["wordpress_id"]
    client.request(kind, post_id, content=target_content)
    saved = client.request(kind, post_id)
    verify_remote_identity(saved, metadata)
    if raw_content(saved) != target_content:
        raise PublishError(
            "WordPress accepted the write but readback differs. Inspect the live article before retrying."
        )
    return saved


def current_main_commit(root):
    return run_git(root, "rev-parse", "refs/heads/main").decode("ascii").strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, help="Committed .wp.html article or page path")
    parser.add_argument("--commit", required=True, help="Full SHA of the approved Git commit")
    parser.add_argument("--baseline-commit", required=True, help="Full SHA last confirmed on WordPress")
    parser.add_argument("--apply", action="store_true", help="Write the approved content to WordPress")
    parser.add_argument("--confirm-id", type=int, help="Required on --apply; WordPress post/page ID")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        validate_commit(args.commit)
        validate_commit(args.baseline_commit)
        if args.apply:
            if args.confirm_id is None:
                raise PublishError("--apply requires --confirm-id")
            if current_main_commit(root) != args.commit:
                raise PublishError("Publication requires the current local main HEAD commit")
        baseline_content, baseline_meta = load_snapshot(
            root, args.baseline_commit, args.path
        )
        target_content, target_meta = load_snapshot(root, args.commit, args.path)
        if target_meta != baseline_meta:
            raise PublishError("Metadata changes are not supported by this content-only publisher")
        if args.apply and args.confirm_id != target_meta["wordpress_id"]:
            raise PublishError("Confirmed WordPress ID does not match the article metadata")
        client = WordPressClient(os.environ.get("WORDPRESS_ACCESS_TOKEN"))
        current, desired = plan_update(
            client, baseline_content, baseline_meta, target_content
        )
        print(f"WordPress {target_meta['type']} #{target_meta['wordpress_id']}")
        print(f"Approved Git commit: {args.commit}")
        print(f"Last-synchronized baseline: {args.baseline_commit}")
        print(f"Target content SHA-256: {hashlib.sha256(desired.encode('utf-8')).hexdigest()}")
        if current == desired:
            print("No content changes to publish.")
            return 0
        print("".join(difflib.unified_diff(
            current.splitlines(keepends=True),
            desired.splitlines(keepends=True),
            fromfile="wordpress/current",
            tofile=f"git/{args.commit}",
        )), end="")
        if not args.apply:
            print("\nDRY RUN ONLY. No WordPress changes made.")
            return 0
        saved = apply_update(client, baseline_meta, desired)
        print("\nPUBLISHED AND VERIFIED by authenticated WordPress readback.")
        print(f"WordPress modified timestamp: {saved.get('modified', 'unknown')}")
        print("Record this Git commit and WordPress modified timestamp as the new baseline.")
        return 0
    except PublishError as exc:
        print(f"Publication blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
