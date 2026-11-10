"""Offline tests for the guarded WordPress publisher. No network or secrets needed."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "wordpress_publisher.py"
SPEC = importlib.util.spec_from_file_location("wordpress_publisher", MODULE_PATH)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)

COMMIT = "a" * 40
BASELINE = "b" * 40
SOURCE_PATH = "articles/2026-01-21/example--wp-220.wp.html"
META = {
    "wordpress_site_id": 228574095,
    "wordpress_id": 220,
    "type": "post",
    "status": "publish",
    "slug": "example",
    "original_publication_date": "2026-01-21",
    "published_at_local": "2026-01-21T20:05:19",
    "wordpress_modified_at": "2026-01-23T00:02:35",
    "content_format": "wordpress-block-html",
    "featured_media_id": 0,
}


def remote(content="<p>Before</p>", modified=None):
    return {
        "id": 220,
        "type": "post",
        "status": "publish",
        "slug": "example",
        "date": "2026-01-21T20:05:19",
        "modified": modified or "2026-01-23T00:02:35",
        "featured_media": 0,
        "content": {"raw": content},
    }


class FakeClient:
    def __init__(self, current, *, normalize=False):
        self.current = current
        self.writes = []
        self.normalize = normalize

    def request(self, kind, post_id, *, content=None):
        if content is not None:
            self.writes.append((kind, post_id, content))
            self.current = remote(
                "<p>Normalized</p>" if self.normalize else content,
                modified="2026-11-10T12:00:00",
            )
        return self.current


class PublisherTests(unittest.TestCase):
    def test_allowed_and_disallowed_paths(self):
        self.assertEqual(
            str(publisher.validate_path(SOURCE_PATH)), SOURCE_PATH
        )
        for bad in (
            "articles/../secrets.wp.html",
            "/articles/2026-01-21/x.wp.html",
            "drafts/2026-01-21/x.wp.html",
            "articles/no-date/x.wp.html",
            "pages/2026-01-21/x.json",
            r"articles\2026-01-21\x.wp.html",
        ):
            with self.subTest(path=bad):
                with self.assertRaises(publisher.PublishError):
                    publisher.validate_path(bad)

    def test_plan_refuses_wordpress_side_edit(self):
        client = FakeClient(remote("<p>Edited in WordPress</p>"))
        with self.assertRaisesRegex(publisher.PublishError, "diverges"):
            publisher.plan_update(client, "<p>Before</p>", META, "<p>After</p>")
        self.assertEqual(client.writes, [])

    def test_plan_refuses_metadata_only_edit(self):
        client = FakeClient(remote(modified="2026-10-01T00:00:00"))
        with self.assertRaisesRegex(publisher.PublishError, "timestamp"):
            publisher.plan_update(client, "<p>Before</p>", META, "<p>After</p>")
        self.assertEqual(client.writes, [])

    def test_plan_refuses_image_or_status_change(self):
        for field, value in (("featured_media", 111), ("status", "draft")):
            obj = remote()
            obj[field] = value
            with self.subTest(field=field):
                with self.assertRaises(publisher.PublishError):
                    publisher.plan_update(FakeClient(obj), "<p>Before</p>", META, "<p>After</p>")

    def test_plan_accepts_matching_baseline(self):
        client = FakeClient(remote())
        before, after = publisher.plan_update(
            client, "<p>Before</p>", META, "<p>After</p>"
        )
        self.assertEqual(before, "<p>Before</p>")
        self.assertEqual(after, "<p>After</p>")
        self.assertEqual(client.writes, [])

    def test_apply_performs_readback(self):
        client = FakeClient(remote())
        saved = publisher.apply_update(client, META, "<p>After</p>")
        self.assertEqual(saved["content"]["raw"], "<p>After</p>")
        self.assertEqual(client.writes, [("post", 220, "<p>After</p>")])

    def test_apply_detects_wordpress_normalization(self):
        client = FakeClient(remote(), normalize=True)
        with self.assertRaisesRegex(publisher.PublishError, "readback differs"):
            publisher.apply_update(client, META, "<p>After</p>")

    def test_no_publish_without_apply_and_confirmed_id(self):
        def snapshots(root, commit, source):
            return ("<p>Before</p>" if commit == BASELINE else "<p>After</p>", dict(META))

        with (
            patch.object(publisher, "load_snapshot", side_effect=snapshots),
            patch.object(publisher, "WordPressClient", return_value=FakeClient(remote())) as factory,
            patch.dict(os.environ, {"WORDPRESS_ACCESS_TOKEN": "fake-token"}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = publisher.main([
                "--path", SOURCE_PATH, "--commit", COMMIT,
                "--baseline-commit", BASELINE,
            ])
        self.assertEqual(result, 0)
        self.assertEqual(factory.return_value.writes, [])
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(publisher.main([
                "--path", SOURCE_PATH, "--commit", COMMIT,
                "--baseline-commit", BASELINE, "--apply",
            ]), 1)

    def test_apply_checks_current_main_and_matching_id(self):
        def snapshots(root, commit, source):
            return ("<p>Before</p>" if commit == BASELINE else "<p>After</p>", dict(META))

        client = FakeClient(remote())
        with (
            patch.object(publisher, "load_snapshot", side_effect=snapshots),
            patch.object(publisher, "current_main_commit", return_value=COMMIT),
            patch.object(publisher, "WordPressClient", return_value=client),
            patch.dict(os.environ, {"WORDPRESS_ACCESS_TOKEN": "fake-token"}),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            result = publisher.main([
                "--path", SOURCE_PATH, "--commit", COMMIT,
                "--baseline-commit", BASELINE,
                "--apply", "--confirm-id", "220",
            ])
        self.assertEqual(result, 0)
        self.assertEqual(len(client.writes), 1)

    def test_readback_without_raw_content_is_rejected(self):
        with self.assertRaisesRegex(publisher.PublishError, "content.raw"):
            publisher.raw_content({"content": {"rendered": "<p>HTML</p>"}})

    def test_unauthorized_redirect_is_refused(self):
        handler = publisher.SameOriginRedirects()
        class Dummy:
            pass
        with self.assertRaisesRegex(publisher.PublishError, "outside"):
            handler.redirect_request(
                Dummy(), None, 302, "Found", {}, "https://example.org/collect"
            )


if __name__ == "__main__":
    unittest.main()
