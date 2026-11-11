# Editorial workflow

## New Git-authored articles

Use `tools/new_article.py` to create a new `articles/YYYY-MM-DD/<slug>.md` and adjacent `<slug>.json`, then edit, review, and commit the source. The Markdown publisher renders supported markup into Gutenberg blocks without changing the imported `.wp.html` files. See [EDITORIAL.md](EDITORIAL.md). Git is authoritative; do not edit content in the WordPress dashboard.

## Initial import (historical WordPress content)

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

1. Review and merge the article's committed Git source to `main`; this does not publish.
2. For new Markdown posts, run `tools/editorial_publisher.py` in offline preview mode, then require explicit `--apply --confirm-slug` for a live create or update. For imported Gutenberg posts, continue to use `tools/wordpress_publisher.py` with its existing baseline guards.
3. Verify the WordPress editable readback after any write.
4. For a new Markdown post, commit the verified receipt fields to its JSON sidecar before attempting another update. For legacy Gutenberg posts, retain the confirmed baseline separately.
5. For substantive factual corrections, record an appropriate dated public correction notice if editorially warranted.

## WordPress dashboard edits

Direct edits in WordPress are outside the supported workflow. If a remote post unexpectedly differs from the last verified publication, block and investigate; there is no automatic reverse import or three-way merge.

## Confidentiality

Never commit authentication credentials, private configuration, or exports containing unrelated user data.
