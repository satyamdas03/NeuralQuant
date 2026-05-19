---
name: Obsidian Quantum V2
colors:
  surface: '#10131c'
  surface-dim: '#10131c'
  surface-bright: '#353943'
  surface-container-lowest: '#0a0e16'
  surface-container-low: '#181c24'
  surface-container: '#1c2028'
  surface-container-high: '#262a33'
  surface-container-highest: '#31353e'
  on-surface: '#e0e2ee'
  on-surface-variant: '#b9cbbe'
  inverse-surface: '#e0e2ee'
  inverse-on-surface: '#2d303a'
  outline: '#83958a'
  outline-variant: '#3a4a41'
  surface-tint: '#00e29d'
  primary: '#f7fff8'
  on-primary: '#003824'
  primary-container: '#00ffb2'
  on-primary-container: '#00724d'
  inverse-primary: '#006c49'
  secondary: '#c1c1ff'
  on-secondary: '#1500a8'
  secondary-container: '#2e25d4'
  on-secondary-container: '#b1b1ff'
  tertiary: '#fffcff'
  on-tertiary: '#3f2e00'
  tertiary-container: '#ffdc91'
  on-tertiary-container: '#7d5e00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#47ffb8'
  primary-fixed-dim: '#00e29d'
  on-primary-fixed: '#002113'
  on-primary-fixed-variant: '#005236'
  secondary-fixed: '#e1dfff'
  secondary-fixed-dim: '#c1c1ff'
  on-secondary-fixed: '#09006b'
  on-secondary-fixed-variant: '#2b20d2'
  tertiary-fixed: '#ffdf9b'
  tertiary-fixed-dim: '#edc157'
  on-tertiary-fixed: '#251a00'
  on-tertiary-fixed-variant: '#5b4300'
  background: '#10131c'
  on-background: '#e0e2ee'
  surface-variant: '#31353e'
  cyber-red: '#FF4158'
  surface-deep: '#090E1A'
  panel-glass: rgba(13, 20, 37, 0.7)
  border-glow: rgba(0, 255, 178, 0.15)
  text-primary: '#E8F4FF'
  text-muted: rgba(232, 244, 255, 0.45)
typography:
  headline-xl:
    fontFamily: Syne
    fontSize: 96px
    fontWeight: '800'
    lineHeight: '1.1'
    letterSpacing: -0.04em
  headline-lg:
    fontFamily: Syne
    fontSize: 64px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Syne
    fontSize: 40px
    fontWeight: '700'
    lineHeight: '1.2'
  body-lg:
    fontFamily: Syne
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Syne
    fontSize: 15px
    fontWeight: '400'
    lineHeight: '1.5'
  data-lg:
    fontFamily: Space Mono
    fontSize: 24px
    fontWeight: '700'
    lineHeight: '1.2'
    letterSpacing: 0.05em
  data-sm:
    fontFamily: Space Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.4'
    letterSpacing: 0.1em
  label-caps:
    fontFamily: Space Mono
    fontSize: 11px
    fontWeight: '700'
    lineHeight: '1.0'
    letterSpacing: 0.2em
spacing:
  grid-unit: 60px
  gutter: 1.5rem
  margin-mobile: 1rem
  margin-desktop: 4rem
  container-max: 1400px
---

## Brand & Style

The design system embodies **Cyber-Financial Minimalism**, a style that merges institutional authority with high-velocity quantitative research. It is designed for elite financial analysts and algorithmic traders who demand precision and sophisticated data visualization.

The aesthetic is heavily influenced by **High-Tech Brutalism** and **Glassmorphism**. It utilizes a "System HUD" (Heads-Up Display) approach, featuring ultra-sharp edges, high-contrast neon accents against a void-like obsidian background, and technical overlays like scanlines and 60px coordinate grids. The emotional response is one of absolute technical superiority, research-driven confidence, and "bleeding-edge" innovation.

