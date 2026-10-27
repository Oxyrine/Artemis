---
name: Artemis
description: Editorial financial reporting with live variance evidence.
colors:
  background: "#f1f3f7"
  foreground: "#19283e"
  card: "#ffffff"
  card-foreground: "#19283e"
  popover: "#ffffff"
  popover-foreground: "#19283e"
  primary: "#315cdd"
  primary-foreground: "#ffffff"
  secondary: "#e9edf5"
  secondary-foreground: "#263f6c"
  muted: "#edf1f7"
  muted-foreground: "#5c6a80"
  accent: "#e6edff"
  accent-foreground: "#234cbf"
  border: "#dce2ec"
  input: "#c8d2e2"
  ring: "#4168dc"
  brand-ink: "#315cdd"
  sidebar-ground: "#142338"
  sidebar-active: "#2a3e5c"
  table-rule: "#e8edf4"
  sidebar-ink: "#edf2fc"
  sidebar-muted: "#b0bdd0"
  sidebar-rule: "#34455d"
  balance-ground: "#203a60"
  balance-ink: "#ffffff"
  balance-muted: "#c2cfe2"
  balance-rule: "#506580"
  balance-explained: "#a9d8cb"
  balance-held: "#7795cb"
  balance-highlight: "#dce8ff"
  status-verified: "oklch(0.55 0.15 150)"
  status-verified-soft: "oklch(0.95 0.05 150)"
  status-verified-fg: "oklch(0.38 0.1 150)"
  status-probable: "oklch(0.72 0.16 78)"
  status-probable-soft: "oklch(0.96 0.07 90)"
  status-probable-fg: "oklch(0.45 0.1 70)"
  status-insufficient: "oklch(0.6 0.01 260)"
  status-insufficient-soft: "oklch(0.95 0.005 260)"
  status-insufficient-fg: "oklch(0.42 0.01 260)"
  status-conflicting: "oklch(0.56 0.21 27)"
  status-conflicting-soft: "oklch(0.95 0.04 27)"
  status-conflicting-fg: "oklch(0.42 0.16 27)"
  status-auto: "oklch(0.55 0.1 245)"
  status-auto-soft: "oklch(0.95 0.03 245)"
  status-auto-fg: "oklch(0.4 0.09 245)"
  edge-supports: "oklch(0.55 0.15 150)"
  edge-contradicts: "oklch(0.56 0.21 27)"
  edge-neutral: "oklch(0.6 0.01 260)"
  node-receipt: "oklch(0.94 0.04 245)"
  node-invoice: "oklch(0.96 0.02 260)"
  node-adjustment: "oklch(0.96 0.06 90)"
  node-evidence: "oklch(0.99 0 0)"
  node-rule: "oklch(0.95 0.04 300)"
typography:
  headline:
    fontFamily: "'Instrument Serif', Georgia, serif"
    fontSize: "48px"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.025em"
  title:
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "17px"
    fontWeight: 550
    letterSpacing: "-0.025em"
  body:
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "14px"
  label:
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "12px"
  financial:
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "clamp(30px, 3.1vw, 46px)"
    fontWeight: 450
    letterSpacing: "-0.035em"
    fontFeature: "tnum"
rounded:
  badge: "4px"
  navigation: "7px"
  control: "6px"
  surface: "12px"
  pill: "9999px"
spacing:
  compact: "8px"
  control: "12px"
  mobile: "16px"
  section: "20px"
  column: "24px"
  page: "40px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.control}"
    height: "37px"
    padding: "0 10px"
  button-outline:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    height: "37px"
    padding: "0 10px"
  button-ghost:
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    height: "37px"
    padding: "0 10px"
  input-search:
    textColor: "{colors.foreground}"
    rounded: "{rounded.control}"
    height: "36px"
    padding: "4px 10px 4px 33px"
  navigation-active:
    backgroundColor: "{colors.sidebar-active}"
    textColor: "{colors.sidebar-ink}"
    rounded: "{rounded.navigation}"
    padding: "13px 12px"
  chip-verified:
    backgroundColor: "{colors.status-verified-soft}"
    textColor: "{colors.status-verified-fg}"
    rounded: "{rounded.pill}"
    padding: "1px 7px"
  work-section:
    backgroundColor: "{colors.card}"
    textColor: "{colors.card-foreground}"
    rounded: "{rounded.surface}"
    padding: "24px"
  balance-panel:
    backgroundColor: "{colors.balance-ground}"
    textColor: "{colors.balance-ink}"
    rounded: "{rounded.surface}"
    padding: "25px 28px 19px"
---

# Design System: Artemis

