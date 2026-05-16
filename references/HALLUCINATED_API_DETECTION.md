# Hallucinated API Detection via MCP — Feasibility Analysis

## Current limitation

vibe_check.py has ~15 hardcoded regex patterns for known non-existent APIs (e.g., `Promise.allResolved`, `os.path.mkdirs`). This catches maybe 5% of actual hallucinations. The real problem is that LLMs invent plausible-sounding methods that are specific to the libraries YOUR codebase uses — and those can't be hardcoded.

## What "real" hallucinated API detection looks like

The agent needs to answer: **"Does this method actually exist in the version of this library we're using?"**

That requires three things:
1. **Know what libraries are installed** (and their versions)
2. **Know what methods those libraries expose**
3. **Cross-reference method calls in the diff against that manifest**

## How MCP connections make this feasible

### Step 1: Extract the dependency manifest

With GitHub MCP access, the agent can read:
- `package.json` / `package-lock.json` (JS/TS) → exact versions
- `requirements.txt` / `Pipfile.lock` / `pyproject.toml` (Python)
- `go.mod` / `go.sum` (Go)
- `pom.xml` / `build.gradle` (Java)
- `Cargo.toml` / `Cargo.lock` (Rust)

**MCP tool**: `gh api repos/{owner}/{repo}/contents/package.json` or equivalent file read

### Step 2: Extract method calls from the diff

Already partially implemented in vibe_check.py. Needs enhancement:
- Parse `import { X } from 'library'` → know which library `X` comes from
- Parse `library.method()` calls → extract (library, method) pairs
- Handle aliased imports: `import pd from 'pandas'` → `pd.X` maps to `pandas.X`

This is deterministic — regex + import resolution, no ML needed.

### Step 3: Validate methods against library type stubs

This is the key question: **where do you get the list of valid methods?**

**Option A: Type definition files (BEST for JS/TS)**
- TypeScript `.d.ts` files in `node_modules/@types/` define every exported symbol
- With repo MCP access: read `node_modules/@types/{library}/index.d.ts`
- Or fetch from DefinitelyTyped GitHub repo for the pinned version
- Parse exported function/class/method names with regex
- **Feasibility: HIGH** — type stubs are structured, parseable, version-pinned

**Option B: Python type stubs + introspection**
- `typeshed` repo has stubs for stdlib + popular packages
- For installed packages: `pip show {package}` → location, then scan `.pyi` files
- Or use `inspect.getmembers()` programmatically
- **Feasibility: MEDIUM** — requires either runtime access or stub repo parsing

**Option C: Go doc**
- `go doc {package}` lists all exported symbols
- Or parse `pkg.go.dev` API for the pinned version
- **Feasibility: MEDIUM** — structured but requires either local Go or web API

**Option D: Java/Kotlin (hardest)**
- Parse JAR manifests or use `javap` decompiler
- Or query Maven Central API for class listings
- **Feasibility: LOW** — complex class hierarchies, reflection-heavy ecosystem

### Step 4: Cross-reference and flag

For each `(library, method)` pair extracted from the diff:
- Look up in the validated method manifest
- If not found: flag as potential hallucination with confidence based on:
  - Exact library version match → HIGH confidence
  - Fuzzy version match → MEDIUM confidence
  - No manifest available → LOW confidence (skip)

## Concrete implementation path using your MCP stack

Given you have MCP connections to: **GitHub repo, JIRA, Slack**

```
1. GitHub MCP → read package.json (or equivalent) → get dependency list + versions
2. GitHub MCP → read lockfile → get exact pinned versions
3. GitHub MCP → read PR diff → extract (library, method) pairs
4. For JS/TS: GitHub MCP → read @types/ files from node_modules or fetch from DefinitelyTyped
   For Python: GitHub MCP → read .pyi stubs or requirements.txt + typeshed lookup
5. Cross-reference: diff_methods ∩ manifest_methods → validated
                    diff_methods - manifest_methods → FLAGGED
6. JIRA MCP → check if flagged methods were discussed in linked tickets (reduces false positives)
7. Output: list of (file, line, method, library, expected_version, verdict)
```

## What you'd need to build

| Component | Effort | Deterministic? |
|-----------|--------|---------------|
| Dependency manifest parser (multi-language) | Medium | Yes |
| Import resolver (maps aliases to libraries) | Medium | Yes |
| Method call extractor (from diff) | Low (partially exists) | Yes |
| Type stub fetcher + parser (TS) | Low-Medium | Yes |
| Type stub fetcher + parser (Python) | Medium | Yes |
| Cross-reference engine | Low | Yes |
| JIRA context enrichment | Low | Yes |

Total estimate: ~2-3 days of focused work for JS/TS, another 2-3 for Python. Go/Java are harder.

## Is it worth it?

**Yes, but prioritize JS/TS first.** The TypeScript type system makes this almost trivially solvable — `.d.ts` files are literally a machine-readable manifest of every valid method. Python is next easiest via typeshed. Go is doable. Java is probably not worth the effort given reflection and dynamic proxies.

The hallucinated API signal would jump from confidence 0.4 to ~0.8 with this enhancement, and it's one of the most **specific** signals (low false positive rate when done right — a method either exists or it doesn't).
