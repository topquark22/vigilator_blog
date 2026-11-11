#!/usr/bin/env python3
"""One-way Git-to-WordPress publisher for new Markdown-authored posts.

Preview is fully offline. Writes require an approved main commit, --apply, and
an exact slug confirmation. Publication receipts must be committed separately.
"""
import argparse
from datetime import date
import difflib
import hashlib
from html import escape
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request

from wordpress_publisher import (
    API_ORIGIN, MAX_RESPONSE_BYTES, SITE_ID, PublishError, WordPressClient,
    current_main_commit, git_text, raw_content, validate_commit,
)

SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
INLINE = re.compile(r"\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|`([^`\n]+)`|\[([^\]\n]+)\]\((https://[^\s)]+)\)")
IMAGE = re.compile(r"!\[([^\]\n]+)\]\(([^\s)]+)\)\Z")
HEADING = re.compile(r"(#{1,6}) (.+)\Z")
BULLET = re.compile(r"[-*] (.+)\Z")
NUMBER = re.compile(r"(\d+)\. (.+)\Z")
FENCE = re.compile(r"```([a-zA-Z0-9_+-]*)\Z")


def safe_url(value):
    parts = urlsplit(value)
    if (parts.scheme != "https" or not parts.netloc or parts.username or
            parts.password or any(ord(c) < 33 for c in value)):
        raise PublishError(f"Unsafe or unsupported HTTPS URL: {value!r}")
    return value


def inline_markup(text):
    result = []
    at = 0
    for match in INLINE.finditer(text):
        result.append(escape(text[at:match.start()]))
        strong, italic, code, label, href = match.groups()
        if strong is not None:
            result.append(f"<strong>{escape(strong)}</strong>")
        elif italic is not None:
            result.append(f"<em>{escape(italic)}</em>")
        elif code is not None:
            result.append(f"<code>{escape(code)}</code>")
        else:
            result.append(f'<a href="{escape(safe_url(href), quote=True)}">{escape(label)}</a>')
        at = match.end()
    result.append(escape(text[at:]))
    return "".join(result)


def validate_path(source_path):
    path = PurePosixPath(source_path)
    if (path.is_absolute() or len(path.parts) != 3 or path.parts[0] != "articles" or
            not DATE.fullmatch(path.parts[1]) or not SLUG.fullmatch(path.stem) or
            path.suffix != ".md" or "\\" in source_path):
        raise PublishError("Expected articles/YYYY-MM-DD/slug.md")
    try:
        date.fromisoformat(path.parts[1])
    except ValueError:
        raise PublishError("Invalid article directory date") from None
    return path


def validate_metadata(metadata, path):
    if not isinstance(metadata, dict):
        raise PublishError("Article metadata must be a JSON object")
    required = {"title", "slug", "date", "status", "type", "content_format"}
    optional = {"excerpt", "category_ids", "tag_ids", "featured_media_id", "images",
                "wordpress_id", "wordpress_content_sha256", "wordpress_modified_at", "wordpress_url"}
    if (set(metadata) - required - optional or not required.issubset(metadata) or
            metadata["type"] != "post" or metadata["content_format"] != "markdown" or
            metadata["status"] not in ("draft", "publish") or
            metadata["date"] != path.parts[1] or metadata["slug"] != path.stem or
            not isinstance(metadata["title"], str) or not metadata["title"].strip()):
        raise PublishError("Unsupported or inconsistent editorial metadata")
    for key in ("excerpt",):
        if key in metadata and not isinstance(metadata[key], str):
            raise PublishError(f"{key} must be a string")
    for key in ("category_ids", "tag_ids"):
        if key in metadata and (not isinstance(metadata[key], list) or
                any(type(x) is not int or x < 1 for x in metadata[key])):
            raise PublishError(f"{key} must contain WordPress numeric term IDs")
    if "featured_media_id" in metadata and (type(metadata["featured_media_id"]) is not int or
                                          metadata["featured_media_id"] < 1):
        raise PublishError("featured_media_id must be a positive WordPress media ID")
    images = metadata.get("images", {})
    if not isinstance(images, dict):
        raise PublishError("images must be an object")
    for name, item in images.items():
        path_name = PurePosixPath(name)
        if (not name.startswith("media/") or ".." in path_name.parts or
                path_name.is_absolute() or "\\" in name or not isinstance(item, dict) or
                set(item) != {"id", "url"} or type(item["id"]) is not int or item["id"] < 1 or
                not isinstance(item["url"], str)):
            raise PublishError("Invalid WordPress media mapping")
        safe_url(item["url"])
    if "wordpress_url" in metadata:
        if not isinstance(metadata["wordpress_url"], str):
            raise PublishError("wordpress_url must be a string")
        safe_url(metadata["wordpress_url"])
    wp_id = metadata.get("wordpress_id")
    if wp_id is None:
        if any(key in metadata for key in ("wordpress_content_sha256", "wordpress_modified_at", "wordpress_url")):
            raise PublishError("Publication receipt without wordpress_id")
    else:
        if (type(wp_id) is not int or wp_id < 1 or
                not isinstance(metadata.get("wordpress_content_sha256"), str) or
                not re.fullmatch(r"[0-9a-f]{64}", metadata["wordpress_content_sha256"]) or
                not isinstance(metadata.get("wordpress_modified_at"), str) or
                not metadata["wordpress_modified_at"]):
            raise PublishError("Updating requires complete verified publication receipt")
    return metadata


