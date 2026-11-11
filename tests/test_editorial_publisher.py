"""Offline tests for one-way Markdown editorial publishing."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import editorial_publisher as editorial
import new_article

COMMIT = "a" * 40
PATH = "articles/2026-11-11/new-essay.md"
TEXT = "## A heading\n\nA **bold** and [linked](https://example.com) paragraph.\n"
META = {"type": "post", "content_format": "markdown", "title": "New essay",
        "slug": "new-essay", "date": "2026-11-11", "status": "publish"}
BLOCKS = editorial.markdown_to_blocks(TEXT)


def remote(post_id=42, content=BLOCKS, status="publish", modified="2026-11-11T12:00:00"):
    return {"id": post_id, "type": "post", "slug": "new-essay", "status": status,
            "modified": modified, "link": "https://vigilator.blog/new-essay/",
            "content": {"raw": content}, "title": {"raw": "New essay"}, "excerpt": {"raw": ""}}


class Client:
    def __init__(self, *, initial=None, existing=None, modified_content=None):
        self.record = initial
        self.existing = [] if existing is None else existing
        self.modified_content = modified_content
        self.calls = []

    def api(self, method, endpoint, payload=None):
        self.calls.append((method, endpoint, payload))
        if method == "GET" and endpoint.startswith("posts?slug="):
            return self.existing
        if method == "GET":
            return self.record
        if method == "POST":
            self.record = remote(content=self.modified_content if self.modified_content is not None
                                 else payload["content"], status=payload["status"])
            return self.record
        raise AssertionError("Unexpected API request")


class EditorialTests(unittest.TestCase):
    def test_scaffold_creates_empty_draft_and_refuses_overwrite(self):
        with TemporaryDirectory() as workdir:
            root = Path(workdir)
            body, meta = new_article.create_article(root, day="2026-11-11",
                slug="new-essay", title="New essay")
            self.assertEqual(body.read_text(), "")
            self.assertEqual(json.loads(meta.read_text()), {**META, "status": "draft"})
            with self.assertRaises(editorial.PublishError):
                new_article.create_article(root, day="2026-11-11", slug="new-essay",
                                           title="Overwrite")
            self.assertEqual(body.read_text(), "")

    def test_paths(self):
        self.assertEqual(str(editorial.validate_path(PATH)), PATH)
        for path in ("pages/2026-11-11/new-essay.md", "articles/2026-13-90/new.md",
                     "articles/2026-11-11/UPPER.md", "articles/2026-11-11/x.wp.html",
                     "articles/../secret.md", "articles/2026-11-11/../secret.md",
                     r"articles\2026-11-11\x.md", "/articles/2026-11-11/x.md"):
            with self.subTest(path=path), self.assertRaises(editorial.PublishError):
                editorial.validate_path(path)

    def test_metadata_requires_matching_path_and_receipt(self):
        path = editorial.validate_path(PATH)
        self.assertEqual(editorial.validate_metadata(dict(META), path), META)
        for changes in ({"slug": "other"}, {"status": "future"}, {"category_ids": ["1"]},
                        {"images": {"../secret": {"id": 9, "url": "https://example.com"}}},
                        {"wordpress_id": 10}, {"wordpress_content_sha256": "a" * 64},
                        {"title": ""}, {"content_format": "html"}):
            with self.subTest(changes=changes), self.assertRaises(editorial.PublishError):
                editorial.validate_metadata({**META, **changes}, path)

    def test_markdown_blocks(self):
        self.assertIn('<h2 class="wp-block-heading">A heading</h2>', BLOCKS)
        self.assertIn('<strong>bold</strong>', BLOCKS)
        self.assertIn('<a href="https://example.com">linked</a>', BLOCKS)
        text = "- one\n- two\n\n1. first\n2. second\n\n> quote\n\n```py\nx < y\n```\n\n---\n"
        result = editorial.markdown_to_blocks(text)
        self.assertIn("<!-- wp:list -->", result)
        self.assertIn('<!-- wp:list {"ordered":true} -->', result)
        self.assertIn("<!-- wp:quote -->", result)
        self.assertIn("x &lt; y", result)
        self.assertIn("<!-- wp:separator -->", result)

    def test_images_escape_and_mapping(self):
        mapped = editorial.markdown_to_blocks('![A "quote"](media/essays/pic.png)',
            {"media/essays/pic.png": {"id": 19, "url": "https://vigilator.blog/pic.png"}})
        self.assertIn('wp-image-19', mapped)
        self.assertIn('alt="A &quot;quote&quot;"', mapped)
        self.assertIn('<!-- wp:image {"id":19,', mapped)
        direct = editorial.markdown_to_blocks("![Landscape](https://example.com/pic.jpg)")
        self.assertIn('src="https://example.com/pic.jpg"', direct)
        for bad in ("![No alt]()", "![Bad](http://example.com/x.png)",
                    "![Local](media/missing.png)"):
            with self.subTest(image=bad), self.assertRaises(editorial.PublishError):
                editorial.markdown_to_blocks(bad)

    def test_unsupported_markdown_fails(self):
        for bad in ("# H1", "| table |", "<script>alert(1)</script>",
                    "```python\nunclosed", "1. item\n3. missing",
                    "", "    indented code"):
            with self.subTest(markdown=bad), self.assertRaises(editorial.PublishError):
                editorial.markdown_to_blocks(bad)

    def test_git_snapshot(self):
        def file_text(root, sha, path):
            return TEXT if path.endswith(".md") else json.dumps(META)
        with patch.object(editorial, "git_text", side_effect=file_text) as reader:
            meta, blocks = editorial.load_article(Path("."), COMMIT, PATH)
        self.assertEqual(meta, META)
        self.assertEqual(blocks, BLOCKS)
        self.assertEqual(reader.call_count, 2)

    def test_create_post_checks_duplicate_slug(self):
        client = Client(existing=[{"id": 9}])
        with self.assertRaisesRegex(editorial.PublishError, "already exists"):
            editorial.publish(client, META, BLOCKS)
        self.assertEqual([c for c in client.calls if c[0] == "POST"], [])

    def test_create_post_readback_and_receipt(self):
        client = Client()
        receipt = editorial.publish(client, META, BLOCKS)
        self.assertEqual(receipt["wordpress_id"], 42)
        self.assertEqual(receipt["wordpress_content_sha256"], hashlib.sha256(BLOCKS.encode()).hexdigest())
        self.assertEqual(client.calls[1][2]["status"], "publish")
        self.assertEqual([x[0] for x in client.calls], ["GET", "POST", "GET"])

    def test_create_rejects_normalization(self):
        client = Client(modified_content="<p>Changed</p>")
        with self.assertRaisesRegex(editorial.PublishError, "readback"):
            editorial.publish(client, META, BLOCKS)

    def test_update_guards_remote_and_transition(self):
        previous = editorial.markdown_to_blocks("Original version.")
        updated = {**META, "wordpress_id": 42,
                   "wordpress_content_sha256": hashlib.sha256(previous.encode()).hexdigest(),
                   "wordpress_modified_at": "2026-11-11T12:00:00"}
        client = Client(initial=remote(content=previous))
        receipt = editorial.publish(client, updated, BLOCKS)
        self.assertEqual(receipt["wordpress_id"], 42)
        self.assertEqual([x[0] for x in client.calls], ["GET", "POST", "GET"])
        for old in (remote(content="changed"), remote(content=previous, modified="later")):
            client = Client(initial=old)
            with self.assertRaises(editorial.PublishError):
                editorial.publish(client, updated, BLOCKS)
            self.assertEqual([x[0] for x in client.calls], ["GET"])
        client = Client(initial=remote(content=previous, status="draft"))
        with self.assertRaisesRegex(editorial.PublishError, "Status change"):
            editorial.publish(client, updated, BLOCKS)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(editorial.publish(Client(initial=remote(content=previous, status="draft")),
                                           updated, BLOCKS, allow_status_change=True)["wordpress_id"], 42)

    def test_dry_run_is_offline(self):
        with (patch.object(editorial, "load_article", return_value=(dict(META), BLOCKS)),
              patch.object(editorial, "EditorialClient") as client,
              patch.object(editorial, "current_main_commit") as main,
              contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(editorial.main(["--path", PATH, "--commit", COMMIT]), 0)
        client.assert_not_called()
        main.assert_not_called()

    def test_apply_requires_exact_main_and_slug(self):
        with (patch.object(editorial, "load_article", return_value=(dict(META), BLOCKS)),
              patch.object(editorial, "current_main_commit", return_value=COMMIT),
              patch.object(editorial, "EditorialClient", return_value=Client()) as factory,
              patch.dict(os.environ, {"WORDPRESS_ACCESS_TOKEN": "test-token"}),
              contextlib.redirect_stdout(io.StringIO()),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(editorial.main(["--path", PATH, "--commit", COMMIT, "--apply"]), 1)
            self.assertEqual(editorial.main(["--path", PATH, "--commit", COMMIT, "--apply",
                                            "--confirm-slug", "wrong"]), 1)
            factory.assert_not_called()
            self.assertEqual(editorial.main(["--path", PATH, "--commit", COMMIT, "--apply",
                                            "--confirm-slug", "new-essay"]), 0)
        with (patch.object(editorial, "load_article", return_value=(dict(META), BLOCKS)),
              patch.object(editorial, "current_main_commit", return_value="b" * 40),
              contextlib.redirect_stderr(io.StringIO())):
            self.assertEqual(editorial.main(["--path", PATH, "--commit", COMMIT, "--apply",
                                            "--confirm-slug", "new-essay"]), 1)


if __name__ == "__main__":
    unittest.main()
