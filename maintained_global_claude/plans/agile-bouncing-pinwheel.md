# JSON Similarity Analysis - Evaluation Report

**Date:** 2025-12-11
**Dataset:** 197 project JSON files (652 KB - 5.4 MB each)
**Purpose:** Evaluate approaches for measuring similarity to enable clustering, duplicate detection, ranking, and visualization

---

## Executive Summary

Your 197 JSON files represent different project configurations with a consistent structure (metadata + hierarchical paths) but varying content and nesting depths. Based on research of state-of-the-art approaches and analysis of your specific data, I recommend a **hybrid multi-metric approach** that combines structural and semantic similarity. This report presents 4 implementation options ranked from simplest to most comprehensive.

---

## Your Data Characteristics

### Structure Analysis
- **Format:** All files follow pattern: `{metadata: {...}, paths: {...}}`
- **Metadata:** Company name, export date, file counts (json, ts, txt, sql, html, scss)
- **Paths:** Deeply nested hierarchy (1-5 levels) representing directories and components
- **Size range:** 652 KB (Cryopeak) to 5.4 MB (HSii)
- **Average:** ~2,112 paths per file

### Content Types
1. **Structural:** Directory hierarchies, path names, nesting levels
2. **Configuration:** Component types (label, select, datePicker, button, etc.), settings, positions
3. **Code:** TypeScript functions, SQL queries, HTML templates
4. **Metadata:** Timestamps, file counts, company names

### Example Similarity Challenge
Looking at the sample files:
- **360EEC vs Acadian:** Very similar structure, nearly identical paths, slight config differences
- **CrescentES vs others:** Different TypeScript code in onLoad/onBeforeSave hooks
- Files vary in: number of paths (528-3873), component types, custom code

---

## Similarity Measurement Approaches

### 1. Path-Based Similarity (Simple & Fast)

**How it works:**
- Extract all path strings (e.g., "ActivityLogHeaders/Header/Date Picker-105c7fff")
- Compare sets using Jaccard similarity: `|paths1 ∩ paths2| / |paths1 ∪ paths2|`
- Optional enhancements: weight by depth, compare path prefixes

**Pros:**
- ✅ Very fast (seconds for 197 files)
- ✅ Simple to implement (~50 lines)
- ✅ Good for structural similarity
- ✅ No external dependencies

**Cons:**
- ❌ Ignores actual content (config values, code)
- ❌ Misses semantic similarity (different paths, similar purpose)
- ❌ Sensitive to naming differences

**Use case fit:**
- ✅ Clustering by architecture
- ⚠️ Duplicate detection (misses content changes)
- ✅ Fast ranking/search
- ✅ Initial exploration

**Estimated runtime:** ~30 seconds for all pairwise comparisons (19,503 pairs)

**Code complexity:** ~100 lines

---

### 2. Tree Edit Distance (Structural Shape)

**How it works:**
- Convert JSON to tree structure
- Compute minimum edit operations (insert, delete, relabel) to transform one tree to another
- Use algorithms like APTED (All Paths Tree Edit Distance) or Zhang-Shasha

**Pros:**
- ✅ Captures structural similarity beyond just paths
- ✅ Handles different nesting levels gracefully
- ✅ Well-researched algorithms with proven correctness
- ✅ More robust than simple path comparison

**Cons:**
- ❌ Computationally expensive (O(n³) worst case)
- ❌ Still ignores content (values, code)
- ❌ Requires external library (apted)
- ❌ Harder to interpret (what does distance=42 mean?)

**Use case fit:**
- ✅✅ Clustering by architecture
- ⚠️ Duplicate detection (still misses content)
- ✅ Ranking by structural similarity
- ✅ Finding architectural patterns

**Estimated runtime:** ~5-10 minutes for all pairs (with optimization)

**Code complexity:** ~150 lines

---

### 3. Configuration Content Similarity (Semantic)

**How it works:**
- Extract all configuration objects (componentType, settings, positions)
- Compare distributions of component types
- Compare settings keys (schema similarity)
- Compare settings values (content similarity)
- Combine using weighted average

**Pros:**
- ✅ Captures semantic similarity (what components do)
- ✅ Detects configuration changes
- ✅ Good for finding functional duplicates
- ✅ Interpretable (can show which configs differ)

**Cons:**
- ❌ Ignores code similarity
- ❌ Moderate complexity
- ❌ Slower than path-based

