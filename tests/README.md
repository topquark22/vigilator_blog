# Tests

Offline unit tests cover the guarded legacy Gutenberg publisher and the one-way Markdown editorial publisher, including path and metadata validation, conversion, explicit approval, creation and update guards, WordPress drift detection, and readback verification. They require no WordPress credentials or network.

Run from the repository root:

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

WordPress dashboard edits are unsupported; unexpected remote changes must block publication.
