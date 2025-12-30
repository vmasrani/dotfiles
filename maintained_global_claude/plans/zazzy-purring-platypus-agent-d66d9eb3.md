# Implementation Plan: Single Component View & Two-Component Comparison

## Overview
Add two new features to layer4_viz.html:
1. Click any file to view its code in a modal
2. Select files from left/right panels for side-by-side diff comparison

## Architecture Analysis

### Current State
- **File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html` (1919 lines)
- **Backend**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/backend.py` (FastAPI)
- **Database**: PostgreSQL with `components` table containing code and metadata
- **Libraries**: Chart.js, Prism.js (syntax highlighting) already loaded
- **Existing Modal**: `#pathModal` (lines 1029-1057) for directory comparison

### Key Code Patterns
- **Modal Pattern**: `.modal` container with `.modal-content`, `.modal-header`, `.close` button
- **Tree Rendering**: `renderTree()` generates file tree HTML, `attachTreeHandlers()` for folder toggle
- **File Items**: `<span class="file-item" data-path="..." data-is-shared="true/false">`
- **API Calls**: `fetchAPI()` wrapper function (lines 1105-1109)
- **Styling**: CSS custom properties, consistent design system with cyan/coral accent colors

---

## Feature 1: Single Component View

### Implementation Steps

#### 1.1 Add New API Endpoint
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/backend.py`

Add endpoint after line 516:

```python
@app.get("/api/component/{project_id}/{path:path}")
def get_component_code(project_id: int, path: str):
    """Get code for a specific component by project_id and full_path"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT
            component_id,
            project_id,
            full_path,
            component_type,
            typescript_code,
            sql_code,
            html_template,
            code_hash
        FROM components
        WHERE project_id = %s AND full_path = %s
        LIMIT 1;
    """
    
    cursor.execute(query, (project_id, path))
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not result:
        raise HTTPException(status_code=404, detail="Component not found")
    
    return result
```

**Rationale**: Need to fetch code content by path. Using path parameter to match `data-path` attribute on file items.

#### 1.2 Add HTML Modal Structure
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Add after existing `#pathModal` (around line 1057):

```html
<!-- Single Component View Modal -->
<div id="componentModal" class="modal">
  <div class="modal-content">
    <div class="modal-header">
      <h2 id="componentModalTitle">Component View</h2>
      <span class="close" onclick="closeComponentModal()">&times;</span>
    </div>
    <div id="componentModalContent">
      <div class="loading">Loading component...</div>
    </div>
  </div>
</div>
```

**Rationale**: Reuse existing modal styling, consistent naming pattern.

#### 1.3 Add CSS Styles
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Add to `<style>` section (around line 806):

```css
.file-item.clickable {
  cursor: pointer;
  padding: 2px 6px;
  transition: all 0.2s;
  display: inline-block;
}

.file-item.clickable:hover {
  background: rgba(0, 229, 255, 0.2) !important;
  color: var(--cyan);
  padding-left: 10px;
}

.component-meta {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding: 15px;
  background: var(--charcoal-light);
  border: 1px solid var(--charcoal-lighter);
}

.code-section {
  margin: 20px 0;
}

.code-section-header {
  background: var(--charcoal-lighter);
  color: var(--cyan);
  padding: 12px 20px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-family: 'JetBrains Mono', monospace;
  border-left: 3px solid var(--cyan);
  margin-bottom: 0;
}
```

**Rationale**: Maintain design consistency, clear visual hierarchy for code sections.

#### 1.4 Add JavaScript Functions
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Add before `showPathComparison()` function (around line 1624):

