# Chapter 6: Bootstrap UI — The Biopunk Skin

## Why Bootstrap 5 with Dark Mode?

A flipdot display is inherently physical — black steel dots clicking against a
yellow-green background, driven by electromagnetic pulses. The web interface
that controls it should feel like it belongs in the same room. Not a clean SaaS
dashboard. Not Material Design. Something that looks like it was pulled from a
CRT terminal in a biology lab that never got decommissioned.

Bootstrap 5 gives us responsive layout, accessible components, and a solid grid
system without writing any of that ourselves. Its `data-bs-theme="dark"` attribute
flips every component to dark mode in one attribute. We don't fight the framework —
we let it handle the structural work, then override the skin.

```html
<html lang="en" data-bs-theme="dark">
```

One attribute. Every Bootstrap component — cards, tables, alerts, navbars —
instantly renders with dark backgrounds and light text. This is our starting
point, not our finish line.

## CSS Custom Properties: The Biopunk Palette

We define four custom properties on `:root` and use them everywhere:

```css
:root {
  --bio-green: #00ff41;    /* Phosphor green — the primary accent */
  --bio-dim: #00cc33;      /* Slightly muted — for hover states */
  --bio-bg: #0a0a0a;       /* Near-black — darker than Bootstrap's dark */
  --bio-card: #111;        /* Card surfaces — just barely visible */
}
```

Why custom properties instead of overriding Bootstrap's Sass variables? Because
we're loading Bootstrap from a CDN, not compiling it. Custom properties let us
theme on top of the pre-built CSS without a build step. No Node.js, no Webpack,
no `npm run build`. Just a `<link>` tag and a `<style>` block. For a project
running on a Raspberry Pi, that simplicity matters.

The colors are deliberate. `#00ff41` is the classic phosphor green from VT100
terminals. `#0a0a0a` is darker than Bootstrap's default dark theme (`#212529`),
pushing the contrast closer to a real terminal. The cards at `#111` sit just
above the background — visible but not distracting.

## Courier New: The Right Wrong Font

```css
body { font-family: 'Courier New', monospace; }
```

Courier New is not a beautiful font. That's the point. It signals "this is a
tool, not a product." Monospace type makes the interface feel like a terminal
session, which is honest — you are literally typing commands for hardware. Every
form input inherits it via `font-family: inherit`, so text looks the same in the
input field as it will on the display.

## Template Inheritance: base.html as the Shell

Flask's Jinja2 templates use block-based inheritance. `base.html` defines the
page skeleton — `<head>`, navbar, flash messages, footer — and punches a hole
with `{% block content %}`. Every page template fills that hole:

```html
<!-- base.html -->
<div class="container">
  {% block content %}{% endblock %}
</div>

<!-- index.html -->
{% extends "base.html" %}
{% block content %}
  <!-- dashboard goes here -->
{% endblock %}
```

The flash message rendering in `base.html` maps categories to Bootstrap alert
classes with a conditional chain. The dismissible button uses Bootstrap's
JavaScript — the only JS we load. No custom scripts for the base UI.

## The Dashboard Grid

The index page splits into two equal columns on large screens and stacks
vertically on small ones:

```html
<div class="row g-4">
  <div class="col-lg-6"><!-- Send Message form --></div>
  <div class="col-lg-6"><!-- Recent Messages table --></div>
</div>
```

`col-lg-6` means: take 6 of 12 columns (half width) at the `lg` breakpoint
(992px+). Below that, each column goes full-width. Both columns wrap their
content in `.card.p-4`, giving them the dark `--bio-card` background. Cards
inside a grid is a pattern that scales — when we add voice status, webcam feed,
or queue depth panels later, they slot into the same grid.

## Custom Button Classes

Bootstrap's built-in `.btn-success` is green, but the *wrong* green:

```css
.btn-bio {
  background: var(--bio-green);
  color: #000;
  font-weight: bold;
  border: none;
}
.btn-outline-bio {
  color: var(--bio-green);
  border-color: var(--bio-green);
  background: transparent;
}
```

`btn-bio` is the primary action — solid green, black text. The "Send" button.
`btn-outline-bio` is secondary — ghost style, used for "Clear Display." The
naming follows Bootstrap's convention (`btn-*`, `btn-outline-*`) so any
developer familiar with the framework knows what they do.

## The Navbar and Queue Badge

```html
<nav class="navbar navbar-dark mb-4">
  <a class="navbar-brand" href="/">&#9632; BIOPUNK FLIPDOT</a>
  <span class="navbar-text small" id="queue-badge"></span>
</nav>
```

The `#queue-badge` span is a placeholder. Once the API is wired up (Chapter 11),
a small JavaScript fetch will poll `/api/display/status` and update the badge
with the current queue depth. The brand uses `&#9632;` (a solid square) as a
visual nod to the flipdot's physical dots.

## What's Next

Chapter 7 connects the Blue Yeti microphone and Vosk speech recognition — the
first hardware input beyond the keyboard.
