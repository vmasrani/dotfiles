# Implementation Plan: Component Selection & Comparison Features

## Overview
Add two features to the directory comparison visualization:
1. **Single Component View**: Click any file to view its code in a modal with syntax highlighting
2. **Two-Component Comparison**: Shift+click files from left/right panels to see side-by-side diff

## Critical Files

### Backend
- `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/backend.py`
  - Add 2 new API endpoints

### Frontend
- `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`
  - Single-file application (HTML + CSS + JavaScript)
  - Add modals, styles, and interaction handlers

## Implementation Steps

### 1. Backend API Endpoints (backend.py, after line 516)

#### Endpoint 1: Get Single Component
```python
@app.get("/api/component/{project_id}/{path:path}")
def get_component_code(project_id: int, path: str):
    # Query components table for typescript_code, sql_code, html_template
    # Return 404 if not found
```

#### Endpoint 2: Compare Two Components
```python
@app.post("/api/compare-components")
def compare_components(request: dict):
    # Accept: project1_id, path1, project2_id, path2
    # Return both components for comparison
```

### 2. Feature 1: Single Component View

#### HTML (after line 1057)
- Add `#componentModal` with header, close button, content area

#### CSS (after line 806)
- `.file-item.clickable` with hover effect
- `.component-meta` for file metadata display
- `.code-section` and `.code-section-header` for organized code display

#### JavaScript (before line 1624)
- `showComponentModal(projectId, path)` - fetch and display code
- `closeComponentModal()` - cleanup and hide
- State: `componentModalState = { isOpen, currentProjectId, currentPath }`
- Use existing Prism.js for syntax highlighting (TypeScript, SQL, HTML)

### 3. Feature 2: Two-Component Comparison

#### HTML (after componentModal, ~line 1070)
- Add `#compareModal` with larger width (2000px max-width)
- Include meta section and content section

#### CSS
- `.file-item.selected-left` - cyan highlight for left panel selections
- `.file-item.selected-right` - coral highlight for right panel selections
- `.selection-controls` - sticky header with selection status
- `.comparison-container` - grid layout for side-by-side panels
- `.comparison-panel` with `.left`/`.right` variants

#### JavaScript (around line 1622)
- State: `comparisonState = { isActive, leftSelection, rightSelection }`
- `handleFileSelection(fileItem, projectId, path, projectName)` - track selections
- `updateComparisonUI()` - refresh selection controls and enable/disable compare button
- `clearComparisonSelection()` - reset state and remove CSS classes
- `showCompareModal()` - fetch both components and render side-by-side
- `renderCodeComparison(codeType, code1, code2, project1Name, project2Name)` - generate comparison HTML
- `closeCompareModal()` - cleanup

#### Update showPathComparison() (line 1624)
- Add selection controls HTML at top of modal content

### 4. Event Handlers

#### Update attachTreeHandlers() (line 1549)
Replace entire function to support:
- Existing folder toggle (click `.tree-folder`)
- **Regular click** on `.file-item` → `showComponentModal()`
- **Shift+click** on `.file-item` → `handleFileSelection()`
- Call `updateComparisonUI()` after attaching handlers

#### Keyboard Support (around line 1905)
- ESC key closes both modals
- Update existing `window.onclick` to handle both modals

### 5. External Dependencies

#### Add to `<head>` (around line 13)
```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/diff/5.1.0/diff.min.js"></script>
```
Note: jsdiff library for potential future diff enhancements (currently using simple side-by-side)

## Key Design Decisions

1. **Interaction Model**:
   - Regular click = view single component
   - Shift+click = select for comparison
   - No mode switching needed

2. **Visual Feedback**:
   - Cyan (left panel) and coral (right panel) consistent with existing design
   - Selected items get border-left highlight
   - Sticky selection controls show current selections

3. **State Management**:
   - Vanilla JavaScript with closure-based state
   - Two independent state objects (single view vs comparison)
   - No framework overhead

4. **Code Display**:
   - Reuse existing Prism.js (already loaded)
   - Show TypeScript, SQL, and HTML sections separately
   - Scrollable panels for large files (max-height: 70vh)

## Edge Cases Handled

- Missing component → 404 error message
- Empty code fields → "No code found" message
- Paths with special characters → `encodeURIComponent()`
- Network errors → user-friendly error messages
- Large files → scrollable panels
- Multiple modals open → ESC closes active modal
- Selection persistence → cleared manually with "Clear" button
- Prism language fallback → use JavaScript if language unavailable

## Testing Checklist

### Single Component View
- [ ] Click file in left/right panel → modal opens
- [ ] Code displayed with correct syntax highlighting
- [ ] ESC key closes modal
- [ ] Missing file shows error

### Comparison
- [ ] Shift+click left panel → cyan highlight
- [ ] Shift+click right panel → coral highlight
- [ ] Compare button enables when both selected
- [ ] Side-by-side view shows both files
- [ ] Clear button resets selections

## Variables to Track

When implementing, need to know:
- `currentProject1Id` and `currentProject2Id` (likely in closure where `showPathComparison()` is called)
- `projects` array (global, contains project metadata)
- `API_BASE` constant (base URL for API calls)
- `fetchAPI()` helper function (wrapper for fetch)
- `escapeHtml()` helper function (XSS prevention)

These should already exist in the codebase based on exploration.

## Implementation Sequence

1. **Backend first** (15 min) - Add both endpoints, test with curl
2. **Feature 1** (30 min) - Single component view end-to-end
3. **Feature 2** (45 min) - Comparison selection and modal
4. **Integration** (20 min) - Update shared event handlers, test both features together

**Estimated Total Time**: ~2 hours