```javascript
// Component Modal State
let componentModalState = {
  isOpen: false,
  currentProjectId: null,
  currentPath: null
};

function closeComponentModal() {
  const modal = document.getElementById('componentModal');
  modal.style.display = 'none';
  componentModalState.isOpen = false;
  componentModalState.currentProjectId = null;
  componentModalState.currentPath = null;
}

async function showComponentModal(projectId, path) {
  componentModalState.isOpen = true;
  componentModalState.currentProjectId = projectId;
  componentModalState.currentPath = path;
  
  const modal = document.getElementById('componentModal');
  const content = document.getElementById('componentModalContent');
  const title = document.getElementById('componentModalTitle');
  
  title.textContent = `Component: ${path}`;
  content.innerHTML = '<div class="loading">Loading component code...</div>';
  modal.style.display = 'block';
  
  try {
    const encodedPath = encodeURIComponent(path);
    const component = await fetchAPI(`/component/${projectId}/${encodedPath}`);
    
    const project = projects.find(p => p.project_id === projectId);
    const projectName = project?.company_name || `Project ${projectId}`;
    
    let codeHtml = '';
    
    if (component.typescript_code) {
      const highlighted = Prism.highlight(
        component.typescript_code,
        Prism.languages.typescript || Prism.languages.javascript,
        'typescript'
      );
      codeHtml += `
        <div class="code-section">
          <div class="code-section-header">TypeScript</div>
          <div class="code-block">
            <pre class="language-typescript"><code>${highlighted}</code></pre>
          </div>
        </div>
      `;
    }
    
    if (component.sql_code) {
      const highlighted = Prism.highlight(
        component.sql_code,
        Prism.languages.sql || Prism.languages.javascript,
        'sql'
      );
      codeHtml += `
        <div class="code-section">
          <div class="code-section-header">SQL</div>
          <div class="code-block">
            <pre class="language-sql"><code>${highlighted}</code></pre>
          </div>
        </div>
      `;
    }
    
    if (component.html_template) {
      const highlighted = Prism.highlight(
        component.html_template,
        Prism.languages.html || Prism.languages.markup,
        'html'
      );
      codeHtml += `
        <div class="code-section">
          <div class="code-section-header">HTML Template</div>
          <div class="code-block">
            <pre class="language-html"><code>${highlighted}</code></pre>
          </div>
        </div>
      `;
    }
    
    if (!codeHtml) {
      codeHtml = '<div class="empty-state">No code found for this component.</div>';
    }
    
    content.innerHTML = `
      <div class="component-meta">
        <span class="pill">Project: <span>${escapeHtml(projectName)}</span></span>
        <span class="pill">Path: <span>${escapeHtml(component.full_path)}</span></span>
        <span class="pill">Type: <span>${escapeHtml(component.component_type || 'unknown')}</span></span>
        <span class="pill">Hash: <span>${escapeHtml(component.code_hash || 'none')}</span></span>
      </div>
      ${codeHtml}
    `;
  } catch (err) {
    content.innerHTML = `<div class="error">Failed to load component: ${escapeHtml(err.message)}</div>`;
  }
}
```

**Rationale**: 
- State management tracks modal state
- Supports TypeScript, SQL, and HTML (all three code types in database)
- Reuses Prism.js for syntax highlighting
- Error handling for missing components

#### 1.5 Attach Click Handlers to File Items
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Modify `attachTreeHandlers()` function (around line 1549):

```javascript
function attachTreeHandlers() {
  // Existing folder toggle handlers
  document.querySelectorAll('.tree-folder').forEach(folder => {
    folder.addEventListener('click', (e) => {
      const nodeId = e.target.getAttribute('data-node-id');
      const children = document.getElementById(nodeId);
      if (children) {
        children.classList.toggle('hidden');
        e.target.classList.toggle('collapsed');
      }
    });
  });
  
  // NEW: File click handlers for single component view
  document.querySelectorAll('.file-item').forEach(fileItem => {
    fileItem.classList.add('clickable');
    fileItem.addEventListener('click', (e) => {
      e.stopPropagation(); // Prevent folder toggle
      const path = fileItem.getAttribute('data-path');
      const projectId = currentProject1Id || currentProject2Id;
      
      // Determine which project this file belongs to
      // Check if in left or right panel
      const isLeftPanel = fileItem.closest('.tree-panel:nth-child(1)') !== null;
      const targetProjectId = isLeftPanel ? currentProject1Id : currentProject2Id;
      
      if (path && targetProjectId) {
        showComponentModal(targetProjectId, path);
      }
    });
  });
}
```

**Rationale**: 
- Attach handlers after tree is rendered
- Determine project context from panel position
- Prevent event bubbling to folder handlers

#### 1.6 Add Keyboard Support
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Add to existing window event listeners (around line 1905):

```javascript
// ESC key to close modals
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    if (componentModalState.isOpen) {
      closeComponentModal();
    }
    if (document.getElementById('pathModal').style.display === 'block') {
      closeModal();
    }
  }
});

// Click outside modal to close
window.addEventListener('click', (event) => {
  const pathModal = document.getElementById('pathModal');
  const componentModal = document.getElementById('componentModal');
  
  if (event.target === pathModal) {
    closeModal();
  }
  if (event.target === componentModal) {
    closeComponentModal();
  }
});
```

**Rationale**: Standard UX pattern for modal dismissal.

---

## Feature 2: Two-Component Comparison

### Implementation Steps

