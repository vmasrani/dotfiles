# PostgreSQL Preprocessing Plan for JSON Similarity Analysis

## Context

- **Data**: 197 JSON files (637 KB - 5.4 MB each)
- **Structure**: `{metadata: {...}, paths: {...}}` with nested component hierarchies
- **Scale**: ~2,000 components per project × 197 projects = ~400k total components
- **Goal**: Enable fast similarity search for duplicate/clone detection and search-by-example
- **Key insight**: User needs component-level granularity, not just whole-file similarity

## Database Schema Design

### 1. Main Tables

#### `projects` - One row per JSON file
```sql
CREATE TABLE projects (
    project_id SERIAL PRIMARY KEY,
    company_name TEXT NOT NULL,
    file_name TEXT NOT NULL UNIQUE,
    export_date TIMESTAMPTZ,
    total_paths INTEGER,
    file_type_counts JSONB,
    raw_metadata JSONB,  -- Full metadata for reference
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### `components` - One row per component (leaf node)
```sql
CREATE TABLE components (
    component_id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(project_id),

    -- Path information
    full_path TEXT NOT NULL,              -- e.g., "BackofficeBidTabs/Dispensed Product/Non-579ef2aa"
    path_depth INTEGER,                    -- Nesting level (1-5)
    parent_path TEXT,                      -- Path of parent directory
    path_segments TEXT[],                  -- Array for hierarchy queries

    -- Component metadata (not for similarity)
    component_identifier TEXT,             -- From Configuration.json
    component_type TEXT,                   -- datePicker, select, grid, etc.
    definition_category TEXT,
    definition_name TEXT,

    -- Raw data (with noise removed)
    clean_config JSONB,                    -- Configuration.json minus noise keys
    raw_config JSONB,                      -- Full Configuration.json for reference

    -- Code content
    typescript_code TEXT,                  -- Concatenated .ts files
    sql_code TEXT,                         -- Concatenated .sql files
    html_template TEXT,                    -- .html files
    requirements_text TEXT,                -- req_requirements.txt

    -- Computed feature columns (for fast similarity)
    config_keys TEXT[],                    -- Sorted array of settings keys
    config_hash TEXT,                      -- MD5 of normalized config JSON
    code_hash TEXT,                        -- MD5 of concatenated code

    -- Position/layout (kept as structured data)
    position_col INTEGER,
    position_row INTEGER,
    position_width INTEGER,
    position_height INTEGER,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX idx_components_project ON components(project_id);
CREATE INDEX idx_components_type ON components(component_type);
CREATE INDEX idx_components_path ON components USING GIN(path_segments);
CREATE INDEX idx_components_config_keys ON components USING GIN(config_keys);
CREATE INDEX idx_components_config_hash ON components(config_hash);
CREATE INDEX idx_components_code_hash ON components(code_hash);
CREATE INDEX idx_components_full_path ON components(full_path);
```

#### `component_settings` - Normalized key-value pairs for flexible querying
```sql
CREATE TABLE component_settings (
    component_id INTEGER REFERENCES components(component_id),
    setting_key TEXT NOT NULL,
    setting_value JSONB,
    value_type TEXT,  -- 'string', 'number', 'boolean', 'object', 'array'
    PRIMARY KEY (component_id, setting_key)
);

CREATE INDEX idx_settings_key ON component_settings(setting_key);
CREATE INDEX idx_settings_value ON component_settings USING GIN(setting_value);
```

### 2. Noise Key Exclusion List

Based on analysis, these keys should be excluded from similarity calculations:

```sql
CREATE TABLE noise_keys (
    key_path TEXT PRIMARY KEY,
    reason TEXT,
    applies_to TEXT  -- 'metadata', 'config', 'all'
);

-- Populate with auto-detected noise
INSERT INTO noise_keys (key_path, reason, applies_to) VALUES
    -- Unique identifiers (different across clones)
    ('id', 'UUID - unique per component instance', 'config'),
    ('identifier', 'Auto-generated identifier', 'config'),

    -- Timestamps (irrelevant for functional similarity)
    ('exportDate', 'Export timestamp', 'metadata'),
    ('req_lastModifiedOn', 'Last modified timestamp', 'config'),
    ('req_lastModifiedBy', 'Last modified user', 'config'),

    -- File paths (environment-specific)
    ('parent_path', 'Absolute file path - environment specific', 'config'),
    ('sourceDirectory', 'Absolute directory path', 'metadata'),

    -- Status fields (workflow metadata)
    ('req_status', 'Workflow status code', 'config'),

    -- Position (layout, not functionality)
    ('position', 'Layout position - not functional similarity', 'config'),
    ('position.col', 'Column position', 'config'),
    ('position.row', 'Row position', 'config'),
    ('position.width', 'Width', 'config'),
    ('position.height', 'Height', 'config');
```

**Note**: Position is stored separately in structured columns but excluded from config similarity.

## Preprocessing Functions

### 1. JSON Cleaning Function

```sql
CREATE OR REPLACE FUNCTION clean_config_json(raw_config JSONB)
RETURNS JSONB AS $$
DECLARE
    cleaned JSONB;
    noise_key TEXT;
BEGIN
    cleaned := raw_config;

    -- Remove top-level noise keys
    FOR noise_key IN
        SELECT key_path FROM noise_keys WHERE applies_to IN ('config', 'all')
    LOOP
        cleaned := cleaned - noise_key;
    END LOOP;

    -- Remove settings.* noise keys
    IF cleaned ? 'settings' THEN
        FOR noise_key IN
            SELECT REPLACE(key_path, 'settings.', '')
            FROM noise_keys
            WHERE key_path LIKE 'settings.%'
        LOOP
            cleaned := jsonb_set(
                cleaned,
                '{settings}',
                (cleaned->'settings') - noise_key
            );
        END LOOP;
    END IF;

    RETURN cleaned;
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

### 2. Feature Extraction Function

```sql
CREATE OR REPLACE FUNCTION extract_config_keys(config JSONB)
RETURNS TEXT[] AS $$
    SELECT ARRAY_AGG(key ORDER BY key)
    FROM jsonb_object_keys(config->'settings') AS key;
$$ LANGUAGE sql IMMUTABLE;
```

### 3. Normalized Hash Functions

```sql
-- Config hash: deterministic JSON serialization
CREATE OR REPLACE FUNCTION compute_config_hash(config JSONB)
RETURNS TEXT AS $$
    -- Sort keys to ensure consistent ordering
    SELECT MD5(
        jsonb_pretty(
            jsonb_strip_nulls(config)
        )::TEXT
    );
$$ LANGUAGE sql IMMUTABLE;

-- Code hash: concatenated, whitespace-normalized
CREATE OR REPLACE FUNCTION compute_code_hash(
    ts_code TEXT,
    sql_code TEXT,
    html_code TEXT
)
RETURNS TEXT AS $$
    SELECT MD5(
        CONCAT(
            COALESCE(REGEXP_REPLACE(ts_code, '\s+', ' ', 'g'), ''),
            COALESCE(REGEXP_REPLACE(sql_code, '\s+', ' ', 'g'), ''),
            COALESCE(REGEXP_REPLACE(html_code, '\s+', ' ', 'g'), '')
        )
    );
$$ LANGUAGE sql IMMUTABLE;
```

## Data Loading Process

### Step 1: Load Projects

```python
# Python script to load projects table
import psycopg2
import json
from pathlib import Path

def load_projects(json_dir, conn):
    for json_file in Path(json_dir).glob("*.json"):
        data = json.loads(json_file.read_text())

        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (
                company_name, file_name, export_date,
                total_paths, file_type_counts, raw_metadata
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING project_id
        """, (
            data['metadata']['company'],
            json_file.stem,
            data['metadata']['exportDate'],
            data['metadata']['totalPaths'],
            json.dumps(data['metadata']['fileTypeCounts']),
            json.dumps(data['metadata'])
        ))

        project_id = cursor.fetchone()[0]
        conn.commit()

        # Now process components...
        load_components(data['paths'], project_id, conn)
```

### Step 2: Extract and Load Components

```python
def extract_component_from_path(path_data, full_path, parent_path=""):
    """Recursively extract components from nested paths"""
    components = []

    # Base component info
    config = path_data.get('files', {}).get('Configuration.json', {})

    component = {
        'full_path': full_path,
        'path_depth': full_path.count('/') + 1,
        'parent_path': parent_path,
        'path_segments': full_path.split('/'),
        'component_type': path_data.get('componentType') or config.get('componentType'),
        'component_identifier': config.get('identifier'),
        'definition_category': config.get('definitionCategory'),
        'definition_name': config.get('definitionName'),
        'raw_config': config,
    }

    # Extract code files
    files = path_data.get('files', {})
    component['typescript_code'] = '\n\n'.join([
        v for k, v in files.items()
        if k.endswith('.ts') and isinstance(v, str)
    ])
    component['sql_code'] = '\n\n'.join([
        v for k, v in files.items()
        if k.endswith('.sql') and isinstance(v, str)
    ])
    component['html_template'] = files.get('template.html', '')
    component['requirements_text'] = files.get('req_requirements.txt', '')

    # Extract position
    position = config.get('position', {})
    component['position_col'] = position.get('col')
    component['position_row'] = position.get('row')
    component['position_width'] = position.get('width')
    component['position_height'] = position.get('height')

    components.append(component)

    # Recursively process child paths
    for child_key, child_data in path_data.items():
        if child_key not in ['path', 'files', 'type', 'componentType']:
            if isinstance(child_data, dict):
                child_path = f"{full_path}/{child_key}"
                components.extend(
                    extract_component_from_path(child_data, child_path, full_path)
                )

    return components

def load_components(paths_data, project_id, conn):
    cursor = conn.cursor()

    for top_level_key, top_level_data in paths_data.items():
        components = extract_component_from_path(
            top_level_data,
            top_level_key
        )

        for comp in components:
            # Insert component
            cursor.execute("""
                INSERT INTO components (
                    project_id, full_path, path_depth, parent_path,
                    path_segments, component_identifier, component_type,
                    definition_category, definition_name, raw_config,
                    typescript_code, sql_code, html_template, requirements_text,
                    position_col, position_row, position_width, position_height,
                    clean_config, config_keys, config_hash, code_hash
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    clean_config_json(%s::jsonb),
                    extract_config_keys(%s::jsonb),
                    compute_config_hash(clean_config_json(%s::jsonb)),
                    compute_code_hash(%s, %s, %s)
                )
                RETURNING component_id
            """, (
                project_id, comp['full_path'], comp['path_depth'],
                comp['parent_path'], comp['path_segments'],
                comp['component_identifier'], comp['component_type'],
                comp['definition_category'], comp['definition_name'],
                json.dumps(comp['raw_config']),
                comp['typescript_code'], comp['sql_code'],
                comp['html_template'], comp['requirements_text'],
                comp['position_col'], comp['position_row'],
                comp['position_width'], comp['position_height'],
                json.dumps(comp['raw_config']),  # for clean_config
                json.dumps(comp['raw_config']),  # for config_keys
                json.dumps(comp['raw_config']),  # for config_hash
                comp['typescript_code'], comp['sql_code'], comp['html_template']
            ))

            component_id = cursor.fetchone()[0]

            # Populate component_settings table
            settings = comp['raw_config'].get('settings', {})
            for key, value in settings.items():
                # Skip noise keys
                if key not in ['req_lastModifiedBy', 'req_lastModifiedOn', 'req_status']:
                    cursor.execute("""
                        INSERT INTO component_settings
                        (component_id, setting_key, setting_value, value_type)
                        VALUES (%s, %s, %s, %s)
                    """, (
                        component_id,
                        key,
                        json.dumps(value),
                        type(value).__name__
                    ))

        conn.commit()
```

## Computed Columns for Similarity

### 1. Path-Based Features

Already computed during insert:
- `path_segments[]` - for hierarchical similarity (Jaccard on arrays)
- `path_depth` - for weighting (top-level paths more important)

### 2. Config-Based Features

Already computed during insert:
- `config_keys[]` - schema similarity (compare key sets)
- `config_hash` - exact duplicate detection (instant lookups)
- `clean_config` - for detailed comparison when needed

### 3. Code-Based Features

Already computed during insert:
- `code_hash` - exact code match detection
- Individual code fields (`typescript_code`, `sql_code`, etc.) - for MinHash/TF-IDF

### 4. Additional Similarity Columns (Optional)

For faster similarity queries, pre-compute these:

```sql
ALTER TABLE components
    ADD COLUMN config_vector TSVECTOR,
    ADD COLUMN code_vector TSVECTOR;

-- Full-text search vectors for semantic similarity
UPDATE components SET
    config_vector = to_tsvector('english',
        COALESCE(clean_config::TEXT, '')
    ),
    code_vector = to_tsvector('english',
        CONCAT(
            COALESCE(typescript_code, ''),
            ' ',
            COALESCE(sql_code, '')
        )
    );

CREATE INDEX idx_config_vector ON components USING GIN(config_vector);
CREATE INDEX idx_code_vector ON components USING GIN(code_vector);
```

## Similarity Query Patterns

### 1. Find Exact Config Duplicates (Instant)

```sql
-- Find all components with identical config (after noise removal)
SELECT c1.component_id, c1.full_path, c1.project_id,
       c2.component_id, c2.full_path, c2.project_id
FROM components c1
JOIN components c2 ON c1.config_hash = c2.config_hash
WHERE c1.component_id < c2.component_id
  AND c1.project_id != c2.project_id;  -- Cross-project only
```

### 2. Find Components by Example (Fast)

```sql
-- Given a component_id, find similar ones
WITH target AS (
    SELECT config_keys, component_type, clean_config, code_hash
    FROM components WHERE component_id = :target_id
)
SELECT
    c.component_id,
    c.full_path,
    p.company_name,
    -- Schema similarity (Jaccard on config_keys)
    (
        SELECT COUNT(*)::FLOAT / NULLIF(
            (SELECT COUNT(*) FROM unnest(c.config_keys) UNION SELECT COUNT(*) FROM unnest(t.config_keys)),
            0
        )
        FROM unnest(c.config_keys)
        INTERSECT
        SELECT unnest(t.config_keys)
    ) AS schema_similarity,
    -- Exact code match
    CASE WHEN c.code_hash = t.code_hash THEN 1.0 ELSE 0.0 END AS code_match
FROM components c
JOIN projects p ON c.project_id = p.project_id
CROSS JOIN target t
WHERE c.component_type = t.component_type  -- Same type only
  AND c.component_id != :target_id
ORDER BY schema_similarity DESC, code_match DESC
LIMIT 50;
```

### 3. Find Similar Code Snippets (MinHash - requires pgvector extension)

```sql
-- First, install pg_trgm for trigram similarity
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Find similar TypeScript code
SELECT
    component_id,
    full_path,
    similarity(typescript_code, :query_code) AS code_similarity
FROM components
WHERE typescript_code IS NOT NULL
  AND LENGTH(typescript_code) > 10
ORDER BY typescript_code <-> :query_code  -- Trigram distance
LIMIT 20;
```

## Performance Optimizations

### 1. Partitioning (Optional - for very large datasets)

```sql
-- Partition by project_id ranges
CREATE TABLE components_partitioned (
    LIKE components INCLUDING ALL
) PARTITION BY RANGE (project_id);

-- Create partitions
CREATE TABLE components_p1 PARTITION OF components_partitioned
    FOR VALUES FROM (1) TO (50);
CREATE TABLE components_p2 PARTITION OF components_partitioned
    FOR VALUES FROM (50) TO (100);
-- etc.
```

### 2. Materialized Views for Common Queries

```sql
-- Pre-compute component statistics per project
CREATE MATERIALIZED VIEW project_component_stats AS
SELECT
    p.project_id,
    p.company_name,
    COUNT(c.component_id) AS total_components,
    COUNT(DISTINCT c.component_type) AS unique_types,
    jsonb_object_agg(
        c.component_type,
        COUNT(*)
    ) AS type_distribution
FROM projects p
LEFT JOIN components c ON p.project_id = c.project_id
GROUP BY p.project_id, p.company_name;

CREATE UNIQUE INDEX ON project_component_stats(project_id);
```

## Summary

### What This Preprocessing Achieves:

1. **Granular component-level access** - Each component is a separate row (~400k rows)
2. **Noise elimination** - Auto-detected noise keys excluded from similarity
3. **Fast duplicate detection** - Hash-based instant lookups (config_hash, code_hash)
4. **Flexible similarity queries** - Multiple feature columns for different similarity metrics
5. **Search by example** - Find similar components given a target component_id
6. **Normalized settings** - Separate table for flexible key-value queries
7. **Code snippet search** - Full-text and trigram similarity on code fields

### Key Files to Create:

1. `/schema/01_create_tables.sql` - Table definitions
2. `/schema/02_create_functions.sql` - Cleaning/extraction functions
3. `/schema/03_create_indexes.sql` - Performance indexes
4. `/scripts/load_data.py` - ETL script using uv
5. `/queries/similarity_examples.sql` - Common query patterns

### Next Steps After Implementation:

1. Add pgvector extension for embedding-based similarity (Option 4 from report)
2. Implement MinHash LSH for fast approximate similarity at scale
3. Create similarity scoring functions that combine multiple metrics
4. Build materialized views for common clustering queries
