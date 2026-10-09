# Third-party sources and provenance

Askr is MIT-licensed, but bundled third-party assets retain their own
licenses. Original license texts are also packaged in `_extensions/askr/licenses`.

| Material | Upstream identity and path | SHA-256 | Modification |
| --- | --- | --- | --- |
| Quartz design reference | `jackyzha0/quartz@d25a6eabf96751ffca56f8a8139272def7a65041`; `styles/callouts.scss`, `base.scss`, `variables.scss`, `quartz.config.ts` | n/a (consulted, not bundled) | Quartz tokens, type/rhythm, links, code and callout visual rules adapted to Quarto DOM; no Quartz runtime or grid transplanted. |
| Schibsted Grotesk regular | `schibsted/schibsted-grotesk@d485f61f105e1b3935f4d21dfb4d371359798603`; `fonts/webfonts/SchibstedGrotesk-Regular.woff2` | `9c90d8cf65fffe63975783a7a05afcc85b7666104d6f377b25edc9e7295ed9c7` | Unmodified; title and UI 400. |
| Schibsted Grotesk bold | same revision; `fonts/webfonts/SchibstedGrotesk-Bold.woff2` | `cb3017aa6302a4f3deb7a658d9a26979d6bdf8d7fbfb4fc771bfe6b86a21ccf9` | Unmodified; title and UI 700. |
| Source Sans 3 upright | `adobe-fonts/source-sans@87b37a2daaed80fcb8e8ccb0085c4d72ddade12e`; `WOFF2/VF/SourceSans3VF-Upright.ttf.woff2` | `5f16566f7a40d39b339ad26be151fa5a1ab1f0c2574c7a2e619765584a1acbd8` | Unmodified; intentional version-pinned Source Sans Pro successor for body 400/600. |
| Source Sans 3 italic | same revision; `WOFF2/VF/SourceSans3VF-Italic.ttf.woff2` | `b4959abc0569392f87c6c6ac612f90e3fe0104d283724189b7d8b6f61af347d3` | Unmodified; body italic 400/600. |
| IBM Plex Mono regular | `IBM/plex@763c36ef9117782905ae010056dfbe8fd2653a25`; `packages/plex-mono/fonts/complete/woff2/IBMPlexMono-Regular.woff2` | `ba204497f16b6d334cee9d1e963a831b73e3a56e1d6300a8489d18df7214b350` | Unmodified. |
| IBM Plex Mono italic | same revision; `IBMPlexMono-Italic.woff2` | `2024bf2b08027dcd6d09091385756e327744bbe26b782c411381dffc40ffc622` | Unmodified. |
| IBM Plex Mono bold | same revision; `IBMPlexMono-Bold.woff2` | `ea576f38d05cc44cca48c45314984beb8cc1d2b886f58e1dce99f15dc344eb1d` | Unmodified. |
| IBM Plex Mono bold italic | same revision; `IBMPlexMono-BoldItalic.woff2` | `03e97fe28d44cc2bdf18d77284046bc9019ee626bdab1f06e7ea64837680824b` | Unmodified. |
| Lucide icons | `lucide-icons/lucide@f06ac67e33d645c40b8ce19a0419c85c5d7dd751`; `icons/{info,flame,circle-alert,triangle-alert,octagon-alert}.svg` | See `ASSET_MANIFEST.md`. | Unmodified files used through CSS masks. |

Quartz is MIT licensed. Schibsted Grotesk, Source Sans 3 and IBM Plex Mono are
SIL Open Font License assets. Lucide is ISC licensed and includes Feather-derived MIT
notices. See the packaged notices for their complete terms.
