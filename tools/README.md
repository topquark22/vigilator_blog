# Editorial and publishing tools

Git is the authoritative editorial source. WordPress is the publication destination.
There is **no WordPress-to-Git content synchronization** or automatic publishing.

- `new_article.py` creates empty Markdown posts and JSON sidecars without overwriting files.
- `editorial_publisher.py` validates and previews committed Markdown and publishes an explicitly approved new or updated post, with readback verification.
- `wordpress_publisher.py` continues to handle guarded updates to existing imported Gutenberg posts/pages.

See [docs/EDITORIAL.md](../docs/EDITORIAL.md) for the new-content workflow.

## Reusable media import

The on-demand [`import-wordpress-media-manual.yml`](../.github/workflows/import-wordpress-media-manual.yml) workflow has **only** a manual `workflow_dispatch` trigger. The operator must select an `import/*` staging branch and check `confirm_import`; it does not execute on pushes, schedules, or merges. The former push-triggered workflow is retained at [`docs/archive/import-wordpress-media.yml`](../docs/archive/import-wordpress-media.yml). If GitHub Actions still exposes that old workflow from historical import branches, disable the old workflow separately via GitHub's Actions UI.

See [`docs/REVERSE_IMPORT.md`](../docs/REVERSE_IMPORT.md) for the on-demand runbook and its scope.

Its downloader is `tools/fetch_wordpress_media.py`, which verifies original file size, checks supported image signatures, writes per-asset SHA-256 metadata and does not contact the WordPress publishing API.

For a sample manifest, see `site/shared-media.json`. Stage the exact images specified in your article import; the final article commit is assembled separately from verified blobs without merging temporary workflow commits into `main`.

## Guarded WordPress publisher

`tools/wordpress_publisher.py` previews and (only with `--apply --confirm-id`)
publishes an approved Git revision of an existing WordPress post or page.
It requires authenticated raw-content preflight comparison, a confirmed
Git baseline, and WordPress readback verification. See
[`docs/PUBLISHING.md`](../docs/PUBLISHING.md) before using it.

The publisher is content-only for now: creating posts, updating media,
and automatically recording a new synchronization baseline are not
implemented. No live publication is triggered by a Git commit.
