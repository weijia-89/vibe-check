# Measuring "Code Submitted Without Understanding" — The Ultimate Cause

## The proxy problem

vibe_check.py measures **"was this code AI-generated?"** as a proxy for the actual risk: **"did the author submit code they don't understand?"** These are different things:

- AI-generated code that the author fully understands → **low risk** (good use of tools)
- Human-written code the author copied from Stack Overflow without understanding → **high risk**
- AI-generated code submitted as-is with no review → **highest risk**

The proxy catches case 3, misses case 2, and false-alarms on case 1. Can we do better?

## What "understanding" actually means (operationalized)

An author "understands" their code if they can:
1. **Explain** why each design decision was made (not just what the code does)
2. **Predict** failure modes — what breaks under edge cases, load, bad input
3. **Modify** the code to meet a changed requirement without starting over
4. **Debug** it when something goes wrong in production
5. **Integrate** it with existing codebase patterns and conventions

## Measurable signals of understanding (via MCP)

### Signal A: PR description quality (GitHub MCP)
**What to measure**: Does the PR description explain *why*, not just *what*?
- Ratio of "what" language ("adds endpoint", "creates component") to "why" language ("because users need X", "to handle the case where Y")
- Presence of: design alternatives considered, tradeoff discussion, test plan
- Length relative to diff size (0-line description for 500-line PR = red flag)
- **Confidence: MEDIUM** — some teams don't use PR descriptions

### Signal B: Review conversation depth (GitHub MCP)
**What to measure**: How does the author respond to review comments?
- Does the author explain their reasoning when questioned, or just say "fixed"?
- Do they push back with technical arguments, or comply without discussion?
- Ratio of substantive replies to "done"/"fixed"/"addressed" replies
- Do they ask clarifying questions about the codebase?
- **Confidence: MEDIUM-HIGH** — strong signal but depends on team review culture

### Signal C: Commit iteration pattern (GitHub MCP)
**What to measure**: Was the code written incrementally or dumped in one shot?
- Number of commits: 1 giant commit = suspicious; 5-10 incremental = more likely understood
- Commit message progression: do they show evolving thinking? ("start with X", "refactor to handle Y", "fix edge case Z")
- Force-push frequency: lots of force pushes might mean "regenerated and replaced" vs "iterated"
- Time between commits: all within 2 minutes = likely AI batch; spread over hours = likely manual
- **Confidence: MEDIUM** — gaming is easy (just split AI output into fake commits)

### Signal D: JIRA ticket alignment (JIRA MCP)
**What to measure**: Does the code actually solve what the ticket asked for?
- Extract requirements from JIRA ticket (acceptance criteria, description)
- Compare against what the PR actually implements
- Look for: requirements addressed vs missed, scope creep (PR does more than ticket asked), ticket context reflected in code structure
- **Confidence: LOW-MEDIUM** — requires NLP comparison, not fully deterministic

### Signal E: Post-merge behavior (GitHub MCP, longitudinal)
**What to measure**: What happens after the PR is merged?
- Does the same author fix bugs in this code, or does someone else?
- Time-to-first-bug-fix for code in this PR
- Does the author revert/rewrite significant portions within 2 weeks?
- **Confidence: HIGH (retrospective)** — but only available after the fact

### Signal F: Codebase familiarity indicators (GitHub MCP)
**What to measure**: Has this author worked in this area of the codebase before?
- Git blame analysis: has author previously modified files in the same directory?
- Import patterns: does the PR use the same utilities/patterns as existing code in that module?
- Naming consistency with surrounding code (not just internal consistency)
- **Confidence: MEDIUM-HIGH** — strong contextual signal

## A skill for this: "Understanding Score"

Yes, this could be a skill. Here's the design:

### Architecture
```
understanding-check/
├── SKILL.md
├── scripts/
│   ├── pr_understanding.py      — Orchestrator
│   ├── description_analyzer.py  — Signal A
│   ├── review_depth.py          — Signal B  
│   ├── commit_pattern.py        — Signal C
│   ├── ticket_alignment.py      — Signal D (needs JIRA MCP)
│   └── codebase_familiarity.py  — Signal F
└── references/
    └── RESEARCH.md
```

### How it would work

1. Takes a PR number
2. Fetches via GitHub MCP: PR description, review comments, commit history, file blame
3. Fetches via JIRA MCP: linked ticket (if any) with acceptance criteria
4. Computes understanding signals A-D and F
5. Outputs an "Understanding Score" (0-100) alongside the vibe_check AI probability
6. The combined report would look like:

```
AI Generation: 65% (Grade D)
Understanding:  30% (Low)
→ RISK: HIGH — likely vibe-coded with minimal review

vs.

AI Generation: 70% (Grade D)  
Understanding:  85% (High)
→ RISK: LOW — AI-assisted but author demonstrates comprehension
```

### The key insight

**AI probability × (1 - Understanding) = Risk**

A high AI score with high understanding = productive AI usage. A high AI score with low understanding = vibe coding risk. This reframes the tool from "catching AI users" to "catching risky submissions."

## What would it take to build?

| Component | MCP needed | Effort | Deterministic? |
|-----------|-----------|--------|---------------|
| Description analyzer | GitHub | 1 day | Mostly (keyword/ratio based) |
| Review depth scorer | GitHub | 2 days | Mostly (reply classification) |
| Commit pattern analyzer | GitHub | 1 day | Yes |
| Ticket alignment | JIRA | 2-3 days | Partially (needs semantic comparison) |
| Codebase familiarity | GitHub | 1-2 days | Yes (git blame + file history) |
| Orchestrator + report | — | 1 day | Yes |

**Total: ~8-10 days.** Signals A, C, and F are fully deterministic. B is mostly deterministic. D needs some NLP help (or an LLM call for semantic comparison, which is fine in a skill context).

## Honest assessment

This is a harder problem than AI detection. "Understanding" is a cognitive state; we can only measure behavioral proxies. The strongest signals (review conversation depth, post-merge behavior) are the hardest to game. The weakest (PR description, commit pattern) are trivially gameable.

A combined vibe_check + understanding_check would be significantly more useful than either alone, because it separates the question "was AI used?" from the question that actually matters: "does the author know what they shipped?"
