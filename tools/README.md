# Editorial and publishing tools

Git is the authoritative editorial source. WordPress is the publication destination.
There is **no WordPress-to-Git content synchronization** or automatic publishing.

- `new_article.py` creates empty Markdown posts and JSON sidecars without overwriting files.
- `editorial_publisher.py` validates and previews committed Markdown and publishes an explicitly approved new or updated post, with readback verification.
- `wordpress_publisher.py` continues to handle guarded updates to existing imported Gutenberg posts/pages.

See [docs/EDITORIAL.md](../docs/EDITORIAL.md) for the new-content workflow.

## Reusable media import

The former `import-wordpress-media.yml` GitHub Actions workflow is archived at [`docs/archive/import-wordpress-media.yml`](../docs/archive/import-wordpress-media.yml) and is no longer active on `main`. It previously ran on `import/*` branches when `staging/media-manifest.json` changed, or by manual dispatch. GitHub's repository-wide **Disable workflow** control should also be used to prevent invocation from older import branches.

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