## Overview

**Creative North Star: "The Annual Report"**

Artemis takes its hierarchy from an annual report: deep ink navigation frames a cool paper canvas, cobalt marks actions, and expressive serif titles distinguish interpretation from the figures beneath them. The composition is asymmetric and deliberate, with white working surfaces and quiet rules.

Instrument Serif supplies the editorial voice; Geist keeps records and numbers precise. A navy reconciliation panel turns actual explained and held paise into a split variance bridge. Data is the visual material, and semantic statuses retain their established meanings.

**Key Characteristics:**

- Deep navy navigation and cobalt actions.
- Self-hosted Instrument Serif headings with Geist body and figures.
- Live variance bridge beside an asymmetric white outcome index.
- Cool paper, generous surface corners and quiet table rules.

The final visual cascade is tokens.css, workspace.css, then editorial.css; editorial.css governs where it overrides the structural base.

## Colors

### Primary

- **Reporting Cobalt** (primary, brand-ink): primary actions, operational accents and the receipt opening affordance.
- **Deep Navigation Ink** (sidebar-ground): persistent navigation, with sidebar-ink and sidebar-muted providing the correct light text hierarchy.
- **Reconciliation Navy** (balance-ground): the financial overview, paired with balance-ink, balance-muted and balance-rule.

### Neutral

- **Cool Paper** (background): the canvas outside working surfaces.
- **White Record** (card, popover): queue, outcome index, evidence and temporary controls.
- **Financial Ink** (foreground): body text and figures.
- **Slate Metadata** (muted-foreground): quiet labels and secondary information.
- **Cool Rules** (border, input, table-rule): fields, separators and record structure.

### Semantic accents

- **Explained Mint** (balance-explained): the actual explained share of the variance bridge and sidebar workflow endpoint.
- **Held Periwinkle** (balance-held): the actual held share of that bridge.
- Status, edge and node palettes retain their dedicated source tokens. The bridge palette does not redefine outcome semantics.

**The Status Meaning Rule.** Verified is green, Probable amber, Insufficient grey, Conflicting red and Auto-closed blue. Preserve explicit status text; color supplements the label.

Frontmatter records the light-theme primitives. Dark overrides in tokens.css remain authoritative; sidebar and balance tokens without overrides retain their root values. Preview ramps in the sidecar are synthesized display aids, not extra implementation tokens.

## Typography

**Display Font:** Instrument Serif, Georgia, serif fallback, self-hosted regular and italic through @fontsource/instrument-serif.
**Body Font:** Geist Variable, self-hosted through @fontsource-variable/geist, sans-serif fallback.
**Label/Mono Font:** Geist labels and tabular figures; system monospace for identifiers, hashes and tool traces.

**Character:** Editorial hierarchy above precise operational data. Regular serif titles add character without enlarging the data typography.

### Hierarchy

- **Headline:** the frontmatter headline role; page titles step to (43px) on mobile.
- **Case heading:** Instrument Serif (36px, 400, 1.15), becoming (32px) on mobile.
- **Balance heading:** Instrument Serif (26px, 400, 1); compact desktop uses (23px), small phones (24px).
- **Sidebar statement:** Instrument Serif (34px, 400, 1.08) with tracking (-0.015em).
- **Section title:** Geist (17px, 550) with tracking (-0.025em).
- **Body:** Geist (14px); receipt rows and customer names (13px).
- **Label:** secondary metadata and table headers generally (11px), control and status labels generally (12px).
- **Financial:** the frontmatter financial role, with tabular numerals; overview breakdown uses (21–28px).

**The Two Voices Rule.** Use Instrument Serif for editorial headings and the sidebar statement; keep records, controls and financial figures in Geist.

## Layout

The desktop navigation column is (246px); the white breadcrumb bar is (66px). Main content is capped at (1600px), with padding (32px 40px 40px). The dashboard uses (22px) between sections. Its overview has a navy financial panel and white outcome index in a (1.65fr / 1fr) grid with a (260px) minimum index width. At (1200px), navigation narrows to (212px), main padding becomes (28px 26px 36px), and the overview uses (1.5fr / 1fr) with (16px) gaps.

At (1000px), overview panels stack and outcomes become five compact columns. At (760px), the navigation is a toggleable drawer up to (300px) wide; the sticky topbar is (57px), and main padding is (27px 18px). At (440px), outcomes use three columns; the financial breakdown remains two columns with smaller figures.

