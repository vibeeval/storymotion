# Exact upstream runtime notice supplement

The [machine-readable index](upstream-runtime-20261029.json) binds official package integrity, immutable upstream commits and retained notice hashes. It supplements the four historical HF notice gaps without replacing package-local evidence or granting commercial clearance.

## Completed technical evidence

- Reverified official `dfa@1.2.0`, `fontkit@2.0.4`, `brotli@1.3.3` archives against their exact SRI, recorded SHA256, package/README hashes and upstream `gitHead` commits. All three archives lack license-named members. Their exact upstream trees still lack a package-wide MIT copyright/permission text; fontkit's three test-font licenses are separate and unshipped.
- Retained the complete MIT text of Brotli's exact embedded C++ submodule `5ce9bf11b3fe0924d87b2a2d47eb7a53a76a4421`. That copyright is not assigned to the JavaScript wrapper by inference. The existing Google decoder Apache notice remains.
- Reverified the official `@img/sharp-wasm32@0.35.5` archive SRI/SHA256 and all four metadata members without installing or executing its WASM. Retained primary license texts for all 19 components named by exact `versions.json`, plus relevant patent/attribution records. Copies come from immutable upstream commits; only the initial license comment is copied from `turbojpeg.c`.

## Remaining technical evidence

The 19 primary component texts do not establish complete notices for every transitive or compiled object. LGPL license copies alone do not supply all original copyright notices, exact corresponding sources, modification/build records or materials needed to replace/relink LGPL components in a conveyed combined work. The package README also names `libnsgif` without a corresponding `versions.json` version; its actual compiled scope remains to establish.

The exact sharp tag selects `@img/sharp-libvips-dev-wasm32@1.3.4`. Its published build dispatcher passes no `wasm-vips` revision, and its WASM recipe defaults to `HEAD`. A current checkout must not be represented as the old build source. Locate an authoritative build snapshot/material record or obtain upstream clarification before claiming reproducible source/relink evidence. This is technical follow-up, not an owner-only license purchase decision.

The exact wrapper/port MIT texts for dfa, fontkit and brotli remain to acquire from the publisher. Missing documentation is not evidence of a commercial prohibition; generic MIT copyrights and other versions' notices must not be substituted.

## Distribution and rights boundaries

The inspected source allowlist ships no node_modules, WASM or native/browser/compositor executables. Install-time downloads and any future binary conveyance have separate notice, source and integration obligations. Retain relevant licenses/copyrights, patent notices and their conditions. For conveyed mozjpeg binaries or static combinations, upstream specifically requires documentation acknowledging the Independent JPEG Group; preserve the exact retained upstream documents when designing that distribution. No runtime binary is redistributed by this supplement.

The original-code EULA is unchanged. GSAP 3.15.0 and optional Remotion 4.0.537 are not commercially cleared here. Technical inventory must cover manual scene/object/camera/rig editing as well as fixed template forms. Remotion entity/headcount eligibility is an owner fact; integration-code provenance and arbitrary-code surface inventory are technical work. Fixture creator/generator/speaker provenance remains absent in the inspected history. Neutral samples promise no proprietary creative methodology.

All customer/native/commercial acceptance flags remain pending or false. No package was installed or executed, agreement accepted, private source exported, external upload performed or product source modified while preparing this supplement.
