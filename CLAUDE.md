# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## How to run

Open `Sales App.dc.html` directly in a browser (double-click, or serve with any static file server). The file is self-contained — `support.js` bootstraps React 18 from unpkg and mounts the component. No build step required.

For local serving (recommended, avoids file:// CORS issues with image-slot.js):
```
npx serve .
# or
python -m http.server 8080
```

## Architecture

This is a **Claude Design** prototype — a single-file component system where HTML template and JavaScript logic live together in `Sales App.dc.html`.

### Runtime (`support.js`)
- Generated/compiled Claude Design runtime — do not edit
- Loads React 18 from unpkg, provides `DCLogic` base class
- Template directives: `<sc-if value="{{expr}}">`, `<sc-for list="{{arr}}" as="item">`, `<x-import>` for external components
- `{{expr}}` interpolation binds template to values returned from `renderVals()`

### Main component (`Sales App.dc.html`)
The `<script type="text/x-dc" data-dc-script>` block contains a `class Component extends DCLogic` with:
- `state` — reactive state object (mutate via `this.setState(...)`)
- `renderVals()` — returns flat object of all values the template can reference
- Event handlers as class arrow functions

**Two top-level modes**, toggled by `state.mode`:
- `staff` — mobile phone mockup (412px wide), screens: `scan → login → form → history → historyDetail`
- `admin` — full-width desktop dashboard with date filter, summary cards, bar chart, and 3 table views (list / by employee / by store)

The admin top-bar toggle button is gated on `isAdminUser`. The login role-simulation panel is gated on `isDev` (auto-detected from `localhost`/`127.0.0.1`/empty hostname, or override `DEV_MODE` manually).

### External components
- **`image-slot.js`** — custom element `<image-slot>` for evidence photo upload. Persists drops to `.image-slots.state.json` sidecar. Used in the form screen via `<x-import component-from-global-scope="image-slot" from="./image-slot.js">`.
- **`android-frame.jsx`** — Android device frame components (not currently imported by the app).

### Mock data
All data lives in `state.allHistory` and `state.submissionsToday` arrays inside the component. `renderVals()` derives `adminFiltered`, `groupedByEmployee`, `groupedByStore`, `filteredHistory`, etc. from those arrays at render time. No backend yet.

## Key patterns

- To conditionally show UI: `<sc-if value="{{boolVal}}">...</sc-if>` where `boolVal` comes from `renderVals()`
- To iterate: `<sc-for list="{{arr}}" as="item" hint-placeholder-count="N">` — `hint-placeholder-count` controls skeleton count during streaming
- Inline styles are CSS strings resolved from `renderVals()` (e.g. `style="{{periodStyle}}"` where `periodStyle` is a full CSS string)
- Modals use `scrollY` state + `position:absolute; top:${scrollY}px` workaround because `position:fixed` doesn't compose with scrollable containers in this setup

## DEV_MODE

`DEV_MODE` is a class property auto-set from `location.hostname`. To force it on/off, change the line in the class:
```js
DEV_MODE = true;  // always show dev tools
DEV_MODE = false; // always hide dev tools
```
