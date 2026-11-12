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

For imported Gutenberg items, `YYYY-MM-DD` is the **original publication date in the WordPress site's local time**, not the latest modification date or Git commit date. Once assigned, a file's path remains stable even if its title, slug, or modification date changes. The WordPress numeric ID in the filename distinguishes otherwise similar entries.

Each `.wp.html` file will contain the **raw WordPress/Gutenberg block markup** (not HTML rendered for visitors). Its sidecar `.json` records the WordPress ID, URL, original date, and other synchronization metadata. Do not round-trip imported Gutenberg content through Markdown unless a conversion has been verified to preserve the content.

New articles are authored separately as `articles/YYYY-MM-DD/<slug>.md` with an adjacent `<slug>.json` editorial sidecar. Their directory date is the site-local **authoring** date. See [docs/EDITORIAL.md](docs/EDITORIAL.md).

## Editorial conventions

- Import **one article per commit**, including its source and metadata. Pages may likewise be imported individually.
- Edit on branches; review diffs and merge to `main` before publication.
- Publishing to WordPress requires separate, explicit approval; merging alone does not publish.
- Git is authoritative: do not make manual WordPress-side edits. The publishers block on detected WordPress drift rather than importing dashboard changes.
- Exceptionally, manual-only [WordPress-to-Git media staging](docs/REVERSE_IMPORT.md) is available on an `import/*` review branch; it never runs automatically or overwrites `main`.
- Keep secrets, API credentials, exports, and local caches out of version control.
- For substantive corrections to published articles, consider a dated public editorial correction note as well as the Git history.

See [docs/WORKFLOW.md](docs/WORKFLOW.md), [docs/EDITORIAL.md](docs/EDITORIAL.md), and [docs/PUBLISHING.md](docs/PUBLISHING.md). `docs/SYNC_DESIGN.md` is an archived, superseded two-way proposal.

**Status:** existing WordPress articles/pages and media have been imported. A guarded legacy Gutenberg publisher and a separate new-article Markdown publisher have offline tests. Live publication remains an explicit, credentialed operation and has not been tested end-to-end.