#### 2.1 Add New API Endpoint
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/backend.py`

Add after the component endpoint:

```python
@app.post("/api/compare-components")
def compare_components(request: dict):
    """Compare two components side-by-side
    
    Request body:
    {
        "project1_id": int,
        "path1": str,
        "project2_id": int,
        "path2": str
    }
    """
    project1_id = request.get("project1_id")
    path1 = request.get("path1")
    project2_id = request.get("project2_id")
    path2 = request.get("path2")
    
    if not all([project1_id, path1, project2_id, path2]):
        raise HTTPException(status_code=400, detail="Missing required parameters")
    
    conn = get_db()
    cursor = conn.cursor()
    
    query = """
        SELECT
            component_id,
            project_id,
            full_path,
            component_type,
            typescript_code,
            sql_code,
            html_template,
            code_hash
        FROM components
        WHERE (project_id = %s AND full_path = %s)
           OR (project_id = %s AND full_path = %s);
    """
    
    cursor.execute(query, (project1_id, path1, project2_id, path2))
    results = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    component1 = next((r for r in results if r["project_id"] == project1_id), None)
    component2 = next((r for r in results if r["project_id"] == project2_id), None)
    
    return {
        "component1": component1,
        "component2": component2
    }
```

**Rationale**: Single query fetches both components efficiently.

#### 2.2 Add HTML Modal Structure
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Add after componentModal (around line 1070):

```html
<!-- Two-Component Comparison Modal -->
<div id="compareModal" class="modal">
  <div class="modal-content" style="max-width: 2000px;">
    <div class="modal-header">
      <h2 id="compareModalTitle">Component Comparison</h2>
      <span class="close" onclick="closeCompareModal()">&times;</span>
    </div>
    <div id="compareModalMeta"></div>
    <div id="compareModalContent"></div>
  </div>
</div>
```

#### 2.3 Add CSS Styles
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Add to `<style>` section:

```css
.file-item.selected-left {
  background: rgba(0, 229, 255, 0.3) !important;
  border-left: 3px solid var(--cyan);
  padding-left: 10px;
  font-weight: 600;
}

.file-item.selected-right {
  background: rgba(255, 107, 107, 0.3) !important;
  border-left: 3px solid var(--coral);
  padding-left: 10px;
  font-weight: 600;
}

.comparison-container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-top: 20px;
}

.comparison-panel {
  background: var(--charcoal-light);
  border: 1px solid var(--charcoal-lighter);
  padding: 0;
  overflow: hidden;
}

.comparison-panel-header {
  background: var(--charcoal-lighter);
  padding: 15px 20px;
  border-bottom: 1px solid var(--charcoal-lighter);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.comparison-panel-header.left {
  border-left: 3px solid var(--cyan);
}

.comparison-panel-header.right {
  border-left: 3px solid var(--coral);
}

.comparison-panel-body {
  padding: 20px;
  max-height: 70vh;
  overflow-y: auto;
}

.diff-line {
  display: block;
  padding: 2px 5px;
  margin: 0;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
  line-height: 1.6;
}

.diff-line.added {
  background: rgba(0, 229, 255, 0.15);
  border-left: 3px solid var(--cyan);
}

.diff-line.removed {
  background: rgba(255, 107, 107, 0.15);
  border-left: 3px solid var(--coral);
}

.diff-line.unchanged {
  background: transparent;
  opacity: 0.6;
}

.selection-controls {
  position: sticky;
  top: 0;
  background: var(--charcoal-light);
  padding: 15px;
  border: 1px solid var(--charcoal-lighter);
  margin-bottom: 15px;
  z-index: 10;
  display: flex;
  gap: 15px;
  align-items: center;
  flex-wrap: wrap;
}

.selection-status {
  flex: 1;
  display: flex;
  gap: 20px;
  align-items: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem;
}

.selection-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 15px;
  background: var(--charcoal-lighter);
  border: 1px solid var(--charcoal-lighter);
}

.selection-item.left {
  border-left: 3px solid var(--cyan);
}

.selection-item.right {
  border-left: 3px solid var(--coral);
}

.selection-item .label {
  color: var(--gray);
  font-weight: 600;
}

.selection-item .value {
  color: var(--off-white);
}

.selection-item .empty {
  color: var(--gray);
  font-style: italic;
}

