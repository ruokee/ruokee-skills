# Skill Architecture

## Overview

Python-specific engineering: project shape, Python versions, dependencies, package layout, specifications (style, types, tests, docs, custom lint), grammar choices, standard library mechanisms, and tooling.

## Structure

```
python-engineering/
├── SKILL.md
├── workflow/
│   ├── index.md
│   ├── fast-review.md
│   ├── full-review.md
│   └── analysis.md
└── references/
    ├── project/
    │   ├── index.md
    │   ├── structure.md
    │   ├── python-version.md
    │   └── dependency-management.md
    ├── spec/
    │   ├── index.md
    │   ├── style.md
    │   ├── type-hint.md
    │   ├── testing.md
    │   ├── docstrings-api-docs.md
    │   └── custom-lint.md
    ├── grammar/
    │   ├── index.md
    │   ├── match-case.md
    │   ├── context-manager.md
    │   ├── decorator.md
    │   └── exception-groups.md
    ├── stdlib/
    │   ├── index.md
    │   ├── common.md
    │   ├── functools.md
    │   ├── itertools.md
    │   └── contextlib.md
    └── tooling/
        ├── index.md
        ├── uv.md
        ├── ruff.md
        ├── ty.md
        ├── mypy.md
        ├── basedpyright.md
        ├── pytest.md
        ├── coverage.md
        ├── pre-commit.md
        └── flake8-plugin.md
```

## Domain Responsibilities

- **project** — Project shape classification, Python version policy, package structure (src-layout, flat-layout, packaged application, workspace), and dependency management.
- **spec** — Coding specifications: style boundaries, type hints (syntax and annotation choices), type checking (tools and strategies), testing, documentation, and custom lint.
- **grammar** — Python grammar choices that affect design: structural pattern matching, context managers, decorators (syntax, higher-order functions, parameterized decorators, decorator classes), and exception groups.
- **stdlib** — Standard library mechanisms worth knowing as design choices, not just API reference.
- **tooling** — Tool responsibilities, configuration boundaries, command risks, and relationship to specifications.
- **workflow** — Operational modes. Fast review for daily self-check. Full review for explicit comprehensive assessment. Analysis for design discussion and exploration.

## SKILL.md Structure

`SKILL.md` files follow the section order:

1. **Entry Conditions** — When to activate this Skill.
2. **Mode Selection** — Default fast review; full review requires explicit request; analysis mode for discussion and design.
3. **Judgment Order** — Signal-to-leaf routing table and how to approach the problem before reading leaves.
4. **Preferences** — Discovery mechanism and usage rules.
5. **Output Contract** — Finding structure, separation of fact/judgment/preference.
6. **Stop Rules** — What the Skill must not do automatically.

For read-only requests (repository survey, "do not modify," external code analysis), `SKILL.md` states the constraint directly rather than delegating to a separate document.