**Use case fit:**
- ✅✅ Duplicate detection (detects config changes)
- ✅✅ Clustering by functionality
- ✅ Finding projects with similar components
- ✅ Identifying configuration drift

**Estimated runtime:** ~2-3 minutes for all pairs

**Code complexity:** ~200 lines

---

### 4. Code Similarity (Content Analysis)

**How it works:**
- Extract TypeScript, SQL, HTML content
- Use MinHash for fast approximate similarity
- Optional: AST parsing for structural code similarity
- Optional: TF-IDF for token-based similarity

**Pros:**
- ✅ Captures code-level similarity
- ✅ MinHash is very fast for large codebases
- ✅ Finds projects with similar business logic
- ✅ Complements structural metrics

**Cons:**
- ❌ Requires additional libraries (datasketch)
- ❌ Code may be less important than structure for your use case
- ❌ AST parsing adds complexity
- ❌ May have noise (comments, formatting)

**Use case fit:**
- ✅ Finding code clones
- ✅✅ Detecting copy-paste projects
- ⚠️ Clustering (code may vary within similar structures)
- ✅ Identifying common patterns in business logic

**Estimated runtime:** ~1-2 minutes (MinHash), ~10+ minutes (AST-based)

**Code complexity:** ~150 lines (MinHash), ~300+ lines (AST)

---

## Recommended Implementation Options

### Option A: Simple Baseline (Recommended for Start) ⭐

**What you get:**
- Path-based Jaccard similarity
- Basic hierarchical weighting (top-level paths matter more)
- Similarity matrix (197×197)
- Simple clustering (hierarchical or k-means)
- Basic heatmap visualization

**Implementation:**
```python
# Single script, ~100 lines
- Load JSONs, extract paths
- Compute pairwise Jaccard similarity
- Generate similarity matrix
- Run clustering (sklearn)
- Plot heatmap (seaborn)
```

**Outputs:**
- `similarity_matrix.csv` - All pairwise similarities
- `clusters.json` - Cluster assignments
- `heatmap.png` - Visual similarity matrix

**Pros:**
- ✅ Fast to implement (1-2 hours)
- ✅ Fast to run (< 1 minute)
- ✅ No external libraries beyond numpy/pandas/sklearn
- ✅ Easy to understand and debug
- ✅ Good starting point to validate approach

**Cons:**
- ❌ Misses content similarity
- ❌ May group projects that differ only in configs

**Best for:** Quick exploration, validating the concept, fast iteration

**Runtime:** ~30 seconds total

---

### Option B: Hybrid Path + Config (Recommended for Production) ⭐⭐⭐

**What you get:**
- Path similarity (structure)
- Configuration similarity (component types, settings)
- Weighted fusion of both metrics
- Comprehensive clustering
- Multiple visualizations (heatmap, dendrogram, network graph)
- Duplicate detection with thresholds

**Implementation:**
```python
# Modular structure, ~300 lines
- Path metrics: Jaccard, prefix similarity, depth distribution
- Config metrics: component type distribution, settings comparison
- Fusion: configurable weights for different use cases
- Clustering: hierarchical + DBSCAN
- Visualizations: heatmap, dendrogram, network graph
```

**Outputs:**
- `similarity_matrix.csv` - Full matrix
- `detailed_scores.json` - Per-pair breakdowns (path score, config score, combined)
- `clusters_hierarchical.json` - Hierarchical clustering results
- `clusters_dbscan.json` - Density-based clustering
- `duplicates.json` - High-similarity pairs (> 0.95)
- `heatmap.png` - Clustered similarity matrix
- `dendrogram.png` - Hierarchical clustering tree
- `network_graph.png` - Similarity network (edges = high similarity)

**Pros:**
- ✅ Balanced accuracy and speed
- ✅ Captures both structure and content
- ✅ Highly interpretable (can see why projects are similar)
- ✅ Suitable for all use cases (clustering, duplicates, ranking, viz)
- ✅ Configurable weights for different priorities
- ✅ Production-ready

**Cons:**
- ❌ Moderate implementation effort
- ❌ Ignores code similarity (may matter for some duplicates)

**Best for:** Production use, comprehensive analysis, actionable insights

**Runtime:** ~3-5 minutes total

