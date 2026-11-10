# Synchronization baselines

Reserved for versioned, **non-secret** synchronization manifests.

A future sync tool should record the exact content identity acknowledged by both systems (WordPress ID, source path, Git commit, WordPress content hash and modification timestamp). This baseline is needed for three-way conflict detection.

Do not place API credentials, tokens, or local authentication state here. No manifests exist yet.