## Colors

The palette is anchored in **Deep Dark Obsidian**, providing a high-contrast stage for functional color signals. 

- **Sharp Emerald (#00FFB2)**: Used for primary actions, success states, and active data nodes. It represents growth and algorithmic "Alpha."
- **Deep Matte Indigo (#5D5CFF)**: A sophisticated anchor for secondary UI elements, providing depth to the glassmorphic layers.
- **Gold & Cyber Red**: Reserved strictly for semantic signaling—Gold for warnings or signal transitions, and Cyber Red for negative market movements or critical system errors.

The interface relies on varying levels of transparency rather than flat tints to maintain its "glass" quality.

## Typography

Typography is used as a structural element. 
- **Syne** provides a modern, geometric feel for headlines and narrative body text, suggesting an editorial high-fashion influence within a technical space. 
- **Space Mono** is the "Institutional" font, used for all quantitative data, tables, labels, and status messages. Its fixed-width nature ensures that columns of numbers remain perfectly aligned, essential for professional trading environments.

All technical labels (`label-caps`) should be rendered in uppercase with wide letter-spacing to mimic terminal readouts.

## Layout & Spacing

This design system uses a **Fixed Grid Strategy** with a visual 60px background grid overlay. 

- **Desktop**: 12-column grid with 24px gutters. Sections are heavily padded (8rem) to create focus and an expansive, premium feel.
- **Responsive**: On mobile, the grid collapses to a single column with 16px margins. High-density data tables should transition to horizontally scrollable "Data Cards."
- **Institutional Shell**: The navigation is a fixed, blurred top-bar with a strictly defined height of 80px, housing the global ticker and research access points.

## Elevation & Depth

Depth is conveyed through **Luminous Layering** rather than traditional drop shadows.

1.  **Background**: Solid Obsidian (#050810) with a faint 60px grid and scanline overlay (0.03 opacity).
2.  **Panels**: Glassmorphic surfaces with `backdrop-filter: blur(20px)` and a `1px` border of `rgba(0, 255, 178, 0.15)`.
3.  **Active Elements**: Interactive nodes use an **Ambient Glow** (e.g., `box-shadow: 0 0 20px rgba(0, 255, 178, 0.3)`) to suggest they are light-emitting rather than physical objects.
4.  **Transitions**: Use "Reveal" animations where panels clip-mask from center-out or slide-up with a 0.7s ease-out to mimic a sophisticated system boot-up.

## Shapes

The shape language is **Strictly Brutalist**. All buttons, cards, input fields, and research panels must have **0px border-radius**. Sharp corners communicate precision, mathematical accuracy, and an institutional "no-frills" attitude.

The only exceptions are functional "nodes" (data points on charts) and status indicators (Live dots), which should be perfectly circular (50% radius) to differentiate live data from structural UI.

## Components

### Research Panels
Glassmorphic containers with a top-weighted 2px accent border in a Sharp Emerald gradient. These panels should use a staggered "reveal" animation on load.

### Quantitative Tables
Utilize `Space Mono` for all cell data. Headers must be `label-caps`. Row hover states should utilize a subtle background highlight of `rgba(0, 255, 178, 0.05)` and a sharp vertical left-accent.

### Data Visualization
- **Mini-charts**: Line graphs using the Sharp Emerald color with a semi-transparent area fill.
- **Composite Indices**: Circular gauges or radial bars using the Emerald-to-Indigo gradient.

### Buttons
- **Primary**: Solid Sharp Emerald background with black `Space Mono` text. No rounded corners.
- **Ghost**: `1px` solid `rgba(232, 244, 255, 0.2)` border with `text-primary`.
- **Interactive Nodes**: Hovering over a button should trigger a localized scanline pulse.

### Navigation Shell
A high-density top bar containing a live market ticker. The ticker items are separated by `1px` vertical lines in `border-glow` and use `Space Mono` exclusively.