@media (max-width: 1200px) {
  .comparison-container {
    grid-template-columns: 1fr;
  }
}
```

**Rationale**: 
- Visual distinction between left (cyan) and right (coral) selections
- Responsive design for smaller screens
- Diff highlighting for line-by-line comparison

#### 2.4 Add jsdiff Library
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Add to `<head>` section (around line 13):

```html
<script src="https://cdnjs.cloudflare.com/ajax/libs/diff/5.1.0/diff.min.js"></script>
```

**Rationale**: Established library for text diffing, small footprint.

#### 2.5 Add JavaScript State Management
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Add to script section (around line 1622):

```javascript
// Two-component comparison state
let comparisonState = {
  isActive: false,
  leftSelection: null,  // { projectId, path, projectName }
  rightSelection: null  // { projectId, path, projectName }
};

function clearComparisonSelection() {
  comparisonState.leftSelection = null;
  comparisonState.rightSelection = null;
  comparisonState.isActive = false;
  
  // Remove visual selection indicators
  document.querySelectorAll('.file-item.selected-left').forEach(el => {
    el.classList.remove('selected-left');
  });
  document.querySelectorAll('.file-item.selected-right').forEach(el => {
    el.classList.remove('selected-right');
  });
  
  updateComparisonUI();
}

function updateComparisonUI() {
  const controls = document.querySelector('.selection-controls');
  if (!controls) return;
  
  const statusHtml = `
    <div class="selection-status">
      <div class="selection-item left">
        <span class="label">Left:</span>
        ${comparisonState.leftSelection 
          ? `<span class="value">${escapeHtml(comparisonState.leftSelection.path)}</span>`
          : `<span class="empty">No selection</span>`
        }
      </div>
      <div class="selection-item right">
        <span class="label">Right:</span>
        ${comparisonState.rightSelection 
          ? `<span class="value">${escapeHtml(comparisonState.rightSelection.path)}</span>`
          : `<span class="empty">No selection</span>`
        }
      </div>
    </div>
    <button 
      id="btnCompareComponents" 
      ${(!comparisonState.leftSelection || !comparisonState.rightSelection) ? 'disabled' : ''}
      style="${(!comparisonState.leftSelection || !comparisonState.rightSelection) ? 'opacity: 0.5; cursor: not-allowed;' : ''}"
    >
      Compare
    </button>
    <button class="ghost" onclick="clearComparisonSelection()">Clear</button>
  `;
  
  controls.innerHTML = statusHtml;
  
  // Attach compare button handler
  const compareBtn = document.getElementById('btnCompareComponents');
  if (compareBtn && !compareBtn.disabled) {
    compareBtn.addEventListener('click', showCompareModal);
  }
}

function handleFileSelection(fileItem, projectId, path, projectName) {
  // Determine which panel this file is in
  const isLeftPanel = fileItem.closest('.tree-panel:first-child') !== null;
  
  if (isLeftPanel) {
    // Left panel selection
    document.querySelectorAll('.file-item.selected-left').forEach(el => {
      el.classList.remove('selected-left');
    });
    fileItem.classList.add('selected-left');
    
    comparisonState.leftSelection = { projectId, path, projectName };
  } else {
    // Right panel selection
    document.querySelectorAll('.file-item.selected-right').forEach(el => {
      el.classList.remove('selected-right');
    });
    fileItem.classList.add('selected-right');
    
    comparisonState.rightSelection = { projectId, path, projectName };
  }
  
  updateComparisonUI();
}
```

**Rationale**: 
- Separate state for left/right selections
- Clear visual feedback with CSS classes
- Enable/disable compare button based on selection state

#### 2.6 Add Comparison Modal Functions
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

```javascript
function closeCompareModal() {
  const modal = document.getElementById('compareModal');
  modal.style.display = 'none';
}

