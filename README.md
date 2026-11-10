# Words of a Watchman — source repository

Git-managed editorial source for [vigilator.blog](https://vigilator.blog).

WordPress hosts the public site. Git tracks proposed and approved revisions. Publishing and importing are **explicit operations**; nothing in this scaffold automatically changes WordPress.

## Layout

```text
articles/
  YYYY-MM-DD/
    <original-slug>--wp-<id>.wp.html
    <original-slug>--wp-<id>.json
pages/
  YYYY-MM-DD/
    <original-slug>--wp-<id>.wp.html
    <original-slug>--wp-<id>.json
media/
docs/
schemas/
sync-state/
tools/
tests/
```

`YYYY-MM-DD` is the **original publication date in the WordPress site's local time**, not the latest modification date or Git commit date. Once assigned, a file's path remains stable even if its title, slug, or modification date changes. The WordPress numeric ID in the filename distinguishes otherwise similar entries.

Each `.wp.html` file will contain the **raw WordPress/Gutenberg block markup** (not HTML rendered for visitors). Its sidecar `.json` records the WordPress ID, URL, original date, and other synchronization metadata. Do not round-trip through Markdown unless a conversion has been verified to preserve the content.

## Editorial conventions

- Import **one article per commit**, including its source and metadata. Pages may likewise be imported individually.
- Edit on branches; review diffs and merge to `main` before publication.
- Publishing to WordPress requires separate, explicit approval; merging alone does not publish.
- Before either import or publication, compare Git, WordPress, and the last synchronized baseline. If both sides changed, **stop and reconcile**, never overwrite silently.
- Keep secrets, API credentials, exports, and local caches out of version control.
- For substantive corrections to published articles, consider a dated public editorial correction note as well as the Git history.

See [docs/WORKFLOW.md](docs/WORKFLOW.md) and [docs/SYNC_DESIGN.md](docs/SYNC_DESIGN.md).

**Status:** directory scaffold and documentation only. The two-way synchronization tools and actual article imports have **not** yet been implemented.
