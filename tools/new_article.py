#!/usr/bin/env python3
"""Create the Markdown and JSON source files for a new editorial post."""
import argparse
import json
from pathlib import Path
import sys

from editorial_publisher import PublishError, validate_path


def create_article(root, *, day, slug, title):
    path = validate_path(f"articles/{day}/{slug}.md")
    if not title.strip():
        raise PublishError("Article title cannot be empty")
    body_path = root / str(path)
    meta_path = body_path.with_suffix(".json")
    if body_path.exists() or meta_path.exists():
        raise PublishError("Article already exists; no files overwritten")
    body_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"type": "post", "content_format": "markdown", "title": title,
                "slug": slug, "date": day, "status": "draft"}
    created_body = False
    created_meta = False
    try:
        with body_path.open("x", encoding="utf-8") as body:
            created_body = True
            body.write("")
        with meta_path.open("x", encoding="utf-8") as sidecar:
            created_meta = True
            sidecar.write(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        if created_meta:
            meta_path.unlink(missing_ok=True)
        if created_body:
            body_path.unlink(missing_ok=True)
        raise
    return body_path, meta_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Site-local YYYY-MM-DD")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--title", required=True)
    args = parser.parse_args(argv)
    try:
        paths = create_article(Path(__file__).resolve().parents[1], day=args.date,
                               slug=args.slug, title=args.title)
        print("Created:", *paths, sep="\n  ")
        print("Add Markdown to the empty body, review metadata, and commit before preview.")
        return 0
    except (OSError, PublishError) as exc:
        print(f"Cannot create article: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