**Weight profiles:**
```python
# Clustering: emphasize structure
path: 0.35, config: 0.65

# Duplicate detection: emphasize content
path: 0.25, config: 0.75

# Fast search: emphasize structure
path: 0.60, config: 0.40
```

---

### Option C: Full Multi-Layer System

**What you get:**
- All 4 layers: path, tree edit distance, config, code
- Advanced fusion with multiple weight profiles
- Comprehensive analysis and reporting
- All visualizations + custom network analysis
- Validation metrics and confidence scores

**Implementation:**
```python
# Full system, ~500-700 lines
- Layer 1: Path-based (Jaccard, prefix, depth)
- Layer 2: Tree edit distance (APTED)
- Layer 3: Config similarity (type, keys, values)
- Layer 4: Code similarity (MinHash, token-based)
- Fusion: adaptive weighting
- Advanced clustering: hierarchical, DBSCAN, spectral
- Full visualization suite
```

**Outputs:**
- Everything from Option B, plus:
- `tree_edit_scores.json` - Structural edit distances
- `code_similarity.json` - Code-level similarities
- `report.md` - Comprehensive analysis report
- `per_cluster_analysis/` - Detailed cluster characteristics
- Interactive HTML visualizations

**Pros:**
- ✅✅ Most accurate and comprehensive
- ✅ Handles all edge cases
- ✅ Research-grade quality
- ✅ Extensible for future metrics
- ✅ Detailed interpretability

**Cons:**
- ❌ Significant implementation effort
- ❌ Longer runtime
- ❌ More dependencies (apted, datasketch)
- ❌ Potential overkill for your use case

**Best for:** Research, when accuracy is critical, large-scale production systems

**Runtime:** ~10-20 minutes total (with caching and parallelization)

---

### Option D: Research Report Only (Current) ⭐

**What you get:**
- This report
- Analysis of your data
- Evaluation of all approaches
- Recommendations
- No implementation

**Pros:**
- ✅ Immediate (done!)
- ✅ Helps you make informed decision
- ✅ No code to maintain

**Best for:** Evaluating options before committing

---

## Detailed Comparison Table

| Metric | Option A (Simple) | Option B (Hybrid) | Option C (Full) |
|--------|-------------------|-------------------|-----------------|
| **Implementation time** | 1-2 hours | 4-6 hours | 2-3 days |
| **Runtime (197 files)** | 30 sec | 3-5 min | 10-20 min |
| **Lines of code** | ~100 | ~300 | ~700 |
| **Dependencies** | numpy, pandas, sklearn, seaborn | + scipy | + apted, datasketch |
| **Clustering quality** | Good | Very good | Excellent |
| **Duplicate detection** | Fair | Very good | Excellent |
| **Interpretability** | Good | Excellent | Excellent |
| **Extensibility** | Limited | Good | Excellent |
| **Maintenance** | Easy | Moderate | Complex |

---

## Key Research Findings

### Academic Approaches
1. **Tree Edit Distance (Zhang-Shasha, APTED)**
   - Well-studied for XML/JSON comparison
   - O(m²n²) to O(n³) complexity
   - Good for structural similarity
   - Libraries: `apted` (Python), `tree-similarity` (Java/Python)

2. **Embedding-Based (SchemaEmbed)**
   - Use Word2Vec + autoencoders
   - Captures semantic relationships
   - Requires training on your domain
   - Complex, research-grade

3. **Graph-Based Approaches**
   - Treat JSON as graph
   - Use graph kernels or graph neural networks
   - Very accurate but computationally expensive
   - Overkill for your use case

### Industry Tools
1. **JsonCompare** (Python) - Good for pairwise comparison, not similarity scoring
2. **json-diff** (Python) - Difference detection, not similarity
3. **datasketch** (Python) - MinHash for fast approximate similarity
4. **scipy.spatial.distance** - Standard distance metrics

### Best Practices from Literature
1. **Combine multiple metrics** - No single metric captures all aspects
2. **Normalize by size** - Larger JSONs shouldn't dominate
3. **Use hierarchical weighting** - Top-level structure matters more
4. **Cache intermediate results** - 19,503 pairs take time
5. **Parallelize** - Embarrassingly parallel problem

---

## Specific Recommendations for Your Use Cases

### 1. Clustering Similar Projects
**Recommended:** Option B (Hybrid Path + Config)

**Why:**
- Need to group by both structure AND functionality
- Path similarity finds architectural patterns
- Config similarity finds functional patterns
- Combined gives best clusters

