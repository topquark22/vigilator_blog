# One-way editorial publishing (Git → WordPress)

Git is authoritative. Do not edit content manually in the WordPress dashboard: this pipeline **does not import WordPress-side edits**. A remote change is treated as drift and blocks an update instead of overwriting it. The existing imported Gutenberg articles and the guarded legacy publisher remain supported separately; new articles use Markdown.

No merge, push, pull request, or CI job publishes an article. Publication must be explicitly invoked with credentials, a reviewed `main` commit, and confirmation.

## Start a new article

```bash
python tools/new_article.py --date 2026-11-11 --slug example-essay --title "Example essay"
```

This creates **empty** `articles/2026-11-11/example-essay.md` and `articles/2026-11-11/example-essay.json`, initially a draft. Fill in the Markdown and review the sidecar. The path date is the *site-local authoring date* and is stable; WordPress sets the actual initial publication time when a post is published. The `.json` sidecar contains:

```json
{
  "type": "post",
  "content_format": "markdown",
  "title": "Example essay",
  "slug": "example-essay",
  "date": "2026-11-11",
  "status": "draft"
}
```

The `status` is either `draft` or `publish`. Change it to `publish` only when approved. Optional fields are `excerpt` (string), `category_ids` and `tag_ids` (arrays of **existing WordPress term IDs**), `featured_media_id` (existing WordPress media ID), and `images` (see below). All fields are explicitly validated; unsupported keys fail rather than being silently discarded. Categories and tags are not created by the publisher.

Supported Markdown: paragraphs, H2–H6 headings, inline emphasis/bold/code, HTTPS links, simple consecutive ordered or unordered lists, single-level quotes, fenced code, separators, and standalone images. The converter deliberately rejects H1 (use the post title), tables, nested lists, raw block HTML, and unclosed code fences. Inspect the generated Gutenberg block markup before publishing; it is **not** a theme-accurate browser preview. This limited dialect avoids silently corrupting complex Gutenberg content.

Images may use public HTTPS URLs. To use a Git-managed file, upload it to the WordPress media library by a separately approved process and specify its existing media ID and HTTPS URL in the sidecar, for example:

```json
"images": {
  "media/my-essay/diagram.png": {
    "id": 321,
    "url": "https://vigilator.blog/wp-content/uploads/2026/11/diagram.png"
  }
}
```

Then reference it in the Markdown with `![Diagram](media/my-essay/diagram.png)`. The publisher will refuse a local image with no mapping. **Automated media uploads are not implemented in this version.** Do not invent media IDs or URLs.

## Review and dry run (no token required)

Commit the body and sidecar, review the diff, and merge to `main`. With a complete approved commit SHA:

```bash
python tools/editorial_publisher.py \
  --path articles/2026-11-11/example-essay.md \
  --commit FULL_APPROVED_SHA
```

The dry run reads **only committed Git objects**, validates metadata, converts the Markdown to Gutenberg blocks, and prints the proposed markup and SHA-256. It needs no WordPress access.

## Explicit create or update

After reviewing the dry run, and **only once** separately configured OAuth credentials are available:

```bash
python tools/editorial_publisher.py \
  --path articles/2026-11-11/example-essay.md \
  --commit FULL_APPROVED_MAIN_SHA \
  --apply --confirm-slug example-essay
```

The command requires the given commit to match the current local `main` HEAD. It uses `WORDPRESS_ACCESS_TOKEN` from the environment (never pass the token as a CLI argument, print it, or commit it). Use a protected GitHub environment if later wrapping the command in Actions; do not configure automatic publishing on pushes. The writer uses the existing WordPress.com API proxy for site ID `228574095`.

For a new article, it searches WordPress for any existing post with the same slug, aborting on a match. Otherwise, it creates the post in the approved status, fetches it again with edit context, and verifies its ID, slug, status, title, and exact Gutenberg content. On success it prints a receipt resembling:

```json
{
  "wordpress_id": 987,
  "wordpress_content_sha256": "64-lowercase-hex-digits-from-the-actual-run",
  "wordpress_modified_at": "2026-11-11T11:00:00",
  "wordpress_url": "https://vigilator.blog/example-essay/"
}
```

These values above are **illustrative**, not an actual publication. Add the **real** receipt fields to the article's JSON sidecar in a separate reviewed Git commit before any further update. Without a receipt, the next run will treat the article as new, detect the existing slug, and refuse to create a duplicate. A failed write or failed readback must be inspected manually before retrying.

For updates, the receipt identifies the existing WordPress post. The publisher checks its existing content hash and last-modified time before overwriting it, then sends the proposed title/body/metadata and reads back for verification. A draft→public or public→draft status transition additionally requires `--allow-status-change`. This is **one-way drift detection**, not bidirectional synchronization.

WordPress saves are not atomic compare-and-swap operations; concurrent dashboard edits remain a race. The design assumes that the site owner honors the no-manual-edits convention. Server-side normalization of Gutenberg block markup may cause exact-readback failure and must be investigated before any retry.

## Tests

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

The tests do not use a WordPress token, access the network, or publish anything. No live end-to-end test of this new publisher has yet been performed.
