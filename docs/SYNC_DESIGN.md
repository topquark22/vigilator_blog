# Bidirectional WordPress ↔ Git sync design

**Design only.** There is no running synchronization pipeline or publisher yet.

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