async function showCompareModal() {
  if (!comparisonState.leftSelection || !comparisonState.rightSelection) {
    alert('Please select one file from each panel');
    return;
  }
  
  const modal = document.getElementById('compareModal');
  const title = document.getElementById('compareModalTitle');
  const meta = document.getElementById('compareModalMeta');
  const content = document.getElementById('compareModalContent');
  
  title.textContent = 'Component Comparison';
  meta.innerHTML = '';
  content.innerHTML = '<div class="loading">Loading components for comparison...</div>';
  modal.style.display = 'block';
  
  try {
    const response = await fetchAPI('/compare-components', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        project1_id: comparisonState.leftSelection.projectId,
        path1: comparisonState.leftSelection.path,
        project2_id: comparisonState.rightSelection.projectId,
        path2: comparisonState.rightSelection.path
      })
    });
    
    const { component1, component2 } = response;
    
    if (!component1) {
      content.innerHTML = `<div class="error">Component not found: ${escapeHtml(comparisonState.leftSelection.path)}</div>`;
      return;
    }
    
    if (!component2) {
      content.innerHTML = `<div class="error">Component not found: ${escapeHtml(comparisonState.rightSelection.path)}</div>`;
      return;
    }
    
    // Build comparison UI
    meta.innerHTML = `
      <div class="comparison-stats">
        <div class="comparison-stat">
          <div class="label">Same Code Hash</div>
          <div class="value">${component1.code_hash === component2.code_hash ? 'YES' : 'NO'}</div>
        </div>
        <div class="comparison-stat">
          <div class="label">Left Component Type</div>
          <div class="value">${escapeHtml(component1.component_type || 'unknown')}</div>
        </div>
        <div class="comparison-stat">
          <div class="label">Right Component Type</div>
          <div class="value">${escapeHtml(component2.component_type || 'unknown')}</div>
        </div>
      </div>
    `;
    
    // Compare TypeScript code
    let comparisonHtml = '';
    
    if (component1.typescript_code || component2.typescript_code) {
      comparisonHtml += renderCodeComparison(
        'TypeScript',
        component1.typescript_code || '',
        component2.typescript_code || '',
        comparisonState.leftSelection.projectName,
        comparisonState.rightSelection.projectName
      );
    }
    
    if (component1.sql_code || component2.sql_code) {
      comparisonHtml += renderCodeComparison(
        'SQL',
        component1.sql_code || '',
        component2.sql_code || '',
        comparisonState.leftSelection.projectName,
        comparisonState.rightSelection.projectName
      );
    }
    
    if (component1.html_template || component2.html_template) {
      comparisonHtml += renderCodeComparison(
        'HTML Template',
        component1.html_template || '',
        component2.html_template || '',
        comparisonState.leftSelection.projectName,
        comparisonState.rightSelection.projectName
      );
    }
    
    if (!comparisonHtml) {
      comparisonHtml = '<div class="empty-state">No code to compare.</div>';
    }
    
    content.innerHTML = comparisonHtml;
    
  } catch (err) {
    content.innerHTML = `<div class="error">Failed to load comparison: ${escapeHtml(err.message)}</div>`;
  }
}

