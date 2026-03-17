# Chapter 2: Jinja2 Templates — The Biopunk Interface

## The Aesthetic

We're building a hacker lab display controller. The UI should feel like it belongs
in the same room as the flipdot — dark, monospaced, glowing green on black. Think
terminal aesthetics meets physical computing.

## Template Inheritance

Flask uses Jinja2 for templates. The key concept is **inheritance**: a base template
defines the page structure, and child templates fill in the content.

### base.html — The Shell

```html
<html lang="en" data-bs-theme="dark">
<head>
  <title>{% block title %}Biopunk Flipdot{% endblock %}</title>
  <link href="...bootstrap.min.css" rel="stylesheet">
  <style>
    :root {
      --bio-green: #00ff41;
      --bio-bg: #0a0a0a;
    }
    body {
      font-family: 'Courier New', monospace;
      background: var(--bio-bg);
      color: var(--bio-green);
    }
  </style>
</head>
<body>
  <nav class="navbar">...</nav>
  <div class="container">
    {% block content %}{% endblock %}
  </div>
</body>
</html>
```

The CSS custom properties (`--bio-green`, `--bio-bg`) create a consistent theme.
Bootstrap's dark mode (`data-bs-theme="dark"`) handles the heavy lifting, and we
override specific components to get the green-on-black terminal look.

### index.html — The Content

```html
{% extends "base.html" %}

{% block content %}
<div class="row g-4">
  <div class="col-lg-6">
    <!-- Message form -->
  </div>
  <div class="col-lg-6">
    <!-- Recent messages table -->
  </div>
</div>
{% endblock %}
```

`{% extends "base.html" %}` is the magic — this template inherits everything from
the base and only defines what goes inside `{% block content %}`.

## Flash Messages

Flask's `flash()` function stores a message that appears once on the next page load.
We use it for feedback after queueing a message:

```python
flash(f'Queued: "{msg.body}" ({msg.transition})', 'success')
```

The template renders these with Bootstrap alert styling:

```html
{% for category, msg in get_flashed_messages(with_categories=true) %}
  <div class="alert alert-{{ category }}">{{ msg }}</div>
{% endfor %}
```

## Why This Matters

The web interface is the most accessible input to the display. Voice, gesture, and
webcam inputs require specific hardware. The API requires a client. But anyone on
the local network can open a browser and send a message. It's the democratic input
— and for a lab/workshop setting, that's exactly what you want.

## What's Next

Chapter 3 adds Flask-WTF forms with CSRF protection and validation — turning the
raw HTML form into something secure and user-friendly.
