# Preparing a source release

Review the public file list, MIT scope and retained third-party notices before any publication.
Do not include Git history from a private repository, work data, credentials, personal media, private AccountPacks or generated artifacts.

The tracked `SOURCE-MANIFEST.json` binds the source payload to a local payload commit and its exact file hashes.
It deliberately does not hash itself. After reviewed source edits, commit the payload, then run:

```sh
python3 -B tools/build_source_manifest.py
```

Review and commit only the refreshed manifest as the next commit. This avoids a self-referential commit/hash cycle.
The script does not install, accept any terms, grant media rights, certify native behavior, publish or push.
Original-code MIT permissions do not depend on this technical installation manifest.

Before publishing, independently review secrets and personal data; confirm upstream redistribution/notice obligations;
run the documented source tests and an authorized clean installation on each claimed platform.
`customer_release_ready`, `publication_ready`, native/browser acceptance and unresolved third-party rights must not be
promoted merely to make checks green. A source-distribution manifest keeps pending qualification explicit.