function renderCodeComparison(codeType, code1, code2, project1Name, project2Name) {
  // Use jsdiff to compute line-by-line diff
  const diff = Diff.diffLines(code1, code2);
  
  // Build left and right panels
  let leftHtml = '';
  let rightHtml = '';
  
  diff.forEach(part => {
    const lines = part.value.split('\n').filter(l => l !== '');
    
    if (part.added) {
      // Only in right
      lines.forEach(line => {
        rightHtml += `<div class="diff-line added">${escapeHtml(line)}</div>`;
      });
    } else if (part.removed) {
      // Only in left
      lines.forEach(line => {
        leftHtml += `<div class="diff-line removed">${escapeHtml(line)}</div>`;
      });
    } else {
      // Unchanged in both
      lines.forEach(line => {
        const escapedLine = escapeHtml(line);
        leftHtml += `<div class="diff-line unchanged">${escapedLine}</div>`;
        rightHtml += `<div class="diff-line unchanged">${escapedLine}</div>`;
      });
    }
  });
  
  // Apply syntax highlighting
  const lang = codeType === 'TypeScript' ? 'typescript' : 
               codeType === 'SQL' ? 'sql' : 'html';
  
  let left1Highlighted = code1;
  let code2Highlighted = code2;
  
  try {
    if (Prism.languages[lang]) {
      code1Highlighted = Prism.highlight(code1, Prism.languages[lang], lang);
      code2Highlighted = Prism.highlight(code2, Prism.languages[lang], lang);
    }
  } catch (e) {
    console.warn('Prism highlighting failed:', e);
  }
  
  return `
    <div style="margin: 30px 0;">
      <h3 style="color: var(--cyan); font-size: 1.2rem; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 0.05em;">
        ${codeType} Comparison
      </h3>
      <div class="comparison-container">
        <div class="comparison-panel">
          <div class="comparison-panel-header left">
            <span style="font-weight: 600; color: var(--cyan);">${escapeHtml(project1Name)}</span>
            <span style="font-size: 0.75rem; color: var(--gray);">${comparisonState.leftSelection.path}</span>
          </div>
          <div class="comparison-panel-body">
            <div class="code-block">
              <pre class="language-${lang}"><code>${code1Highlighted}</code></pre>
            </div>
          </div>
        </div>
        <div class="comparison-panel">
          <div class="comparison-panel-header right">
            <span style="font-weight: 600; color: var(--coral);">${escapeHtml(project2Name)}</span>
            <span style="font-size: 0.75rem; color: var(--gray);">${comparisonState.rightSelection.path}</span>
          </div>
          <div class="comparison-panel-body">
            <div class="code-block">
              <pre class="language-${lang}"><code>${code2Highlighted}</code></pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
}
```

**Rationale**: 
- Side-by-side layout for easy comparison
- Syntax highlighting maintained via Prism.js
- jsdiff for intelligent line-level diffing
- Support all three code types (TypeScript, SQL, HTML)

#### 2.7 Add Selection Controls to Modal
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Modify `showPathComparison()` function to add selection controls (around line 1678):

```javascript
content.innerHTML = `
  <div class="selection-controls">
    <span style="color: var(--gray); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;">
      Click files to select for comparison:
    </span>
    <div class="selection-status">
      <div class="selection-item left">
        <span class="label">Left:</span>
        <span class="empty">No selection</span>
      </div>
      <div class="selection-item right">
        <span class="label">Right:</span>
        <span class="empty">No selection</span>
      </div>
    </div>
    <button id="btnCompareComponents" disabled style="opacity: 0.5; cursor: not-allowed;">Compare</button>
    <button class="ghost" onclick="clearComparisonSelection()">Clear</button>
  </div>
  <div class="comparison-stats">
    <!-- existing stats -->
  </div>
  <div class="tree-comparison">
    <!-- existing tree panels -->
  </div>
`;
```

#### 2.8 Update File Click Handlers
**File**: `/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html`

Modify `attachTreeHandlers()` to support both features:

```javascript
function attachTreeHandlers() {
  // Existing folder toggle handlers
  document.querySelectorAll('.tree-folder').forEach(folder => {
    folder.addEventListener('click', (e) => {
      const nodeId = e.target.getAttribute('data-node-id');
      const children = document.getElementById(nodeId);
      if (children) {
        children.classList.toggle('hidden');
        e.target.classList.toggle('collapsed');
      }
    });
  });
  
  // File click handlers - support both single view and comparison
  document.querySelectorAll('.file-item').forEach(fileItem => {
    fileItem.classList.add('clickable');
    fileItem.addEventListener('click', (e) => {
      e.stopPropagation();
      const path = fileItem.getAttribute('data-path');
      
      // Determine project context
      const isLeftPanel = fileItem.closest('.tree-panel:first-child') !== null;
      const projectId = isLeftPanel ? currentProject1Id : currentProject2Id;
      const project = projects.find(p => p.project_id === projectId);
      const projectName = project?.company_name || `Project ${projectId}`;
      
      if (!path || !projectId) return;
      
      // Check if Shift key is held for comparison mode
      if (e.shiftKey) {
        handleFileSelection(fileItem, projectId, path, projectName);
      } else {
        // Single component view
        showComponentModal(projectId, path);
      }
    });
  });
}
```

**Rationale**: 
- Default click = single component view
- Shift+click = add to comparison selection
- Clear UX pattern, no mode switching required

---

## Edge Cases & Error Handling

### Edge Cases to Handle

1. **Missing Component**
   - API returns 404 → Show friendly error in modal
   - Implementation: Try-catch in `showComponentModal()`

2. **Empty Code Fields**
   - Component exists but no TypeScript/SQL/HTML
   - Implementation: Check each field, show "No code found" message

3. **Same File Selected Twice**
   - User selects same file for left and right
   - Implementation: Warning message, disable compare button

4. **Path Encoding Issues**
   - Paths with special characters (spaces, slashes)
   - Implementation: `encodeURIComponent()` for path parameter

5. **Network Errors**
   - API unreachable or timeout
   - Implementation: Catch fetch errors, show error message in modal

6. **Large Files**
   - Very long code files slow down rendering
   - Implementation: CSS `max-height` with scrolling on code blocks

7. **Multiple Modals Open**
   - User opens comparison while component modal is open
   - Implementation: Only one modal open at a time (ESC closes current)

8. **Selection State Persistence**
   - User closes modal, selections should remain
   - Implementation: Don't clear state on modal close, only on "Clear" button

9. **Project ID Mismatch**
   - File path doesn't exist in target project
   - Implementation: Backend returns null, frontend shows error

10. **Prism.js Language Support**
    - Language not loaded for syntax highlighting
    - Implementation: Fallback to JavaScript highlighting

### Error Handling Strategy

#### Frontend (JavaScript)
```javascript
try {
  const component = await fetchAPI(`/component/${projectId}/${encodedPath}`);
  // ... render component
} catch (err) {
  if (err.message.includes('404')) {
    content.innerHTML = `<div class="error">Component not found at path: ${escapeHtml(path)}</div>`;
  } else if (err.message.includes('Network')) {
    content.innerHTML = `<div class="error">Network error: Unable to reach API. Please check that the backend is running.</div>`;
  } else {
    content.innerHTML = `<div class="error">Error loading component: ${escapeHtml(err.message)}</div>`;
  }
}
```

#### Backend (Python)
```python
# Already has error handling via HTTPException
# Add logging for debugging
import logging

logger = logging.getLogger(__name__)

@app.get("/api/component/{project_id}/{path:path}")
def get_component_code(project_id: int, path: str):
    logger.info(f"Fetching component: project_id={project_id}, path={path}")
    # ... existing implementation
    if not result:
        logger.warning(f"Component not found: {project_id}/{path}")
        raise HTTPException(status_code=404, detail=f"Component not found: {path}")
```

---

## Testing Checklist

### Feature 1: Single Component View
- [ ] Click file in left panel → modal opens with correct code
- [ ] Click file in right panel → modal opens with correct code
- [ ] ESC key closes modal
- [ ] Click outside modal closes modal
- [ ] Close button (×) closes modal
- [ ] TypeScript code has syntax highlighting
- [ ] SQL code has syntax highlighting
- [ ] HTML code has syntax highlighting
- [ ] Component with no code shows "No code found" message
- [ ] Non-existent path shows 404 error
- [ ] Network error shows appropriate message
- [ ] File path with spaces/special chars works correctly

### Feature 2: Two-Component Comparison
- [ ] Shift+click file in left panel → adds to left selection (cyan highlight)
- [ ] Shift+click file in right panel → adds to right selection (coral highlight)
- [ ] Compare button disabled when only one file selected
- [ ] Compare button enabled when both files selected
- [ ] Click Compare → comparison modal opens
- [ ] Side-by-side code display works
- [ ] Diff highlighting shows added/removed/unchanged lines
- [ ] Same code hash displays correctly in stats
- [ ] Clear button removes selections and highlights
- [ ] Selecting new file replaces previous selection
- [ ] ESC closes comparison modal
- [ ] Comparison of identical files works
- [ ] Comparison of completely different files works
- [ ] Mixed code types (TS vs SQL) handled gracefully

### Integration Tests
- [ ] Switch between single view and comparison mode smoothly
- [ ] Open single view, close, then open comparison → both work
- [ ] Multiple comparisons in sequence work correctly
- [ ] Filter tree (show all/differences/shared) doesn't break file clicks
- [ ] Folder collapse/expand doesn't interfere with file selection
- [ ] Responsive design works on smaller screens

---

## Performance Considerations

### Optimizations

1. **Lazy Loading Code**
   - Don't load code until modal opens
   - Cache fetched components in memory (optional)

2. **Syntax Highlighting**
   - Prism.js already loaded, no additional overhead
   - Highlight only visible code (not diffs)

3. **Modal Rendering**
   - Reuse existing modal DOM elements
   - Only update content, not rebuild structure

4. **Event Listeners**
   - Use event delegation where possible
   - Remove listeners when modal closes (not critical for single-page app)

5. **Diff Algorithm**
   - jsdiff is efficient for moderate file sizes
   - For very large files (>10k lines), consider truncation

### Potential Bottlenecks

1. **Large Files**: Files with >5000 lines may slow rendering
   - Mitigation: Add scrolling, consider line limits
   
2. **Many Files**: Clicking rapidly could queue multiple API calls
   - Mitigation: Debounce or cancel previous requests
   
3. **Network Latency**: Slow API responses
   - Mitigation: Loading indicators, timeout handling

---

## Implementation Order

### Phase 1: Backend (15 min)
1. Add `/api/component/{project_id}/{path:path}` endpoint
2. Add `/api/compare-components` POST endpoint
3. Test endpoints with curl or Postman

### Phase 2: Single Component View (30 min)
1. Add `#componentModal` HTML structure
2. Add CSS styles for component modal
3. Add `showComponentModal()` and `closeComponentModal()` functions
4. Update `attachTreeHandlers()` to handle file clicks
5. Add keyboard support (ESC key)
6. Test with various file types

### Phase 3: Two-Component Comparison (45 min)
1. Add jsdiff CDN script
2. Add `#compareModal` HTML structure
3. Add CSS styles for comparison (selections, diff highlighting)
4. Add comparison state management
5. Add selection UI controls
6. Implement `handleFileSelection()` function
7. Implement `showCompareModal()` and `renderCodeComparison()` functions
8. Update `attachTreeHandlers()` for Shift+click
9. Test comparison with various file combinations

### Phase 4: Polish & Testing (20 min)
1. Test all edge cases
2. Verify responsive design
3. Check accessibility (keyboard navigation)
4. Verify error messages are clear
5. Test with backend API running

**Total Estimated Time**: ~2 hours

---

## Rollback Plan

If issues arise during implementation:

1. **Backend Changes**: 
   - Remove new endpoints from backend.py
   - Restart API server

2. **Frontend Changes**:
   - Revert to backup: `cp layer4_viz.html.backup layer4_viz.html`
   - Or use git: `git checkout layer4_viz.html`

3. **Partial Implementation**:
   - Feature 1 (Single View) can work independently of Feature 2
   - Can deploy Feature 1 first, then add Feature 2 later

---

## Future Enhancements (Out of Scope)

1. **Unified Diff View**: Alternative to side-by-side comparison
2. **Copy Code Button**: Copy code blocks to clipboard
3. **Permalink**: Share direct link to specific component
4. **Code Search**: Search within displayed code
5. **Download Code**: Download component code as file
6. **History**: Track recently viewed components
7. **Annotations**: Add notes/comments to code sections
8. **Inline Diff**: Character-level highlighting within lines

---

## Dependencies Summary

### External Libraries (CDN)
- **Existing**: Chart.js, Prism.js (typescript, sql, html)
- **New**: jsdiff (5.1.0)

### Browser Requirements
- Modern browser with ES6+ support
- Fetch API
- CSS Grid support

### Backend Requirements
- Python 3.12+
- FastAPI
- PostgreSQL with `components` table

---

## Critical Files for Implementation

1. **/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/backend.py**
   - Add 2 new API endpoints
   - Lines to modify: After line 516 (add endpoints)

2. **/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html**
   - Main implementation file
   - Lines to modify:
     - ~13: Add jsdiff CDN
     - ~806: Add CSS styles
     - ~1070: Add modal HTML structures
     - ~1549: Update `attachTreeHandlers()`
     - ~1622: Add state management and modal functions
     - ~1678: Update `showPathComparison()` to add selection controls

3. **/Users/vmasrani/dev/projects/fieldcap/similarity/layer4/layer4_viz.html.backup**
   - Backup for rollback if needed
   - Keep as-is, do not modify

---

## Key Design Decisions

### 1. Single API Endpoint vs. Multiple
**Decision**: Use separate endpoints for single component and comparison
**Rationale**: Clearer separation of concerns, easier to optimize separately

### 2. Shift+Click vs. Toggle Button
**Decision**: Shift+click for comparison mode
**Rationale**: Familiar UX pattern, no UI clutter, works alongside single-click

### 3. Side-by-Side vs. Unified Diff
**Decision**: Side-by-side for initial implementation
**Rationale**: Easier to read for long files, matches existing tree comparison layout

### 4. jsdiff vs. Custom Implementation
**Decision**: Use jsdiff library
**Rationale**: Battle-tested, handles edge cases, small size (~10KB)

### 5. Modal vs. Inline Display
**Decision**: Modal for both features
**Rationale**: Consistent with existing UI, focuses attention, handles large content

### 6. State Management Approach
**Decision**: Simple object-based state (no framework)
**Rationale**: Matches existing vanilla JS approach, minimal complexity

---

## Code Style Guidelines

Follow existing conventions in layer4_viz.html:

1. **Naming**: camelCase for functions/variables
2. **CSS**: BEM-like naming with descriptive classes
3. **Indentation**: 2 spaces
4. **Quotes**: Single quotes for JS strings, double for HTML attributes
5. **Comments**: Explain "why" not "what"
6. **Error Messages**: User-friendly, specific, actionable

---

## Security Considerations

### Input Validation
- **Path Parameter**: Validate on backend (no path traversal)
- **Project IDs**: Integer validation, check existence
- **SQL Injection**: Use parameterized queries (already implemented)

### XSS Prevention
- **Code Display**: Already using `escapeHtml()` for user data
- **Prism Highlighting**: Operates on escaped content, safe
- **Modal Content**: Always escape before inserting into DOM

### CORS
- Already configured in backend (`allow_origins=["*"]`)
- For production: Restrict to specific origins

---

## Documentation Updates Needed

After implementation, update:

1. **TEMPLATE_VIZ_README.md**: Add section on new features
2. **README.md**: Mention component viewing capabilities
3. **Inline comments**: Add JSDoc comments for new functions

---

