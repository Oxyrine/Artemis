---
name: Artemis
description: A calm operational ledger for evidence-backed reconciliation.
colors:
  background: "#f5f5f2"
  foreground: "#242720"
  card: "#ffffff"
  card-foreground: "#242720"
  popover: "#ffffff"
  popover-foreground: "#242720"
  primary: "#30362b"
  primary-foreground: "#ffffff"
  secondary: "#eeefe9"
  secondary-foreground: "#30362b"
  muted: "#eeefe9"
  muted-foreground: "#666b61"
  accent: "#e8eae3"
  accent-foreground: "#242720"
  border: "#e1e3db"
  input: "#d6d9cf"
  ring: "#737e5b"
  brand-ink: "#63704c"
  sidebar-ground: "#f0f1ec"
  sidebar-active: "#e3e6dc"
  table-rule: "#eceee7"
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
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "28px"
    fontWeight: 550
    lineHeight: 1.25
    letterSpacing: "-0.035em"
  title:
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "14px"
    fontWeight: 550
    letterSpacing: "-0.015em"
  body:
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "14px"
  label:
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "12px"
  financial:
    fontFamily: "'Geist Variable', sans-serif"
    fontSize: "clamp(20px, 2.1vw, 30px)"
    fontWeight: 550
    letterSpacing: "-0.035em"
    fontFeature: "tnum"
rounded:
  badge: "4px"
  navigation: "6px"
  surface: "8px"
  pill: "9999px"
spacing:
  compact: "8px"
  control: "12px"
  mobile: "16px"
  section: "20px"
  column: "24px"
  page: "36px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.primary-foreground}"
    rounded: "{rounded.surface}"
    height: "32px"
    padding: "0 10px"
  button-outline:
    backgroundColor: "{colors.background}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.surface}"
    height: "32px"
    padding: "0 10px"
  button-ghost:
    textColor: "{colors.foreground}"
    rounded: "{rounded.surface}"
    height: "32px"
    padding: "0 10px"
  input-search:
    textColor: "{colors.foreground}"
    rounded: "{rounded.surface}"
    height: "34px"
    padding: "4px 10px 4px 33px"
  navigation-active:
    backgroundColor: "{colors.sidebar-active}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.navigation}"
    padding: "11px 12px"
  chip-verified:
    backgroundColor: "{colors.status-verified-soft}"
    textColor: "{colors.status-verified-fg}"
    rounded: "{rounded.pill}"
    padding: "1px 7px"
  work-section:
    backgroundColor: "{colors.card}"
    textColor: "{colors.card-foreground}"
    rounded: "{rounded.surface}"
    padding: "20px"
---

# Design System: Artemis

## Overview

**Creative North Star: "The Achromatic Ledger"**

The Achromatic Ledger makes dense financial records composed and inspectable. Warm stone grounds, near-black ink and white work surfaces give receipts and evidence a clear hierarchy. Muted olive marks the product identity; outcome colors retain their precise semantic jobs.

This Operate-mode workspace is compact, quiet and direct. Self-hosted Geist, tabular figures and aligned rules carry the interface. Its signature is variance closure beside policy-controlled review, supported by an evidence graph and a separately verifiable audit history.

**Key Characteristics:**

- Warm stone surfaces and near-black ink.
- Compact operational typography with tabular financial figures.
- Flat bordered containers and restrained state transitions.
- Status labels, evidence tiers and visible keyboard focus.

## Colors

The palette is achromatic with warm olive undertones. Stronger chroma conveys outcomes and evidence relationships. Frontmatter records the shipping light-theme primitives; dark overrides remain authoritative in web/src/design/tokens.css.

### Primary

- **Ledger Ink** (primary): compact action buttons and deliberate emphasis.
- **Muted Olive** (brand-ink): Artemis mark, environment dots and text caret. Keyboard focus uses the dedicated ring token.

### Neutral

- **Warm Stone** (background): the workspace ground.
- **White Paper** (card, popover): records and supporting controls.
- **Near-black Ink** (foreground): headings, values and primary text.
- **Quiet Stone Ink** (muted-foreground): metadata and supporting labels.
- **Stone Rules** (border, table-rule, input): structure, row dividers and field edges.
- **Sidebar Stone** (sidebar-ground, sidebar-active): navigation ground and selected destinations.

### Named Rules

**The Status Meaning Rule.** Verified is green, Probable amber, Insufficient grey, Conflicting red and Auto-closed blue. Preserve explicit status text; color supplements the label.

Dedicated edge tokens encode supports, contradicts and neutral. Dedicated node tokens distinguish receipts, invoices, adjustments, evidence and rules.

## Typography

**Display Font:** Geist Variable, sans-serif fallback; no separate display face ships.
**Body Font:** Geist Variable, self-hosted through @fontsource-variable/geist.
**Label/Mono Font:** Geist for labels; the existing system monospace utility for UTRs, evidence IDs, hashes and tool traces.