def image_block(line, images):
    match = IMAGE.fullmatch(line)
    if not match:
        raise PublishError("Image must occupy its own line and have nonempty alt text")
    alt, source = match.groups()
    if source.startswith("media/"):
        if source not in images:
            raise PublishError(f"No uploaded WordPress media mapping for {source}")
        record = images[source]
        url, media_id = record["url"], record["id"]
        attrs = json.dumps({"id": media_id, "sizeSlug": "full", "linkDestination": "none"}, separators=(",", ":"))
        klass = f' class="wp-image-{media_id}"'
    else:
        url, attrs, klass = safe_url(source), "", ""
    tag = f'<img src="{escape(url, quote=True)}" alt="{escape(alt, quote=True)}"{klass}/>'
    return f'<!-- wp:image{(" " + attrs) if attrs else ""} -->\n<figure class="wp-block-image size-full">{tag}</figure>\n<!-- /wp:image -->'


def markdown_to_blocks(markdown, images=None):
    """Convert a deliberately limited Markdown dialect; reject ambiguous constructs."""
    images = images or {}
    lines = markdown.splitlines()
    blocks = []
    at = 0
    while at < len(lines):
        line = lines[at]
        if not line.strip():
            at += 1
            continue
        if line.startswith("```"):
            match = FENCE.fullmatch(line)
            if match is None:
                raise PublishError("Unsupported code fence")
            at += 1
            code = []
            while at < len(lines) and lines[at] != "```":
                code.append(lines[at])
                at += 1
            if at == len(lines):
                raise PublishError("Unclosed code fence")
            text = escape("\n".join(code) + "\n")
            blocks.append(f'<!-- wp:code -->\n<pre class="wp-block-code"><code>{text}</code></pre>\n<!-- /wp:code -->')
            at += 1
            continue
        heading = HEADING.fullmatch(line)
        if heading:
            level = len(heading.group(1))
            if level == 1:
                raise PublishError("Use title metadata instead of Markdown H1")
            text = inline_markup(heading.group(2))
            blocks.append(f'<!-- wp:heading {{"level":{level}}} -->\n<h{level} class="wp-block-heading">{text}</h{level}>\n<!-- /wp:heading -->')
            at += 1
            continue
        if line in ("---", "***"):
            blocks.append('<!-- wp:separator -->\n<hr class="wp-block-separator has-alpha-channel-opacity"/>\n<!-- /wp:separator -->')
            at += 1
            continue
        if line.startswith("!["):
            blocks.append(image_block(line, images))
            at += 1
            continue
        bullet = BULLET.fullmatch(line)
        numbered = NUMBER.fullmatch(line)
        if bullet or numbered:
            ordered = numbered is not None
            items = []
            start = int(numbered.group(1)) if ordered else 1
            expected = start
            while at < len(lines):
                item = NUMBER.fullmatch(lines[at]) if ordered else BULLET.fullmatch(lines[at])
                if not item:
                    break
                if ordered and int(item.group(1)) != expected:
                    raise PublishError("Numbered list must be consecutive")
                expected += 1
                value = item.group(2) if ordered else item.group(1)
                items.append(f'<!-- wp:list-item -->\n<li>{inline_markup(value)}</li>\n<!-- /wp:list-item -->')
                at += 1
            tag = "ol" if ordered else "ul"
            attributes = {"ordered": True} if ordered else {}
            if ordered and start != 1:
                attributes["start"] = start
            attrs = " " + json.dumps(attributes, separators=(",", ":")) if attributes else ""
            start_attr = f' start="{start}"' if ordered and start != 1 else ""
            blocks.append(f'<!-- wp:list{attrs} -->\n<{tag} class="wp-block-list"{start_attr}>\n' +
                          "\n".join(items) + f'\n</{tag}>\n<!-- /wp:list -->')
            continue
        if line.startswith("> "):
            quote_lines = []
            while at < len(lines) and lines[at].startswith("> "):
                quote_lines.append(lines[at][2:])
                at += 1
            paragraph = inline_markup(" ".join(quote_lines))
            blocks.append('<!-- wp:quote -->\n<blockquote class="wp-block-quote"><!-- wp:paragraph -->\n' +
                          f'<p>{paragraph}</p>\n<!-- /wp:paragraph --></blockquote>\n<!-- /wp:quote -->')
            continue
        if (line.startswith(("#", "<", "|", "    ", "\t", ">", "- ", "* ")) or
                re.match(r"\d+\.\s", line)):
            raise PublishError(f"Unsupported Markdown construct at line {at + 1}")
        paragraph = []
        while at < len(lines) and lines[at].strip():
            candidate = lines[at]
            if (paragraph and (HEADING.fullmatch(candidate) or BULLET.fullmatch(candidate) or
                               NUMBER.fullmatch(candidate) or candidate.startswith(("> ", "![", "```")) or
                               candidate in ("---", "***"))):
                break
            if candidate.startswith(("<", "|", "    ", "\t")):
                raise PublishError(f"Unsupported Markdown construct at line {at + 1}")
            if "![" in candidate:
                raise PublishError("Images must be on standalone lines")
            paragraph.append(candidate)
            at += 1
        blocks.append('<!-- wp:paragraph -->\n<p>' + inline_markup(" ".join(paragraph)) + '</p>\n<!-- /wp:paragraph -->')
    if not blocks:
        raise PublishError("Article body is empty")
    return "\n\n".join(blocks) + "\n"


