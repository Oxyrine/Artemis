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
  document: "0px"
  floating: "12px"
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
  status-verified:
    textColor: "{colors.status-verified-fg}"
    padding: "0"
  work-section:
    textColor: "{colors.foreground}"
    rounded: "{rounded.document}"
    padding: "26px 0 0"
  balance-panel:
    textColor: "{colors.foreground}"
    rounded: "{rounded.document}"
    padding: "0"
---

# Design System: Artemis

## Overview

**Creative North Star: "The Annual Report"**

Artemis uses the hierarchy of an annual report: deep ink navigation, a cool paper canvas, cobalt actions, Instrument Serif headings and precise Geist figures. Open document sections, whitespace and thin rules carry the composition.

Receipts, variance closure and evidence share the page without repeated card containers. The variance bridge uses actual explained and held paise; meaningful status and provenance appear as plain text. Enclosed surfaces are reserved for controls and interactions that require containment.

**Key Characteristics:**

- Open document sections and column separators.
- Deep navy navigation, cobalt actions and cool paper.
- Self-hosted Instrument Serif titles with Geist records and tabular figures.
- Actual variance proportions and plain-language review evidence.

The final visual rules live in web/src/design/editorial.css and guide.css, over the structural workspace.css base. Shared colors remain in tokens.css. Frontmatter records root color tokens; local overrides described below govern the open overview. Dark token overrides remain authoritative.

## Colors

### Primary

- **Reporting Cobalt** (primary, brand-ink): actions, operational accents and the held variance share.
- **Deep Navigation Ink** (sidebar-ground): sidebar ground with light sidebar-ink and sidebar-muted text.

### Neutral

- **Cool Paper** (background): continuous document canvas.
- **Financial Ink** (foreground): headings, figures and overview values.
- **Slate Metadata** (muted-foreground): provenance, mode and supporting labels.
- **Quiet Rules** (border, table-rule): top rules, column separators and record rows.
- **Control White** (card, popover): fields, topbar, guide and temporary controls; not repeated work-section fills.

The open balance section locally maps balance-ink to foreground, balance-muted to muted-foreground, balance-rule to border, balance-explained to status-verified and balance-held to primary. Root balance colors remain available in source; they no longer give the overview a navy card fill. The worked example similarly maps its balance colors to ordinary document text and rules.

**The Status Meaning Rule.** Verified is green, Probable amber, Insufficient grey, Conflicting red and Auto-closed blue. Keep written states; color supplements text.

## Typography

**Display Font:** self-hosted Instrument Serif regular and italic, Georgia/serif fallback.
**Body Font:** self-hosted Geist Variable, sans-serif fallback.
**Label/Mono Font:** Geist metadata; system monospace identifiers, hashes and traces.

Page headings use the frontmatter headline role (48px), becoming (43px) on mobile. Case headings use (36px), then (32px). Balance headings use (26px); section headings use Geist (17px, 550). Body text is (14px), table records (13px), and metadata generally (11–12px). Financial values use tabular numerals, with overview totals sized by the frontmatter financial role. The welcome heading uses Instrument Serif at clamp(28px, 3.1vw, 40px).

**The Two Voices Rule.** Use Instrument Serif for editorial headings and Geist for records, controls and financial figures.

## Layout

Desktop has a (246px) navy sidebar, (66px) breadcrumb bar and main content capped at (1600px), with (32px 40px 40px) padding. At (1200px), navigation narrows to (212px), with (26px) main horizontal gutters. The scope strip and environment label are absent.

The overview uses (1.65fr / 1fr) columns. Its outcome index has a left rule and (30px) left padding, reduced to (22px) on compact desktop. At (1000px), overview sections stack, the separator becomes a top rule, and outcomes use five columns. At (440px), outcomes use three columns. The overview itself has zero container padding.

At (1000px), receipt rows replace the desktop queue table, keeping customer, both amounts, outcome and review state together in a vertical region capped at (530px). The toolbar description spans its first grid row; mode, Run batch and Reset share the second. Desktop queue and audit scrolling regions retain (460px) and (580px) maximum heights respectively.

Case evidence and review use two columns until (950px); the review aside's left rule becomes a top rule when stacked. At (760px), navigation becomes a drawer up to (300px) wide, the sticky topbar is (57px), and main horizontal gutters become (18px). Sidebar content scrolls; its statement gives way on phones and short screens.

