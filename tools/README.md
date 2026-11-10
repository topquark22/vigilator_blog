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
