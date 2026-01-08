---
name: polish
description: Transform functional apps into production-grade, professional software. Covers modern UI design systems, keyboard-first navigation, command palettes, view modes, and polished UX patterns. Use when upgrading an MVP to feel like a real product.
---

# Polish: Production-Grade App Transformation

## Overview

Transform a working prototype into professional, polished software that feels like a real product. This skill covers the patterns and principles that separate hobby projects from production-grade tools.

**Core principle:** Production apps feel *inevitable* - every interaction, shortcut, and visual element feels like it couldn't have been designed any other way.

## When to Use

**Use when:**
- App works but feels like a prototype
- User asks to make something "production-ready" or "professional"
- Need to add power-user features (keyboard shortcuts, command palette)
- UI needs modernization
- App should feel like VS Code, Linear, Raycast, or Finder

## Design System: VS Code/Linear/GitHub Dark

### Color Palette

```css
:root {
  /* Backgrounds - layered depth */
  --bg-primary: #0d1117;      /* Deepest - main canvas */
  --bg-secondary: #161b22;    /* Elevated - cards, headers */
  --bg-tertiary: #21262d;     /* Highest - hover, active states */
  --bg-overlay: rgba(0, 0, 0, 0.8);  /* Modals with blur */

  /* Borders - subtle structure */
  --border: #30363d;          /* Default borders */
  --border-muted: #21262d;    /* Subtle dividers */

  /* Text - clear hierarchy */
  --text-primary: #e6edf3;    /* Main content */
  --text-secondary: #8b949e;  /* Supporting text */
  --text-muted: #6e7681;      /* Disabled, hints */

  /* Accent - blue (interaction) */
  --accent: #58a6ff;          /* Links, focus states */
  --accent-emphasis: #1f6feb; /* Buttons, CTAs */
  --accent-muted: rgba(56, 139, 253, 0.15);  /* Selection bg */

  /* Semantic - status */
  --success: #3fb950;         /* Selected, confirmed */
  --success-muted: rgba(63, 185, 80, 0.15);
  --warning: #d29922;         /* Highlights, matches */
  --danger: #f85149;          /* Errors, destructive */
}
```

### Typography

```css
:root {
  --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace;

  --text-xs: 11px;   /* Labels, counters */
  --text-sm: 12px;   /* Secondary info */
  --text-base: 14px; /* Body text */
  --text-lg: 16px;   /* Headings */
  --text-xl: 18px;   /* Modal titles */
}
```

### Visual Properties

```css
:root {
  /* Sharp, modern corners */
  --radius-sm: 3px;
  --radius-md: 6px;
  --radius-lg: 8px;

  /* Subtle shadows - prefer borders */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 12px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 8px 24px rgba(0, 0, 0, 0.5);

  /* Snappy transitions */
  --transition-fast: 100ms ease;
  --transition-normal: 150ms ease;
}
```

### Design Principles

1. **Borders over shadows** - Use 1px borders for structure, shadows for elevation
2. **Sharp corners** - Max 6-8px radius, not rounded pills
3. **Subtle hover states** - Background change, not transform
4. **Focus rings** - 3px accent-muted box-shadow for keyboard nav
5. **Backdrop blur** - 8-12px blur on overlays for depth

---

## Keyboard-First Navigation

### Mac Finder-Inspired Patterns

| Key | Action | Notes |
|-----|--------|-------|
| `Space` | Quick Look / Preview | Toggle overlay, don't navigate |
| `Enter` | Open / Confirm | Full detail view |
| `Tab` | Toggle selection + advance | fzf-style multi-select |
| `Shift+Tab` | Toggle selection + go back | |
| `←→↑↓` | Navigate | Context-aware (grid vs list vs preview) |
| `Escape` | Close / Back / Clear | Layered: modal → view → selection → search |
| `/` | Focus search | Universal pattern |

### Meta Key Shortcuts

| Key | Action |
|-----|--------|
| `⌘⇧P` | Command palette |
| `⌘A` | Select all |
| `⌘D` | Deselect all |
| `⌘,` | Settings |
| `⌘K` | Quick actions (alternative to ⌘⇧P) |

### Implementation Pattern

```typescript
useEffect(() => {
  const handleKeyDown = (e: KeyboardEvent) => {
    // Skip when typing in inputs
    if (e.target instanceof HTMLInputElement) {
      if (e.key === "Escape") (e.target as HTMLInputElement).blur();
      return;
    }

    const isMeta = e.metaKey || e.ctrlKey;

    // Meta shortcuts first (highest priority)
    if (isMeta && e.shiftKey && e.key === "p") {
      e.preventDefault();
      toggleCommandPalette();
      return;
    }

    // Context-aware navigation
    switch (e.key) {
      case " ":
        e.preventDefault();
        if (viewMode === "quicklook") closeQuickLook();
        else openQuickLook();
        break;
      case "Escape":
        // Layered escape behavior
        if (modalOpen) closeModal();
        else if (viewMode !== "grid") setViewMode("grid");
        else if (hasSelection) clearSelection();
        else clearSearch();
        break;
      // ...
    }
  };

  window.addEventListener("keydown", handleKeyDown);
  return () => window.removeEventListener("keydown", handleKeyDown);
}, [dependencies]);
```

---

## Command Palette

### Structure

```typescript
interface Command {
  id: string;
  label: string;
  shortcut?: string;
  category: "view" | "selection" | "navigation" | "actions" | "settings";
  action: () => void;
}
```

### Essential Commands