The base preserves the queue's sticky table header and (460px) maximum scrolling region. At (1000px) and below, receipt cards replace the desktop queue table in a vertical scrolling region capped at (530px), keeping customer, both amounts, outcome and review state together. The toolbar becomes a grid: the agent description spans the first row, with mode, Run batch and Reset grouped on the second row. The audit table retains its (580px) scrolling region. Case detail keeps the flexible evidence column plus review aside and becomes one column below (950px), placing the first two main blocks before review and remaining evidence after it.

**The Data Is Material Rule.** Draw the variance bridge from actual explained and held paise. Global overview totals remain stable when the queue is filtered.

## Elevation & Depth

The final surfaces are flat, with rounded white records on cool paper and a solid navy overview. Work sections have no resting shadow or outer border. Table rules remain quiet, while the review aside retains an input-colored border. Temporary mobile navigation and inherited select popups retain functional elevation.

**The Flat Record Rule.** Separate records with surface tone and quiet rules; reserve shadows for temporary overlapping controls.

## Shapes

The repeated working surface has (12px) corners. Toolbar buttons, selects, queue search and closure result use (6px) corners; navigation uses (7px). Outcome rows have (5px) corners, and the bridge's segments use (2px) corners with a (4px) gap. Pills remain fully rounded. Evidence tiers preserve solid, dashed and dotted borders for primary, supporting and derived evidence.

## Components

### Buttons

Cobalt Run batch is the primary action. Toolbar buttons are (37px) high with (6px) corners. The inherited outline, ghost and destructive variants retain their semantic behavior. Shared color transitions remain (160ms ease); enabled buttons move down (1px) while pressed, and outcome filters opt out.

### Chips

Outcome pills retain soft semantic fills, strong readable text and a (5px) dot. Their effective label is (12px, 500) with (18px) line height. Review badges use small rectangular corners. Color always appears with a written state.

### Cards / Containers

Work sections have the surface radius, card fill and (24px) padding; mobile reduces this to (20px), then (18px 16px) on small phones. The outcome index is a white companion surface. The navy overview uses its own balance palette and (25px 28px 19px) desktop padding.

### Inputs / Fields

Queue search is (36px) high with a cool paper fill and control radius. Queue filters are white, (36px) high and use (11px) labels. The toolbar is a transparent rule-separated row rather than a card. Shared focus uses a (2px) ring with (3px) offset; inherited field and button focus/invalid treatments remain.

### Navigation

Navy navigation has light labels, muted metadata and a lighter active row. The serif sidebar statement is followed by a receipt–evidence–decision chain. Hover and active states use sidebar-specific tokens to preserve contrast. Mobile retains the same hierarchy in a drawer.

### Reconciliation Overview

The panel presents the global total, an explained/held split bridge, actual breakdown amounts and a clarifying caption. The track is (10px) high. Segment width follows actual paise proportions, with a neutral empty state; widths transition over (300ms) using cubic-bezier(.16,1,.3,1). The white outcome index uses semantic dots, text and right-aligned counts on desktop; selected rows have a thin outline, without the former underline. Narrow layouts turn outcomes into compact tiles.

### Receipt Queue

Quiet shaded headers, aligned money columns and lighter rules prioritize scanning. Customer labels use (13px, 550); identifiers and metadata use (11px). Tablet and mobile receipt cards preserve customer, receipt, variance and state together from (1000px) down. Review and audit inherit serif headings and the ink/cobalt palette.

### Evidence Graph

The graph has an open-by-default text version. Each relationship resolves its source and target from graph-node labels, making the explanation readable without internal IDs where nodes are available. At (760px) and below, the text relationships move above the visual graph; their (1.6) line height, wrapping and (8px) vertical spacing support inspection at entry.

Reduced motion preserves the base override: animation and transition durations become (.01ms), with auto scrolling.

## Do's and Don'ts

### Do:

- Do use shared semantic colors from web/src/design/tokens.css and final visual rules from web/src/design/editorial.css.
- Do keep global financial totals independent of queue filters.
- Do align financial figures and preserve explicit status labels.
- Do preserve integer paise and format amounts only through web/src/lib/format.ts.
- Do explicitly label synthetic data and synthetic benchmark results.
- Do preserve policy limits, reviewer identity, required comments, reset confirmation and status meanings.
- Do support keyboard focus, reduced motion and mobile receipt inspection.

### Don't:

- Don't replace Instrument Serif headings with generic sans-serif titles.
- Don't reintroduce the superseded achromatic olive identity.
- Don't invent performance figures or substitute a decorative split for actual paise data.
- Don't make Probable amber read as a red error.
- Don't add remote font dependencies or shipping raster imagery.
- Don't imply configured tax rules are tax advice or synthetic accuracy is production accuracy.