def load_article(root, commit, path_string):
    validate_commit(commit)
    path = validate_path(path_string)
    try:
        source = git_text(root, commit, str(path))
        metadata = json.loads(git_text(root, commit, str(path.with_suffix(".json"))))
    except (ValueError, UnicodeError) as exc:
        raise PublishError(f"Invalid committed article: {exc}") from None
    validate_metadata(metadata, path)
    return metadata, markdown_to_blocks(source, metadata.get("images", {}))


class EditorialClient(WordPressClient):
    def api(self, method, endpoint, payload=None):
        if method not in ("GET", "POST") or not endpoint.startswith("posts"):
            raise PublishError("Invalid WordPress API request")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        url = f"{API_ORIGIN}/wp/v2/sites/{SITE_ID}/{endpoint}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        try:
            with self.opener.open(Request(url, data=data, headers=headers, method=method), timeout=30) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise PublishError(f"WordPress API returned HTTP {exc.code}") from None
        except URLError as exc:
            raise PublishError(f"WordPress API connection failed: {exc.reason}") from None
        if len(body) > MAX_RESPONSE_BYTES:
            raise PublishError("Oversized WordPress API response")
        try:
            return json.loads(body)
        except (ValueError, UnicodeError):
            raise PublishError("Invalid WordPress API response") from None


def post_payload(meta, blocks):
    payload = {"title": meta["title"], "slug": meta["slug"], "status": meta["status"], "content": blocks}
    for source, target in (("excerpt", "excerpt"), ("category_ids", "categories"),
                           ("tag_ids", "tags"), ("featured_media_id", "featured_media")):
        if source in meta:
            payload[target] = meta[source]
    return payload