**Character:** Economical, legible and restrained, with moderate weights and tight heading tracking. Tabular numerals support comparisons.

### Hierarchy

- **Headline:** the frontmatter headline role; mobile page titles step down to (25px).
- **Title:** the frontmatter title role for section headings; toolbar headings use (13px, 550).
- **Body:** the frontmatter body role; receipt tables use (13px).
- **Label:** the frontmatter label role for metadata, navigation groups and table headers.
- **Financial:** the frontmatter financial role; mobile summary values use (21px), then (22px) in stacked rows.

**The Financial Figure Rule.** Use tabular figures for money and sequence values. Keep identifier monospace separate from amount presentation.

## Layout

Desktop uses a fixed navigation column (232px), a breadcrumb bar (64px) and a centered main container capped at (1640px). Main padding is (32px 36px 40px), increasing horizontally to (48px) above (1600px). At (1200px) and below, navigation narrows to (210px), page gutters become (24px), and the case-review aside narrows from (330px) to (290px).

Case detail pairs a flexible evidence column and review aside with a (24px) gap. At (950px) it becomes one column: the first two evidence/closure blocks precede review, and remaining evidence follows it. At (760px), navigation becomes a toggleable drawer, the topbar becomes sticky and (57px) tall, and page gutters become (16px).

The desktop queue is a financial schedule with sticky headers and a scrolling region capped at (460px). At (600px), receipt cards replace the queue table: identity, two aligned amount fields, then outcome and review state. At (440px), summary values stack into rows and outcome filters wrap into three columns. The audit table retains its own scrolling region capped at (580px).

## Elevation & Depth

Record surfaces are flat at rest, separated by tone and one-pixel rules. There are no decorative card shadows. Temporary overlays retain functional elevation: the mobile drawer uses the exact shadow recorded in the sidecar, while select popups, tabs and focus utilities retain their existing component-library treatments.

**The Flat Record Rule.** Use borders and tonal separation for records; reserve lift for overlapping controls and navigation.

## Shapes

Rectangular records have restrained corners: surfaces and toolbars use the surface radius, navigation uses the navigation radius, and review badges use the badge radius. Outcome pills are fully rounded and include a small dot. Evidence tiers use solid primary, dashed supporting and dotted derived borders so their distinctions survive without color.

## Components

### Buttons

Compact, deliberate controls. Primary uses Ledger Ink and its paired foreground; outline uses the ground with a border; ghost gains a muted surface on hover. Default size is (32px) high with (10px) horizontal padding. Primary hover reduces fill to (80%) opacity. Buttons move down (1px) while pressed; outcome tiles remain stationary. Shared color transitions are (160ms ease). Disabled controls retain library behavior.

### Chips

Outcome pills pair soft semantic fills with stronger semantic text, a (5px) dot and explicit status text. The workspace label is (12px, 500), with (18px) line height. None has a transparent fill and border. Review badges have rectangular corners.

### Cards / Containers

White Paper work sections use a one-pixel Stone Rule border, the surface radius and section padding. Mobile sections use mobile padding. The financial summary is one divided schedule; outcome filters share one bordered strip.

### Inputs / Fields

Queue search has a transparent fill, input border, the surface radius, an inline icon and a (34px) height. Shared keyboard focus has a visible (2px) ring with (3px) offset; field/button primitives retain their own focus and invalid treatments. Keep errors explicit. Reduced-motion preference shortens animation and transition durations to (.01ms) and disables smooth scrolling.

### Navigation

Desktop navigation uses (13px) labels, muted foreground by default, and active stone with stronger ink for selected or hovered destinations. Selection has medium weight and a trailing arrow. Mobile drawer navigation retains the same hierarchy.

### Variance Closure and Receipt Queue

Closure keeps arithmetic result, supporting evidence and policy-controlled review nearby. The queue prioritizes customer, receipt, variance and outcome; mobile cards preserve those fields. Outcome tiles combine a large tabular count, semantic dot and text, plus a bottom ink rule when selected.

## Do's and Don'ts

### Do:

- Do use the shared semantic tokens in web/src/design/tokens.css.
- Do align financial figures and keep status text beside its color.
- Do preserve integer paise and format amounts only through web/src/lib/format.ts.
- Do explicitly label synthetic demo data and synthetic benchmark results.
- Do preserve approval limits, named reviewer decisions, required comments, reset confirmation and status meanings.
- Do support keyboard focus, reduced motion and mobile inspection.

### Don't:

- Don't substitute a brand accent for a semantic outcome color.
- Don't make Probable amber read as a red or salmon error.
- Don't add raster decoration to this asset-free operational world.
- Don't imply configured tax rules are tax advice or synthetic accuracy is production accuracy.
