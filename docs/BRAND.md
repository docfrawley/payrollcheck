# Brand

PayrollCheck keeps the UnderCover design system, with a palette of its own taken from the job site: navy, hi-vis amber and the colors of survey marks and permits. Stage 1 applies it.

## Fonts

From Google Fonts:

- **Headings and body**: Instrument Sans
- **Accent (a tagline or a quote)**: Instrument Serif
- **Code, numbers and identifiers**: JetBrains Mono. Money and IDs are always set in it, such as $1,284.60 and PC-0311

## Colors

- **Primary**: Hi-Vis Amber `#F5A524`, Steel Navy text. The mark and the key actions, such as Sign off and Start a dispatch
- **Information**: Survey Blue `#2D7DD2`, white text
- **Accepted and clean**: Permit Green `#2E9E6A`, Steel Navy text
- **Medium-severity exceptions**: Rebar Rust `#C4572A`, white text
- **High-severity exceptions and screening flags**: Stop Red `#D7263D`, white text
- **Ink on light backgrounds**: Steel Navy `#12263A`
- **Ink on dark backgrounds**: Chalk `#D5DDE5` (proposed)

### The statuses

| Status | Color |
|---|---|
| Received | Grey, Slate `#5F6B78` (proposed) |
| In progress | Survey Blue |
| Awaiting review | Hi-Vis Amber |
| Accepted | Permit Green |
| Returned to sub | Rebar Rust |

When the statuses sit side by side, as in a chart of the queue, use them in this order.

## Surfaces

- **Light mode**: page background `#F2F4F7` (proposed), white panels and cards
- **Dark mode**: page background `#0B1724` (proposed), black panels and cards

Panels are rounded with no outline, and a faint shadow.

Hi-Vis Amber is too bright for small text on a light background, so darken it for headings and body text there, to about `#8F5A00`, and lighten it on dark backgrounds, to about `#FFC766`. Do the same for the other colors wherever they carry small text: on white, Survey Blue and Permit Green are under 4.5:1 as they are, and Survey Blue's white text is too.

The proposed backgrounds, inks, grey and text shades are to be checked for WCAG AA contrast (4.5:1 for body text, 3:1 for large text and icons) when stage 1 applies them, and adjusted if they fail.

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
