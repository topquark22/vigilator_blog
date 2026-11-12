# On-demand WordPress-to-Git import

**Normal direction:** Git is authoritative and only explicitly approved Git revisions may be published to WordPress. The reverse direction is not a continuous synchronization service. Use it only when deliberately requested, and stage all changes for review.

## Media import: GitHub Actions

The workflow [`import-wordpress-media-manual.yml`](../.github/workflows/import-wordpress-media-manual.yml) has only a `workflow_dispatch` trigger. It **never** runs on `push`, `pull_request`, `schedule`, or merge. No WordPress OAuth credential is required for public media URLs. It downloads **only** the files listed in an explicitly reviewed `staging/media-manifest.json`; it does not download articles, pages, or WordPress drafts.

1. Create a new `import/<purpose>` branch **from the current `main`**. Do not reuse an old staging branch with unrelated changes.
2. Commit `staging/media-manifest.json` on that branch. Its top-level `assets` array follows [`site/shared-media.json`](../site/shared-media.json). For each item supply `wordpress_media_id`, `original_filename`, `source_url`, `mime_type`, and `expected_size_bytes`; review the public HTTPS source URLs and sizes before proceeding.
3. In GitHub, open **Actions → Import WordPress media to staging → Run workflow**. Select the `import/<purpose>` branch, check **confirm_import**, then start the run. The workflow refuses any branch not beginning `import/`, or a run without the confirmation checkbox. If an administrator disabled this **manual** workflow in GitHub's UI, re-enable it there before dispatch.
4. Review the job logs and Git changes on the staging branch. The downloader validates configured hosts, expected sizes and supported image signatures; it records SHA-256 hashes in metadata. The job commits only the manifest-listed media and metadata to the staging branch. It does **not** push to `main`.
5. Inspect the files, license/rights, and source before bringing **only the approved media blobs** into a separate reviewed article commit. Do not merge staging branches wholesale or add `staging/media-manifest.json` to `main`.

**Important:** The earlier push-triggered `import-wordpress-media.yml` is archived in [`docs/archive/`](archive/import-wordpress-media.yml). Historical `import/*` branches may still carry that file. Keep that *old* workflow disabled in GitHub Actions, and use newly created branches from `main`. A new manual workflow filename prevents unintentionally re-enabling the old workflow.

## Article or page recovery: manual review only

There is currently **no GitHub Actions workflow** that reads WordPress post bodies and turns them into Git commits. If an exceptional WordPress-to-Git content import is necessary, request it explicitly and use authenticated, read-only WordPress access to retrieve the complete editable Gutenberg content and metadata. Compare the result with the Git source and its last confirmed baseline. Prepare a separate review branch preserving the original WordPress ID and the repository's established file conventions; inspect the proposed diff before merging. Never overwrite a Git change, never automatically merge the imported version, and never treat this as routine bidirectional sync.

A failed import or an unexpected WordPress change does **not** authorize WordPress to become the source of truth. Publishing continues to use the guarded Git-to-WordPress workflow, with separate approval.
