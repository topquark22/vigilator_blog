# Archived bidirectional WordPress ↔ Git sync proposal

**Superseded; do not implement or follow this proposal.** The active design is one-way **Git → WordPress**, described in [EDITORIAL.md](EDITORIAL.md) and [WORKFLOW.md](WORKFLOW.md). Direct WordPress dashboard edits are unsupported; unexpected remote drift blocks publication. The design below is preserved solely as historical context.

## Canonical files

- Content: `articles/YYYY-MM-DD/<slug>--wp-<id>.wp.html`, or `pages/...` for pages
- Metadata: adjacent `<slug>--wp-<id>.json`
- Baselines: future non-secret manifest in `sync-state/`
- Original directory date: WordPress site-local publication date, immutable after initial assignment
- Content representation: full raw serialized Gutenberg/WordPress block markup, preserved exactly

## Pull (WordPress to Git)

Read WordPress content with editable context, locate by stable numeric WordPress ID, compare with the last confirmed synchronized baseline, and prepare an import branch. Never change `main` or discard a Git edit without review.

## Push (Git to WordPress)

Read approved source from a specific Git commit and re-fetch WordPress before writing. If it differs from the baseline, halt. Update the existing post/page, retrieve it again, and verify the persisted content before advancing the recorded baseline.

## Conflict policy

| Git since baseline | WordPress since baseline | Behaviour |
|---|---|---|
| No | No | No operation |
| Yes | No | Publish candidate (requires approval) |
| No | Yes | Import candidate |
| Yes | Yes | Stop; three-way reconciliation |

Git and WordPress do **not** share an atomic transaction. A preflight read reduces overwrite risk but is not a perfect compare-and-swap. Use WordPress block-edit optimistic locking when appropriate, retry only after re-reading on conflict, and verify after every publication. Never report a successful sync before verifying.

## Authorization

The assistant's connected WordPress app access is not a reusable API credential for scripts. A standalone sync program will need separately configured WordPress authentication, stored outside Git. Publishing always requires an explicit user decision.

## Implementation milestones

1. Import one existing article with a stable path and verified full source
2. Implement read-only WordPress comparison and dry-run diff
3. Implement guarded, explicitly approved publish + readback verification
4. Implement import branches and baseline-aware three-way conflict detection
5. Add media and page handling without altering unrelated article formatting

## Importing original media with GitHub Actions

Historical instructions only: the former `.github/workflows/import-wordpress-media.yml` was archived to `docs/archive/import-wordpress-media.yml` and removed from the active workflows on `main` after the initial import. It staged original binaries on an isolated `import/*` branch, never published to WordPress, and never merged into `main`. Repository-wide disabling in GitHub Actions also prevents old import branches from invoking it.

1. Create an `import/<article-or-site>` branch from current `main`.
2. Add `staging/media-manifest.json` on that branch. It has the same structure as `site/shared-media.json`: a top-level `assets` array of reviewed WordPress attachment metadata, including `wordpress_media_id`, `original_filename`, `source_url`, `mime_type`, and `expected_size_bytes`.
3. Push the manifest commit. The workflow is triggered by the manifest change; it can also be started manually on an `import/*` branch from GitHub Actions.
4. GitHub Actions downloads the original binaries, verifies sizes and supported image signatures, computes SHA-256 checksums and commits **only the manifest-listed media paths** to the staging branch. It makes no change if the verified files are already current.
5. Inspect the staging artifacts. Construct one clean article commit on current `main` referencing the verified media Git blobs and the exact WordPress article source; do **not** merge staging commits or include the manifest in `main`.

The download requires access only to the approved public WordPress media URLs; no WordPress publishing credentials are used. A failed fetch or verification must block the article import rather than silently omit media. Media remain ordinary Git blobs, not Git LFS.
