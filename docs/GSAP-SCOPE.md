# GSAP scope in this source candidate

The current bounded preset-and-parameter workflow has primary-source support as permitted GSAP use. A source-publication prohibition for this inspected interface has not been established. This conclusion does not relicense GSAP under MIT, give unrestricted permission for broader animation builders, or claim a product-specific written permission letter.

## Official terms and clarification

The bundled `vendor/gsap.min.js` identifies GSAP 3.15.0, Copyright 2026 GreenSock, and links to the [GSAP Standard License](https://gsap.com/standard-license), which redirects to the [official license page](https://gsap.com/community/standard-license/). The primary pages below were read on 2026-11-01. The standard license states an effective date of 2025-04-30 and last modification of 2025-05-30.

- Section I defines the restricted case around competing no-code visual animation-building capabilities; it does not prohibit every graphical preset control.
- Section II grants use, reproduction, display and implementation for permitted uses.
- Section III.1 requires prior written consent for prohibited uses, rather than for every preset tool or commercial product.
- Section III.3 requires proprietary notices and branding to remain intact. The actual bundled header is retained without changes.

The [official administrator clarification for a curated preset tool](https://gsap.com/community/forums/topic/45477-gsap-lisence/) addresses preset selection, parameter adjustment, no blank-canvas timeline/keyframe editor, no arbitrary from-scratch visual animation authoring, and bundling GSAP in the described commercial plugin. The accepted answer by GSAP administrator Cassie states: **“This falls under permitted use!”** This is a relevant official precedent for that described architecture, not an individual permission letter for StoryMotion or all future tools.

## Architecture actually inspected

- `dashboard/template-editor.js` exposes inert declared field controls over bounded template parameters and JSON. It does not execute caller-supplied JavaScript or GSAP programs.
- `storymotion/template_fields.py` and the fixed template validators enforce parameter bounds and fixed module selections. They do not provide a blank-canvas timeline/keyframe authoring interface.
- `storymotion/template_studio.py` prepares selected fixed templates. `storymotion/compose.py` and `template_families.py` generate programmatic seekable animation from validated data.
- The inspected application calls HyperFrames for CLI checking and rendering. No direct product launcher for HyperFrames Studio or a general visual animation editor was found in these application paths. The existence of a separately installed tool's other capabilities does not itself establish that this application exposes them.

The curated preset/parameter clarification supports the current specialized video-template workflow as permitted use. This is a scope-specific assessment using the official terms and precedent; it is not a blanket declaration that GSAP is MIT/OSI licensed or that any downstream visual-builder fork is covered. If the product later adds a general freeform competing animation builder, that changed interface requires a new scope review and any permission required by the actual license.

No new original-code license choice, generic paid GSAP license, or extra owner approval is identified for the inspected bounded interface. Retain GSAP's own license and notice conditions alongside StoryMotion's original-code MIT grant.

## Historical private profile

The prior fixed silent-fixture development approval concerned a separate excluded private profile. Its CI evidence and old license binding are not transferred to this candidate or used as the basis for the preset-interface assessment above. Private entry points fail with `PRIVATE_PROFILE_NOT_DISTRIBUTED`; stale `.runtime/development` or `.runtime/ffmpeg` namespaces remain detectable to prevent fallback.

`renderers/ffmpeg-source.json` is a retained historical private build recipe. Its exact x264 GPLv2 notice is supplied for record consistency. That notice neither enables the private profile nor certifies future binary redistribution. Normal customer installation keeps independent pinned graphs, source/license checks and explicit download gates.