**Algorithm:** Hierarchical clustering with Ward linkage
- Produces dendrogram showing relationships
- Can cut at different heights for different granularities
- Natural for your nested data structure

**Expected outcome:** 5-15 clusters representing different project templates/types

---

### 2. Finding Duplicates/Near-Duplicates
**Recommended:** Option B with high config weight (0.75)

**Why:**
- Duplicates often have identical structure but slightly different configs
- Need to detect subtle differences
- Config + code similarity crucial

**Threshold:** similarity > 0.95 for likely duplicates, > 0.98 for almost certain

**Expected outcome:** 3-10 duplicate pairs (based on preliminary analysis suggesting projects like Cryopeak/Valence, Summit/SummitAus, Crimson/CrimsonUSA are very similar)

---

### 3. Ranking/Search (Find Similar to Query)
**Recommended:** Option A or B with high path weight (0.60)

**Why:**
- Speed matters for interactive search
- Structure is primary signal for "similar projects"
- Can pre-compute and cache similarity matrix

**Interface:**
```python
rank_by_similarity("MyProject.json", top_k=10)
→ Returns 10 most similar projects with scores
```

**Expected outcome:** Sub-second query time after initial computation

---

### 4. Visual Comparison/Analysis
**Recommended:** Option B or C

**Why:**
- Need multiple visualization types
- Heatmap: overall patterns
- Dendrogram: hierarchical relationships
- Network: communities and outliers

**Visualizations to generate:**
1. **Clustered heatmap** - Similarity matrix reordered by clusters
2. **Dendrogram** - Tree showing hierarchical relationships
3. **Network graph** - Nodes = projects, edges = high similarity
4. **Scatter plot** - 2D projection (t-SNE or UMAP) of similarity space
5. **Distribution plots** - Histogram of similarity scores

**Expected outcome:** Clear visual patterns showing project families and outliers

---

## Cost-Benefit Analysis

### Option A (Simple Path-Based)
- **Cost:** 1-2 hours implementation, minimal runtime
- **Benefit:** Fast insights, validates approach, enables quick iteration
- **ROI:** ⭐⭐⭐⭐⭐ (best for exploration)

### Option B (Hybrid Path + Config) ⭐ RECOMMENDED
- **Cost:** 4-6 hours implementation, ~5 min runtime
- **Benefit:** Production-ready, handles all use cases, interpretable
- **ROI:** ⭐⭐⭐⭐⭐ (best for production)

### Option C (Full Multi-Layer)
- **Cost:** 2-3 days implementation, ~20 min runtime, ongoing maintenance
- **Benefit:** Maximum accuracy, research-grade, extensible
- **ROI:** ⭐⭐⭐ (only if accuracy critical or research purpose)

---

## Implementation Roadmap (if choosing Option B)

### Phase 1: Core Metrics (2 hours)
1. JSON loader with validation
2. Path extraction and similarity
3. Config extraction and similarity
4. Simple fusion (weighted average)

**Milestone:** Can compute similarity between any two JSONs

### Phase 2: Pairwise Computation (1 hour)
1. Compute all 19,503 pairs
2. Build similarity matrix
3. Save to CSV/numpy
4. Add caching for re-runs

**Milestone:** Full similarity matrix computed and saved

### Phase 3: Clustering (1 hour)
1. Hierarchical clustering
2. DBSCAN clustering
3. Cluster assignment export
4. Cluster statistics

**Milestone:** Projects grouped into meaningful clusters

### Phase 4: Visualization (2 hours)
1. Heatmap with clustering
2. Dendrogram
3. Network graph
4. Summary statistics

**Milestone:** Visual insights ready for analysis

### Phase 5: Applications (1 hour)
1. Duplicate detection with thresholds
2. Ranking/search function
3. Cluster interpretation
4. Summary report generation

**Milestone:** Production-ready system

**Total: ~6-7 hours spread over 1-2 days**

---

## Sample Output Preview (Option B)

### Console Output
```
Loading 197 JSON files...
✓ Loaded (1.2s)

Computing pairwise similarities...
  Path similarity: 100% [====] (23s)
  Config similarity: 100% [====] (87s)
  Fusion: 100% [====] (5s)
✓ Complete (115s)

Performing clustering...
  Hierarchical: ✓ (8 clusters identified)
  DBSCAN: ✓ (12 clusters, 3 outliers)
✓ Complete (3s)

Detecting duplicates...
✓ Found 5 high-similarity pairs (>0.95)

Generating visualizations...
  Heatmap: ✓
  Dendrogram: ✓
  Network graph: ✓
✓ Complete (42s)

Total runtime: 3m 20s

Results saved to ./similarity_results/
```

