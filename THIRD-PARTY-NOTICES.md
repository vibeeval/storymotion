# Third-party notices

Original StoryMotion code and original project documentation licensed by StoryMotion contributors are offered under the MIT License in LICENSE. That original-code grant does not relicense any third-party material or establish ownership of historical fixture media. LICENSING.md describes the scope. This candidate does not retain the previous original-code software-resale prohibition.

The source allowlist includes original software, bundled GSAP/font files, bounded MIT code adaptations and technical fixtures. It excludes node_modules, installed browser/codec binaries and private development profiles. Dependency downloads and any future binary redistribution have separate obligations. A lockfile or retained license text is evidence, not blanket commercial clearance.

Schibsted Grotesk's OFL-1.1 text and the bounded MG adaptation's MIT notice are retained. These licenses permit commercial use subject to their conditions; no additional purchase requirement is established for those materials. Preserve their copyrights/licenses, keep font copies under OFL and do not sell the fonts by themselves. This does not license excluded upstream media or future caller assets.

GSAP 3.15.0 retains its original header in vendor/gsap.min.js. Its [standard license](https://gsap.com/community/standard-license/) generally permits no-charge commercial use but restricts competing visual-animation builders. Applicability of that restriction to this product’s architecture remains unresolved; no clearance or generic paid-license requirement is claimed here.

## Pinned package evidence

`parse-cache-control@1.0.1` is verified as BSD-3-Clause from the actual published `package/LICENSE`. Its complete copyright, three conditions and disclaimer are retained verbatim in `vendor/licenses/parse-cache-control-1.0.1.LICENSE` (SHA256 `111f42b37daecc6c387d037ef25955bd269e7f9a46a736d5257a23560534763f`). The official tarball integrity matches the current lock. The Zod4.6.7 override changes dependency resolution, without clearing third-party rights. Source: https://registry.npmjs.org/parse-cache-control/-/parse-cache-control-1.0.1.tgz .

Eight version-4.0.537 Remotion artifacts (`@remotion/media` and seven platform compositor packages) contain no package-local LICENSE file, and their published package metadata has no license field. The exact upstream tag resolves to commit `f8ab752182a802f76904f7343e0d70189a1dea0e`; its root license is retained as `vendor/licenses/remotion-4.0.537-UPSTREAM-ROOT-LICENSE.md` (SHA256 `bd65083b940f61904f6ef298aade918a7cad72a3e35bc406e36fab365844b673`). This is explicitly upstream-root evidence, not an invented package LICENSE or clearance for those artifacts or this product. Upstream clarification and commercial eligibility review remain pending.

`vendor/licenses/SOURCES.json` records the pinned official tarball URLs, SRI evidence and scope of each retained license reference. `docs/DEPENDENCY-LOCK.json` remains a lock inventory, not proof that every package's actual license text has been reviewed. Applicable notices, GSAP builder terms and assets remain under review. Corresponding-source and binary obligations depend on the actual binary conveyed; this source allowlist contains no runtime binaries. LICENSE provides the owner-authorized MIT grant for original StoryMotion code and original project documentation only; it does not clear third-party obligations.

## Current HF notice supplement

[hf-runtime-sources.json](docs/notices/hf-runtime-sources.json) supplements the earlier pinned evidence with exact available texts for four gaps in the 94-package Darwin arm64 HF install. Package code, native/WASM payloads and node_modules are not shipped by this source allowlist. The supplement retains incomplete status for all four packages:

| Exact package | Retained evidence | Remaining gap |
|---|---|---|
| @img/sharp-wasm32 0.35.5 | Exact Apache-2.0 LICENSE, publisher README and 19 component versions; immutable upstream primary component texts in the linked supplement. | Transitive/compiled component notices, all copyrights and exact source/relink evidence remain incomplete. Apache alone does not cover the WASM. |
| brotli 1.3.3 | Exact Google decoder Apache notice and Apache text; exact embedded C++ submodule MIT text; publisher MIT declaration. | Wrapper/port MIT copyright and permission text remains missing; upstream C++ copyright is not assigned to it by inference. |
| dfa 1.2.0 | Exact package/README hashes and publisher MIT declaration. | Complete copyright/license text tied to this release. |
| fontkit 2.0.4 | Exact package/README hashes, publisher MIT declaration and the attributed base64 helper's [exact MIT notice](docs/notices/fontkit-base64-arraybuffer-LICENSE.txt) with [source record](docs/notices/fontkit-base64-arraybuffer-SOURCE.json). | Complete package-wide copyright/license text tied to this release. |

The original package-local license files are absent for the last three packages. A missing text is an evidence gap, not proof of a commercial prohibition. No generic MIT text or a different version's copyright is substituted. Required vendor copyright notices must remain during provenance cleanup.

## Immutable upstream notice supplement

[Exact upstream evidence](docs/notices/upstream-runtime-20261029.md) and its [hash index](docs/notices/upstream-runtime-20261029.json) retain primary license texts for all 19 version-declared sharp components, relevant patent/attribution records, and the MIT text of Brotli's exact embedded C++ submodule. The three MIT-declared wrapper packages still lack complete package-wide copyright/permission texts. Exact official archive SRI/SHA256, metadata and release gitHead bindings were reverified without installation or execution. Upstream-root/component evidence is not a fabricated package-local license.

The sharp WASM build's published recipe defaults to an unpinned wasm-vips HEAD. Exact corresponding source/build/relink evidence and complete transitive notices remain unverified; the 19 primary texts do not close obligations applicable to a future binary conveyance. The historical supplement itself changed no original-code license or commercial/customer/native acceptance flag and shipped no runtime binary. The current original-code MIT grant is separate; it does not close these upstream evidence gaps.

## Separate graphs and independent probe

The default core graph has 142 locked entries and no Remotion/React. The explicit addon in `optional/remotion` has 310 locked entries, including 29 actual Remotion packages. `parse-cache-control` belongs to core; the eight absent package-local license references belong to the addon. Both locks and their exact digests are inventoried by graph in `docs/DEPENDENCY-LOCK.json`. Per-graph counts include duplicate code installed in separate namespaces; they are not distinct-code counts. Optional selection does not resolve licensing obligations for either graph.

Independent ffprobe is built locally from the hash-pinned official FFmpeg8.1.3 source; it is not taken from Remotion. The configured recipe disables GPL, nonfree, version3 and networking and enables system zlib. Actual source `LICENSE.md` and LGPL2.1 text are retained in `vendor/licenses/ffmpeg-8.1.3-*`; the system zlib notice is retained as `vendor/licenses/zlib-NOTICE.txt`. Conditional licenses for other source configurations are explained in that upstream LICENSE. Downloaded source and license copies remain alongside the local build receipt. No ffprobe executable or source tarball is redistributed in this source candidate. Binary redistribution/corresponding-source obligations need a separate verified design; this candidate supplies no such clearance.

Two independent source builds and WAV/MP3/PNG probes were verified on macOS arm64 with an existing SDK. This is not engine/browser/clean-device or other-platform acceptance. Applicable core notices, GSAP builder terms and asset rights remain under review. The optional Remotion artifact clarification applies when that addon is offered; it is not an HF-only eligibility requirement. Any conveyed FFmpeg-static binary has separate obligations. No new third-party agreement is accepted by engine selection or source compilation.

The private FFmpeg 8.1.3/x264 build enables GPL and is distinct from the LGPL probe and the npm ffmpeg-static 5.3.0 wrapper. The private build's corresponding-source/build obligations apply if that binary is conveyed; the wrapper version does not identify its separately downloaded executable. No wrapper-downloaded binary is cleared by the private recipe. Commercial use is not automatically forbidden by GPL; actual distribution/integration must satisfy applicable terms. Chrome for Testing 152.0.7977.30 is also an install-time binary: its exact executable/component notices remain separate from the browser-download tooling's license. Neither binary is bundled here.

The pinned optional Remotion 4.0.537 [root license](vendor/licenses/remotion-4.0.537-UPSTREAM-ROOT-LICENSE.md) permits free commercial video/image creation for individuals, qualifying organizations with up to three employees and nonprofits, subject to that text. Other organizations need the applicable Company License. Its separate derivative-resale restriction requires an architecture/scope decision; buying a license is not stated to override that restriction. The addon remains optional, and no terms are accepted here.

## Technical fixture provenance

[fixtures/PROVENANCE.json](fixtures/PROVENANCE.json) and the current [generation receipt](fixtures/GENERATION.json) record fresh zero-input production of the geometric PNG, silent WAV and silent MP3. The actual project geometry/PCM recipes were used, followed by existing LAME encoding for the MP3 and independent full zero-PCM decode. All three fresh outputs match the earlier candidate bytes; matching does not identify the earlier historical creator. These current original technical fixtures are under the project MIT grant, with no external image, speaker, recording or caller-media input. The LAME and decoder executables are not bundled; their software terms remain separate. Silence is not natural-speech or voice acceptance.

The neutral rig's programmatic vector source is bound to a dated own-project declaration and exact source hash in [neutral-rig-origin.json](renderers/neutral-rig-origin.json). The current original-source MIT grant resolves the earlier public-license-selection placeholder for that original source; it grants no third-party artwork, personal-voice or caller-media rights. Technical RGB proxies in media templates are not caller-media clearance.

## Bounded template adaptations

The liquid-merge, bauhaus-modules and pixel-journey numerical techniques adapt MG07/MG09/MG20 from Vincentwei1021/mg-styles-15 commit 49052d80bfaf9fa8412cc9710530e5e95a3b8d8c, MIT. Copyright (c) 2026 Vincentwei1021. The full notice is retained at vendor/notices/mg-styles-15-MIT.txt and copied into prepared assets/notices/. Source films, prompts, music, fonts, sprites and characters are not included. catalog/style-adapters.json records the bounded source/code scope. Other engine, GSAP and asset conditions remain applicable.

## Windows install-time media package

Windows x64 uses the publisher’s FFmpeg/ffprobe 9.0.2 essentials build, separately pinned in [windows-media.json](renderers/windows-media.json). [Publisher build information](https://www.gyan.dev/ffmpeg/builds/) identifies these builds as 64-bit, Windows 10 or later and GPLv3. The [versioned checksum](https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip.sha256) binds the install-time archive. The archive and its actual license are retained locally after authorized download; this source ZIP redistributes neither executable. These Windows binaries are distinct from the macOS LGPL probe recipe and from the ffmpeg-static npm wrapper. No third-party agreement is accepted, redistribution clearance asserted, or native Windows execution claimed.

## Disabled historical private profile

The excluded CI/private-build approvals are not distributed or transferred to this candidate. Python and JavaScript private entry points fail with `PRIVATE_PROFILE_NOT_DISTRIBUTED`; existing private runtime namespaces remain detectable to prevent fallback. The retained historical `ffmpeg-source.json` recipe references the exact [x264 GPLv2 notice](vendor/licenses/x264-b35605a-COPYING.GPLv2), copied without changes to match its recorded SHA256. This supplies the referenced notice and enables no private build, download, binary conveyance or acceptance.
