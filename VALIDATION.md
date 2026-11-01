# Validation boundaries

Source checks exercise synthetic fixtures, local input validation, provider request contracts,
template compilation, local session/HTTP handler logic and platform contracts. Providers remain off
unless a test uses an explicitly synthetic transport. Memory-stream HTTP tests do not establish real
browser/network acceptance. Unit tests do not install renderer dependencies or make paid calls.

Run from the root:

```sh
python3 -B -m unittest discover -s tests -v
sh ./install.sh preflight
```

On Windows use `python -X utf8 -B` and `install.ps1 preflight` instead. Preflight makes no download;
before installation, `ok: false` reports missing runtime dependencies while `source_install_ready`
separately reports source-manifest integrity. Do not promote readiness flags to hide missing checks.

The public test selection excludes private acceptance certificates, signed evidence producers,
old proprietary customer-promotion pipelines and the unshipped experimental adapter. It retains
the product's runtime and safety contracts. No private acceptance record is inherited by this tree.

Current release review must separately establish third-party redistribution/notice obligations,
authorized installation on a clean Mac, native Windows 10/11 x64/NTFS installation and actual
browser/render/audio/visual checks. Static Windows contract tests run on a Mac are not Windows execution.
No hosted CI, clean-device installation or comprehensive 91-template visual acceptance is claimed here.