**View:**
- Switch to [ViewMode]
- Increase/Decrease size
- Toggle panels

**Selection:**
- Select all / Deselect all
- Invert selection
- Select by pattern (regex)

**Navigation:**
- Go to first/last
- Jump to...
- Focus search

**Actions:**
- Open in default app
- Reveal in Finder
- Copy path/content

**Settings:**
- Toggle preferences
- Configure options

### UI Pattern

```
┌─────────────────────────────────────────┐
│ ▸ Type a command...                     │
├─────────────────────────────────────────┤
│ VIEW                                    │
│   Switch to Grid View              G    │
│   Toggle Quick Look            Space    │
│ SELECTION                               │
│   Select All                      ⌘A    │
│   Deselect All                    ⌘D    │
└─────────────────────────────────────────┘
```

---

## View Mode Architecture

### Standard Modes

| Mode | Purpose | Behavior |
|------|---------|----------|
| `grid` | Browse/navigate | Default, shows all items |
| `detail` / `viewer` | Full inspection | Single item, zoom/pan |
| `quicklook` | Fast preview | Overlay, Space to toggle |
| `compare` | Side-by-side | Multiple items |

### Compare Sub-Modes

```typescript
type CompareMode = "solo" | "grid" | "sidebyside";
```

- **Solo**: Full-screen single item, arrows cycle through selection
- **Grid**: Auto-layout all selected items
- **Side-by-side**: Two items with synchronized zoom/pan

### State Management

```typescript
interface ViewState {
  viewMode: "grid" | "viewer" | "compare" | "quicklook";
  compareMode: "solo" | "grid" | "sidebyside";
  quicklookIndex: number;
  selectedIds: Set<string>;
  activeId: string | null;
}
```

---

## Component Patterns

### Overlay/Modal Structure

```tsx
<div className="overlay" onClick={handleBackdropClick}>
  <div className="container">
    <div className="header">
      <div className="title">{title}</div>
      <button className="close">×</button>
    </div>
    <div className="content">{children}</div>
    <div className="footer">{hints}</div>
  </div>
</div>
```

### CSS for Overlays

```css
.overlay {
  position: fixed;
  inset: 0;
  background: var(--bg-overlay);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.container {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  max-width: 90vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
```

### Item Selection States

```css
.item {
  border: 1px solid var(--border-muted);
  transition: all var(--transition-normal);
}

.item:hover {
  background: var(--bg-tertiary);
  border-color: var(--border);
}

.item.active {
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent);
}

.item.selected {
  border-color: var(--success);
  background: var(--success-muted);
}
```

---

## UX Polish Details

### Keyboard Help Overlay

Always provide `?` to show all shortcuts, grouped by function:
- Navigation
- Preview & View
- Selection
- Zoom & Size
- General

### Status Hints

Bottom bar showing:
- Current mode
- Selection count
- Available shortcuts for current context

### Preloading

```typescript
// Preload adjacent items for smooth navigation
useEffect(() => {
  const adjacentIndices = [
    (currentIndex + 1) % items.length,
    (currentIndex - 1 + items.length) % items.length,
  ];
  adjacentIndices.forEach((idx) => {
    const img = new Image();
    img.src = items[idx].src;
  });
}, [currentIndex, items]);
```

### Escape Key Layering

```typescript
// Priority order for Escape:
// 1. Close modals (command palette, settings, help)
// 2. Exit overlay views (quicklook, viewer)
// 3. Return to default view (grid)
// 4. Clear selection
// 5. Clear search
```

---

## Implementation Checklist

### Foundation
- [ ] CSS variables for design system
- [ ] Base reset and typography
- [ ] Scrollbar styling

### Navigation
- [ ] Arrow key navigation (context-aware)
- [ ] Space for Quick Look
- [ ] Tab for selection
- [ ] Escape layering
- [ ] `/` for search focus

### Power Features
- [ ] Command palette (⌘⇧P)
- [ ] Keyboard help overlay (?)
- [ ] Select all / deselect (⌘A/⌘D)

### Views
- [ ] Grid view (default)
- [ ] Detail/Viewer mode
- [ ] Quick Look overlay
- [ ] Compare mode with sub-modes

### Polish
- [ ] Focus rings for keyboard nav
- [ ] Hover states
- [ ] Selection indicators
- [ ] Loading states
- [ ] Empty states
- [ ] Transitions (150ms)

---

## Quick Reference

### File Structure

```
src/
├── components/
│   ├── Grid.tsx           # Main browse view
│   ├── Viewer.tsx         # Detail view
│   ├── QuickLook.tsx      # Space preview
│   ├── Compare.tsx        # Comparison view
│   ├── CommandPalette.tsx # ⌘⇧P
│   ├── KeyboardHelp.tsx   # ? overlay
│   └── SearchBar.tsx      # With dropdown
├── store.ts               # Zustand state
├── types.ts               # ViewMode, etc.
└── styles.css             # Design system
```

### State Shape

```typescript
{
  viewMode: "grid" | "viewer" | "compare" | "quicklook",
  compareMode: "solo" | "grid" | "sidebyside",
  activeId: string | null,
  selectedIds: Set<string>,
  commandPaletteOpen: boolean,
  keyboardHelpOpen: boolean,
}
```

### Key CSS Classes

```
.overlay          - Full-screen backdrop
.container        - Elevated card
.header           - Top bar with title + close
.content          - Main scrollable area
.footer           - Bottom hints bar
.item             - Selectable element
.item.active      - Keyboard focus
.item.selected    - Multi-select
```
