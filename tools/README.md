# Synchronization tools

Reserved for future, separately reviewed CLI operations to:

- pull changes from WordPress into an import branch;
- compare them with Git and the last synchronized baseline;
- push **approved** Git revisions to WordPress;
- verify the content after a write.

There is **no executable sync or publishing implementation** in this scaffold.

## Reusable media import

The `import-wordpress-media.yml` GitHub Actions workflow runs only on `import/*` branches, after a push that changes `staging/media-manifest.json`, or through a manual workflow dispatch targeting such a branch.

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