### Summary Statistics File
```json
{
  "dataset": {
    "n_files": 197,
    "size_range_mb": [0.65, 5.43],
    "avg_paths": 2112
  },
  "similarity": {
    "mean": 0.42,
    "median": 0.38,
    "std": 0.18,
    "min": 0.08,
    "max": 0.98
  },
  "clusters": {
    "hierarchical": {
      "n_clusters": 8,
      "sizes": [87, 45, 18, 15, 12, 9, 8, 3]
    }
  },
  "duplicates": {
    "count": 5,
    "top_pair": {
      "project1": "Cryopeak",
      "project2": "Valence",
      "similarity": 0.947
    }
  }
}
```

---

## Risks and Limitations

### All Approaches
- **Assumption:** Similar structure/content = similar projects (may not always hold)
- **Challenge:** Determining optimal similarity threshold is subjective
- **Limitation:** Doesn't capture business context or project intent

### Path-Based (Option A)
- **Risk:** Misses important content differences
- **Mitigation:** Use as baseline, upgrade to Option B if insufficient

### Config-Based (Options B, C)
- **Risk:** Deep nested configs may have different semantics
- **Mitigation:** Weight different config levels appropriately

### Code-Based (Option C)
- **Risk:** Code similarity may not indicate project similarity
- **Mitigation:** Use lower weight for code metrics

### Performance
- **Risk:** Runtime grows quadratically with dataset size
- **Mitigation:** Parallelize, cache, or use approximate methods (MinHash LSH)

---

## Next Steps

### Immediate (Today)
1. **Decide on option:** A (quick), B (recommended), C (comprehensive), or defer
2. **If implementing:** Review technical requirements below
3. **If deferring:** Save this report for future reference

### Technical Requirements (for implementation)

**All options:**
```bash
uv add numpy pandas scikit-learn matplotlib seaborn
```

**Option B adds:**
```bash
uv add scipy networkx
```

**Option C adds:**
```bash
uv add apted datasketch plotly
```

### Validation Strategy
1. **Manual validation:** Pick 5-10 pairs, manually assess similarity, compare to scores
2. **Known pairs:** Identify known similar/dissimilar pairs, verify scores match intuition
3. **Cluster inspection:** Examine cluster members, verify they make sense
4. **Outlier review:** Check outliers, confirm they're truly different

---

## Conclusion

For your use case (197 project JSONs, multiple use cases, accuracy prioritized), I recommend **Option B (Hybrid Path + Config)** as the sweet spot:

✅ Handles all your use cases (clustering, duplicates, ranking, visualization)
✅ Balances accuracy and implementation effort
✅ Interpretable and actionable
✅ Fast enough for interactive use
✅ Room to extend if needed

**Start simple with Option A** if you want to validate the concept quickly, then upgrade to B.

**Choose Option C** only if you need research-grade accuracy or plan to publish findings.

---

## Sources & References

**Research Papers:**
- [Tree Similarity via Edit Distance](https://dl.acm.org/doi/10.1145/1066157.1066243)
- [Adaptable JSON Diff Framework](https://arxiv.org/pdf/2305.05865)
- [Leveraging Structural and Semantic Measures for JSON Document Clustering](https://www.researchgate.net/publication/369584982_Leveraging_Structural_and_Semantic_Measures_for_JSON_Document_Clustering)

**Libraries & Tools:**
- [tree-similarity (GitHub)](https://github.com/DatabaseGroup/tree-similarity)
- [APTED Algorithm](http://tree-edit-distance.dbresearch.uni-salzburg.at/)
- [JsonCompare (Python)](https://github.com/rugleb/JsonCompare)
- [JSON Diff Tool](https://jsondiff.com/)

**Algorithms:**
- Zhang-Shasha tree edit distance
- MinHash (Locality-Sensitive Hashing)
- Hierarchical clustering (Ward linkage)
- DBSCAN (density-based clustering)

---

**Report prepared by Claude Code**
**Data analyzed:** 197 files, 626 MB total
