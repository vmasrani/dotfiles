# Recipe Aggregator Implementation Plan

## Current State
- Fresh Python 3.12 project
- `tabstack>=1.0.4` already in dependencies
- Basic project structure with pyproject.toml
- Empty main.py

## Requirements from receipe_agg.md
1. Extract recipes from cooking websites using Tabstack API
2. Store recipes in local JSON database
3. Provide CLI for add/list/search operations
4. Use two Tabstack endpoints:
   - `/v1/extract/json` - structured recipe extraction with schema
   - `/v1/extract/markdown` - clean text format

## User's Python Style Requirements (from CLAUDE.md)
- Use uv for everything
- Prefer uv scripts with inline dependencies and shebang
- Use list comprehensions (functional style)
- NO try-except blocks (fail loudly)
- Use pathlib over os
- Use mlh.hypers.Hypers for CLI args
- Small functions, comments only when non-standard

## Architecture Decision Needed

The Node.js version has 4 separate modules:
- extractor.js
- database.js
- search.js
- cli.js

**Option A: Package-based (use existing pyproject.toml)**
- Keep `src/extractor.py`, `src/database.py`, `src/search.py` as regular modules
- Create CLI script with uv shebang that imports from src/
- Pro: Clean separation, matches Node.js structure
- Con: Mixed paradigm (package + script)

**Option B: Single comprehensive script**
- One large `recipe_cli.py` with all functionality
- Pro: Fully aligns with uv script paradigm
- Con: Large file, harder to navigate

**Option C: Multiple independent scripts**
- Each command (add, list, search) as separate script
- Pro: Fully aligns with uv script paradigm
- Con: Code duplication, harder to maintain shared functionality

## Recommended Approach: Option A (Package-based)
Given that:
1. pyproject.toml already exists with tabstack dependency
2. The codebase is substantial (4 modules with different responsibilities)
3. User has existing package infrastructure

Structure:
```
recipe_agg/
├── src/
│   ├── __init__.py
│   ├── extractor.py    # Tabstack API integration
│   ├── database.py     # JSON storage with pathlib
│   ├── search.py       # Search/filter functionality
│   └── models.py       # Recipe dataclass
├── data/
│   └── recipes.json    # Database file
├── recipe_cli.py       # Main CLI with mlh.hypers
├── .env               # TABSTACK_API_KEY
└── pyproject.toml     # Updated with mlh dependency
```

## Implementation Steps

### 1. Update project dependencies
- Add `python-dotenv` for .env handling
- Add `machine-learning-helpers` from GitHub for mlh.hypers

### 2. Create data models (src/models.py)
- Recipe dataclass with all fields from schema

### 3. Implement extractor (src/extractor.py)
- RecipeExtractor class
- Methods: extract_recipe(), get_recipe_markdown()
- Use requests library for Tabstack API calls
- Read API key from environment

### 4. Implement database (src/database.py)
- RecipeDatabase class
- Methods: load_recipes(), save_recipes(), add_recipe(), get_recipe(), get_all_recipes(), delete_recipe(), get_stats()
- Use pathlib for file operations
- JSON serialization/deserialization

### 5. Implement search (src/search.py)
- RecipeSearch class
- Methods: search_by_text(), search_by_ingredient(), filter_by_time(), get_quick_recipes()
- Use list comprehensions for filtering
- Format_recipe() for display

### 6. Implement CLI (recipe_cli.py)
- Use mlh.hypers.Hypers for command-line args
- Subcommands: add, list, search
- No try-except, fail loudly
- Clean formatted output

### 7. Create .env template
- TABSTACK_API_KEY placeholder

## Files to Create/Modify
- `src/__init__.py` (new)
- `src/models.py` (new)
- `src/extractor.py` (new)
- `src/database.py` (new)
- `src/search.py` (new)
- `recipe_cli.py` (new)
- `.env` (new)
- `data/recipes.json` (new, empty initially)
- `pyproject.toml` (modify - add dependencies)
- `.gitignore` (modify - add .env)

## Implementation Details

### Dependencies to Add
```bash
uv add python-dotenv requests machine-learning-helpers --git https://github.com/vmasrani/machine_learning_helpers.git
```

### Data Models (src/models.py)
```python
@dataclass
class Recipe:
    id: str
    title: str
    description: str | None
    total_time: int | None  # in minutes
    servings: int | None
    ingredients: list[str]
    instructions: list[str]
    source_url: str
    imported_at: str
```

### Key Implementation Notes

**Extractor (src/extractor.py)**:
- Use requests.post() for Tabstack API calls
- Extract API key from os.environ (loaded via dotenv)
- Parse time strings to integers (e.g., "45 min" -> 45)
- Default schema matches Node.js version
- ID generation: slugify title + timestamp

**Database (src/database.py)**:
- Use pathlib.Path for all file operations
- Path("./data/recipes.json").read_text() / write_text()
- JSON serialization: dataclass_to_dict helper
- Duplicate detection: check source_url
- Use list comprehensions for filtering/searching

**Search (src/search.py)**:
- All filters use list comprehensions
- Case-insensitive text search: str.lower() + 'in' operator
- Ingredient search: any() with list comprehension
- Format function: build multi-line string with recipe details

**CLI (recipe_cli.py)**:
```python
@dataclass
class Args(Hypers):
    command: str  # add, list, search
    url: str = ""  # for add command
    query: str = ""  # for search command
    search_type: str = "text"  # text, ingredient, quick
```

### Testing Commands
```bash
# Add recipe
uv run recipe_cli.py --command add --url "https://www.seriouseats.com/recipe"

# List recipes
uv run recipe_cli.py --command list

# Search recipes
uv run recipe_cli.py --command search --query "tomato"
uv run recipe_cli.py --command search --query "chicken" --search_type ingredient
uv run recipe_cli.py --command search --search_type quick
```

## User Confirmation
User selected: Package-based structure ✓
