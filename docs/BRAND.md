# Brand

PayrollCheck keeps the UnderCover design system, with a palette of its own taken from the job site: navy, hi-vis amber and the colors of survey marks and permits. Stage 1 applied it, in `dashboard/src/styles.css`, and checked every pairing below for WCAG AA contrast.

## Fonts

From Google Fonts:

- **Headings and body**: Instrument Sans
- **Accent (a tagline or a quote)**: Instrument Serif
- **Code, numbers and identifiers**: JetBrains Mono. Money and IDs are always set in it, such as $1,284.60 and PC-0311

## Colors

- **Primary**: Hi-Vis Amber `#F5A524`, Steel Navy text. The mark and the key actions, such as Sign off and Start a dispatch
- **Information**: Survey Blue `#2D7DD2`, white text. As a fill under white text it is darkened to `#2A6FBB` (5.13:1), since `#2D7DD2` gives 4.22:1
- **Accepted and clean**: Permit Green `#2E9E6A`, Steel Navy text
- **Medium-severity exceptions**: Rebar Rust `#C4572A`, white text. As a fill under white text it is darkened to `#B4501F` (5.11:1), since `#C4572A` gives 4.43:1
- **High-severity exceptions and screening flags**: Stop Red `#D7263D`, white text
- **Ink on light backgrounds**: Steel Navy `#12263A`
- **Ink on dark backgrounds**: Chalk `#D5DDE5`

### The statuses

| Status | Color |
|---|---|
| Received | Grey, Slate `#5F6B78`, white text |
| In progress | Survey Blue |
| Awaiting review | Hi-Vis Amber |
| Accepted | Permit Green |
| Returned to sub | Rebar Rust |

When the statuses sit side by side, as in a chart of the queue, use them in this order.

Until stage 3 brings these statuses, the app's states take their colors, in the same order: waiting Slate (as Received will be), in progress Survey Blue, waiting for sign-off Hi-Vis Amber (as Awaiting review will be), decided Permit Green, sent back Rebar Rust (as Returned to sub will be), and left for a reviewer Stop Red. Refused and failed steps are Stop Red. The judge's grades are A Permit Green, B Survey Blue, C Hi-Vis Amber and F Stop Red, and a diff's added lines are tinted Permit Green and its removed lines Stop Red.

## Surfaces

- **Light mode**: page background `#F2F4F7`, white panels and cards
- **Dark mode**: page background `#0B1724`, black panels and cards

Panels are rounded with no outline, and a faint shadow.

Hi-Vis Amber is too bright for small text on a light background, so it is darkened there to `#8F5A00`, and lightened on dark backgrounds to `#FFC766`. The other colors are shaded the same way wherever they carry small text, since several fall under 4.5:1 as they are (Permit Green on white 3.38:1, Stop Red on black 4.23:1, Slate on black 3.86:1):

| Small text | Light mode | Dark mode |
|---|---|---|
| Hi-Vis Amber | `#8F5A00` | `#FFC766` |
| Survey Blue, and links | `#1F63AE` | `#6AA8EC` |
| Permit Green | `#1D7A50` | `#5CC795` |
| Rebar Rust | `#A9461F` | `#E8845B` |
| Stop Red | `#C01F34` | `#FF6B7D` |
| Slate | `#5F6B78` | `#9AA5B1` |
| Muted text, a little darker than Slate | `#4F5D6B` | `#9AA5B1` |

### Contrast

Checked in stage 1 with the WCAG 2 formula: 4.5:1 for body text, 3:1 for large text and icons. In the browser, a script measured every element's text against its background on every page, in both modes and at five widths, with none under the bar.

| Pairing | Ratio |
|---|---|
| Hi-Vis Amber fill, Steel Navy text | 7.54 |
| Permit Green fill, Steel Navy text | 4.56 |
| Stop Red fill, white text | 4.96 |
| Slate fill, white text | 5.44 |
| Survey Blue fill `#2A6FBB`, white text | 5.13 |
| Rebar Rust fill `#B4501F`, white text | 5.11 |
| Steel Navy on the light page / on white | 13.97 / 15.40 |
| Chalk on the dark page / on black | 13.17 / 15.30 |
| Amber text `#8F5A00` on white / the light page | 5.78 / 5.25 |
| Amber text `#FFC766` on black / the dark page | 13.61 / 11.71 |
| Amber mark on the navy band / the black band | 7.54 / 10.29 |
| White on the navy band | 15.40 |
| Slate text on the light page | 4.94 |

## The header

The header is a band of Steel Navy across the top of the page (black in dark mode), with white text and the brand's mark, the Lucide `clipboard-check` icon in Hi-Vis Amber, beside the wordmark **PayrollCheck** in Instrument Sans semibold. The band always shows two things on every page:

- The chip "Synthetic data — not real rates", always visible
- The business date

## Icons

Lucide icons, where an icon says something at a glance: a status, a severity, an action's button, a choice. Beside text, an icon is the text's size; on a tile or a card of its own, it can be larger. Never emojis.

## Avoid

- Borders on one edge of a panel, and thin lines across the top of the page
- Heavy use of gradient fills

## Tone

Plain business English in US spelling. Short labels, no jargon and no exclamation marks. Be exact and never alarmist: "3 exceptions, $1,284.60 short", not "Violation detected!". Money is in US dollars, such as $1,250.00.
