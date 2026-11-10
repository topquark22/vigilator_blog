# Editorial workflow

## Initial import

1. Obtain the full **editable** source for a WordPress article or page and its original publication timestamp.
2. Assign its stable path under `articles/YYYY-MM-DD/` or `pages/YYYY-MM-DD/`, using the WordPress site's local calendar date.
3. Store the exact serialized Gutenberg/WordPress content in `<slug>--wp-<id>.wp.html`, with a sidecar `<slug>--wp-<id>.json` conforming to `schemas/wordpress-item.schema.json`.
4. Commit **one article per Git commit** (source and metadata together). Do not combine unrelated imports.

WordPress numeric IDs and original dates are stable identifiers. Changing a published article's title or URL must **not** automatically move its existing source path.

## Editing and review

- Create a feature branch from the current `main`.
- Apply the smallest possible edits; preserve block markup and unrelated formatting.
- Review the complete proposed diff and commit before merging.
- Use a separate commit for each article whenever practical.
- Avoid silent automatic publishing. Changes merged into `main` become **eligible** to publish, not automatically live.

## Publication

1. Read the current WordPress article and the last synchronized baseline.
2. If WordPress differs from the baseline, stop for import/reconciliation.
3. Publish only explicitly approved content to the **existing WordPress ID**.
4. Read back the resulting editable content; verify what WordPress actually stored.
5. Update the synchronization baseline only on verified success.
6. For substantive factual corrections, record an appropriate dated public correction notice if editorially warranted.

## Importing WordPress-side changes

Pull the complete current WordPress article into a dedicated import branch. If Git independently changed since the last synchronized baseline, stop and reconcile a three-way difference rather than overwriting either version.

## Confidentiality

Never commit authentication credentials, private configuration, or exports containing unrelated user data.