def verify_post(remote, metadata, content):
    if not isinstance(remote, dict) or type(remote.get("id")) is not int:
        raise PublishError("WordPress did not return a post ID")
    title = remote.get("title")
    excerpt = remote.get("excerpt")
    if (remote.get("type") != "post" or remote.get("slug") != metadata["slug"] or
            remote.get("status") != metadata["status"] or raw_content(remote) != content or
            not isinstance(title, dict) or title.get("raw") != metadata["title"] or
            ("excerpt" in metadata and (not isinstance(excerpt, dict) or
                                         excerpt.get("raw") != metadata["excerpt"])) or
            ("category_ids" in metadata and remote.get("categories") != metadata["category_ids"]) or
            ("tag_ids" in metadata and remote.get("tags") != metadata["tag_ids"]) or
            ("featured_media_id" in metadata and remote.get("featured_media") != metadata["featured_media_id"])):
        raise PublishError("WordPress readback does not match the approved post")
    return {"wordpress_id": remote["id"],
            "wordpress_content_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "wordpress_modified_at": remote.get("modified"),
            "wordpress_url": remote.get("link")}


def publish(client, metadata, blocks, *, allow_status_change=False):
    payload = post_payload(metadata, blocks)
    post_id = metadata.get("wordpress_id")
    if post_id is None:
        result = client.api("GET", f'posts?slug={quote(metadata["slug"])}&status=any&context=edit')
        if not isinstance(result, list):
            raise PublishError("WordPress slug lookup returned an unexpected response")
        if result:
            raise PublishError("A WordPress post with this slug already exists; reconcile before retrying")
        created = client.api("POST", "posts?context=edit", payload)
        if not isinstance(created, dict) or type(created.get("id")) is not int:
            raise PublishError("WordPress creation response has no ID; inspect site before retrying")
        post_id = created["id"]
    else:
        current = client.api("GET", f"posts/{post_id}?context=edit")
        if (not isinstance(current, dict) or current.get("id") != post_id or
                current.get("slug") != metadata["slug"] or current.get("type") != "post"):
            raise PublishError("Existing WordPress post identity changed")
        if hashlib.sha256(raw_content(current).encode("utf-8")).hexdigest() != metadata["wordpress_content_sha256"]:
            raise PublishError("WordPress content no longer matches the last confirmed publication")
        if current.get("modified") != metadata["wordpress_modified_at"]:
            raise PublishError("WordPress modification timestamp changed")
        if current.get("status") != metadata["status"] and not allow_status_change:
            raise PublishError("Status change requires --allow-status-change")
        client.api("POST", f"posts/{post_id}?context=edit", payload)
    saved = client.api("GET", f"posts/{post_id}?context=edit")
    receipt = verify_post(saved, metadata, blocks)
    if receipt["wordpress_id"] != post_id or not receipt["wordpress_modified_at"]:
        raise PublishError("WordPress readback is missing a verified ID or modification time")
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, help="articles/YYYY-MM-DD/slug.md")
    parser.add_argument("--commit", required=True, help="Full approved Git commit SHA")
    parser.add_argument("--apply", action="store_true", help="Perform an authenticated WordPress write")
    parser.add_argument("--confirm-slug", help="Required with --apply; exact approved slug")
    parser.add_argument("--allow-status-change", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        meta, blocks = load_article(root, args.commit, args.path)
        if args.apply:
            if current_main_commit(root) != args.commit:
                raise PublishError("Apply requires current local main HEAD")
            if args.confirm_slug != meta["slug"]:
                raise PublishError("Apply requires --confirm-slug matching committed metadata")
        print(f"Article: {meta['title']} ({meta['slug']})")
        print(f"Target WordPress status: {meta['status']}")
        print(f"Source commit: {args.commit}")
        print(f"Gutenberg SHA-256: {hashlib.sha256(blocks.encode('utf-8')).hexdigest()}")
        if not args.apply:
            print("\n" + blocks)
            print("DRY RUN ONLY: no credentials or WordPress changes required.")
            return 0
        client = EditorialClient(os.environ.get("WORDPRESS_ACCESS_TOKEN"))
        receipt = publish(client, meta, blocks, allow_status_change=args.allow_status_change)
        print("WORDPRESS WRITE VERIFIED. Commit receipt fields to the article JSON sidecar:")
        print(json.dumps(receipt, indent=2))
        return 0
    except PublishError as exc:
        print(f"Publication blocked: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
