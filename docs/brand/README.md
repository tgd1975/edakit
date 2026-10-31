# edakit brand

The logo, the colours and the type of edakit – the source the documentation site, the rule catalog and anything else
made for edakit draw from.

## Logo

The mark is a pair of curly braces drawn as PCB traces – 45° bends, round joins – with copper pads at the four ends
and a via in the middle: a part inside a code block. The wordmark is "edakit", lower case, in IBM Plex Mono Bold with
−0.04 em tracking. Every file is outlined SVG and needs no font.

| File | Use |
| --- | --- |
| `edakit-lockup.svg`, `edakit-lockup-dark.svg` | Mark and wordmark in colour, on light / dark grounds – the primary logo |
| `edakit-lockup-mono-black.svg`, `edakit-lockup-mono-white.svg` | One colour (#1d2626 / white): print, stamps, engraving |
| `edakit-mark.svg`, `edakit-mark-dark.svg` | Mark alone, in colour |
| `edakit-mark-mono-black.svg`, `edakit-mark-mono-white.svg` | Mark alone, one colour – e.g. on a board's silkscreen, or on the teal header of the site |
| `edakit-wordmark.svg`, `edakit-wordmark-dark.svg`, `edakit-wordmark-mono-white.svg` | Wordmark alone |
| `edakit-app-icon.svg` | Icon on a teal square: avatars, social cards, the README |
| `edakit-favicon.svg` | 16–48 px: pad holes dropped, only the centre via |

- Clear space: one via diameter on every side. Smallest mark: 24 px; below that the favicon.
- Don't recolour the pads teal, rotate the mark, or put the colour mark on teal – use the app icon or a mono file there.

## Colours

`tokens.json` holds every colour for the light and the dark theme, the type styles, spacing and radii. The rule
catalog's CSS (`docs/catalog/build.py`) uses the same names as custom properties (`--bg`, `--surface`, `--ink`,
`--muted`, `--line`, `--accent`, `--err` …); `edakit.css` sets the site's Material theme to the same teal.

| Token | Light | Dark | For |
| --- | --- | --- | --- |
| `accent` | #0e6c6a | #5cc4c0 | Links, focus rings, the logo's traces |
| `copper` | #b8691f | #e0954f | The logo's pads – graphics only, not text |
| `ink` | #1d2626 | #e3eaea | Text |
| `muted` | #5d6b6b | #97a6a6 | Secondary text |
| `bg` / `surface` | #f4f6f6 / #ffffff | #111717 / #182020 | Page / cards, tables |

## Type

IBM Plex Sans for text and headings (600), IBM Plex Mono for code and the wordmark – both from Google Fonts.
