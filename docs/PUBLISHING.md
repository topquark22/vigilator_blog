# Publishing approved Git content to WordPress.com

The publisher is `tools/wordpress_publisher.py`. It uses only the Python
standard library. **Nothing publishes automatically.**

## Scope (first version)

- Safely preview a Git content change for an **existing published** WordPress
  post or page; send the approved Gutenberg markup on explicit request.
- Compare WordPress's current **editable/raw** content against the **last
  confirmed synchronized Git commit**. Abort on any direct WordPress change
  or modification timestamp mismatch.
- Preserve ID, slug, original publication date, publication status, featured
  image, title and other metadata by sending **only** the content field.
- Verify the result with a fresh, authenticated WordPress read.
- Reject uncommitted data, publishing from a non-`main` commit, and missing
  confirmation.
- Does **not** yet support new post creation, media replacement, editing
  titles/metadata, automatic sync-baseline commits, or a web preview.

The current WordPress.com site is **228574095 (vigilator.blog)**. The API
uses the WordPress.com proxy at
`https://public-api.wordpress.com/wp/v2/sites/228574095/`. It authenticates
with a WordPress.com OAuth2 Bearer token supplied by the
`WORDPRESS_ACCESS_TOKEN` environment variable. The ChatGPT WordPress
connection does not provide this token to local Python scripts.

Get an appropriately scoped token through WordPress.com's documented
OAuth2 process. **Never** add it to Git, put it in the CLI arguments, paste
it into chat, or print it in diagnostic logs. Use your system's secure secret
storage, and for GitHub Actions use repository or environment secrets. The
publisher makes no authentication-token requests on its own.

## Commands

Choose the complete Git SHA of the reviewed `main` commit containing your
desired article version. The baseline SHA is the commit that contains the
version **currently published** in WordPress.

Example: the existing Nord Stream post, WordPress ID 220:

```bash
python tools/wordpress_publisher.py \
  --path articles/2026-01-21/deutschlands-energiepolitische-sackgasse-eine-selbstverschuldete-krise--wp-220.wp.html \
  --commit FULL_APPROVED_MAIN_SHA \
  --baseline-commit FULL_LAST_SYNCED_SHA
```

The command above is a **dry run**, even if content differs. It prints the
proposed diff and hashes but never writes to WordPress.

Only after reviewing the diff and explicitly authorizing publication:

```bash
python tools/wordpress_publisher.py \
  --path articles/2026-01-21/deutschlands-energiepolitische-sackgasse-eine-selbstverschuldete-krise--wp-220.wp.html \
  --commit FULL_APPROVED_MAIN_SHA \
  --baseline-commit FULL_LAST_SYNCED_SHA \
  --apply --confirm-id 220
```

Here `FULL_..._SHA` are placeholders, not executable values.

If WordPress has changed since the baseline (including a metadata-only
edit that changes its modification timestamp), **stop and reconcile first**.
A post already matching the target content is a no-op.

After publishing, record the approved commit and the reported WordPress
modification timestamp in a new reviewed Git baseline commit. This first
version intentionally **does not update the baseline automatically**.
Subsequent publishing must use the newer confirmed baseline; reusing a
stale baseline correctly causes the next change to be rejected.

WordPress does not provide the same atomic compare-and-swap semantics as
Git. A write can still race with a dashboard editor between the preflight
read and the update; the post-write verification detects discrepancies, but
does not eliminate that race. The WordPress API may also normalize Gutenberg
markup during a save; in that case the script reports a verification failure
and the live post needs inspection.

## Testing

```bash
python -m unittest discover -s tests -p 'test_wordpress_publisher.py' -v
```

Offline tests run without credentials or network calls. A live end-to-end
publish has **not** been performed yet; begin with a disposable draft and
explicit authorization before relying on the publisher for public articles.

See WordPress.com's official REST API documentation:
https://developer.wordpress.com/docs/api/getting-started/
