# Synchronization baselines

Reserved for versioned, **non-secret** synchronization manifests.

For Git-authored Markdown posts, the article's adjacent JSON sidecar records the WordPress post ID, verified content SHA-256, WordPress modification timestamp, and URL after each confirmed publication. Commit this receipt to Git before a subsequent update. The legacy Gutenberg publisher continues to require an explicitly confirmed Git baseline commit. Neither workflow imports content edits from WordPress or attempts three-way synchronization.

Do not place API credentials, tokens, or local authentication state here. No manifests exist yet.