Welcome text and its worked example use open columns, with a left rule before the example. At (860px), they stack with a top rule. Comparison uses three open columns with separators, becoming stacked ruled sections at (1100px).

**The Data Is Material Rule.** Draw the variance bridge from actual explained and held paise. Keep global totals independent of queue filters.

## Elevation & Depth

Work, balance, outcome, welcome, comparison and review sections are transparent and unrounded. Thin top or column rules establish hierarchy. Closure and integrity explanations remain in the document flow. Containment remains for graph navigation, floating guide, forms, confirmation dialogs and error feedback. Temporary overlays retain functional shadow.

**The Open Document Rule.** Use whitespace, top rules and column separators for working sections. Do not wrap each region in a rounded card.

## Shapes

Document sections have zero corner radius. Controls retain (6px) corners and navigation (7px). Outcome filter hit areas retain small (5px) corners for selected/hover feedback; they are controls, not containers. Bridge segments use (2px) corners and a (4px) gap. The floating guide retains (12px) corners, and the evidence graph viewport keeps its border and rounded edge. Evidence tiers retain solid, dashed and dotted borders.

## Components

### Buttons

Cobalt Run batch remains primary. Toolbar buttons are (37px) high with (6px) corners. Shared color transitions use (160ms ease), with a (1px) press displacement; outcome filters opt out.

### Status and Provenance

Queue statuses are plain text in the established semantic foregrounds, without pill fill, border or leading dot. Review state and mode use muted plain text. Narrative provenance is textual. Case-header status/state/mode badges are absent. Evidence-tier markers retain their meaningful border distinctions.

### Sections / Containers

Work sections begin with a one-pixel top rule and padding (26px 0 0), becoming (24px 0 0) on phones. They have no fill, enclosing border or corner radius. Desktop review uses a left separator and (24px) inset; stacked review uses a top rule. Welcome, worked example and comparison use the same open document grammar.

### Inputs / Fields

Queue search and filters remain (36px) high with control corners. Fields retain borders and focus/invalid states because their interaction needs containment. Shared keyboard focus has a (2px) outline and (3px) offset.

### Navigation

Navy sidebar destinations use light text and a lighter active fill. The Receivables workspace / INR scope strip is removed. The topbar contains breadcrumbs without a Synthetic environment tag. Synthetic disclosure remains in the footer.

### Variance Overview and Outcomes

The open overview presents global total, explained/held bridge, actual breakdown and caption. The track is (10px) high, with widths calculated from actual paise and a neutral empty state. Width transitions use (300ms) cubic-bezier(.16,1,.3,1). The adjacent transparent outcome index retains semantic dots, text and counts; selection uses a thin outline on the control.

### Evidence Graph and Guide

The evidence viewport remains enclosed. Its text version is open by default and resolves relationships from node labels. At (760px), readable text relationships move above the graph. The floating guide remains a contained, scrollable overlay up to (360px) wide, with a border and functional shadow; it does not establish a card pattern for page content.

Reduced motion shortens animation/transition durations to (.01ms) and uses auto scrolling. No remote font or shipping raster dependency is introduced.

## Do's and Don'ts

### Do:

- Do use open document sections, whitespace and thin rules as the default.
- Do retain containment for the evidence graph viewport, floating guide, form fields and confirmation dialogs.
- Do keep meaningful queue status, review state, mode and narrative provenance as plain text.
- Do retain synthetic-data disclosure in the footer and explicitly label synthetic benchmark results.
- Do keep global financial totals independent of queue filters.
- Do preserve integer paise and format amounts only through web/src/lib/format.ts.
- Do preserve policy limits, named reviewer decisions, required comments, reset confirmation and status meanings.
- Do support keyboard focus, reduced motion and readable tablet/mobile receipt rows.

### Don't:

- Don't repeat rounded card containers across dashboard, welcome, comparison, evidence and review sections.
- Don't add case-header Verified, Pending approval or Demo agent badges.
- Don't restore the Synthetic environment topbar label or Receivables workspace / INR sidebar strip.
- Don't invent figures or turn Probable amber into a red error.
- Don't add remote fonts or shipping raster imagery.
- Don't present configured tax rules as advice or synthetic accuracy as production accuracy.
