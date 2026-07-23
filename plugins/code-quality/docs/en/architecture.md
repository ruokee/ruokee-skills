# Skill Architecture

## Overview

Language-agnostic software quality: design principles, design patterns, refactoring (Fowler-style), programming paradigms, and agent configuration smells.

## Structure

```
code-quality/
├── SKILL.md
├── workflow/
│   ├── index.md
│   ├── fast-review.md
│   ├── full-review.md
│   └── analysis.md
└── references/
    ├── design-principles/
    │   ├── index.md
    │   ├── dry.md
    │   ├── rule-of-three.md
    │   ├── kiss.md
    │   ├── yagni.md
    │   ├── solid.md
    │   ├── grasp.md
    │   ├── law-of-demeter.md
    │   ├── tell-dont-ask.md
    │   ├── composition-over-inheritance.md
    │   ├── dependency-inversion.md
    │   ├── tdd.md
    │   ├── ddd.md
    │   └── deep-modules.md
    ├── design-patterns/
    │   ├── index.md
    │   ├── factory.md
    │   ├── abstract-factory.md
    │   ├── builder.md
    │   ├── strategy.md
    │   ├── observer.md
    │   ├── adapter.md
    │   ├── decorator.md
    │   ├── facade.md
    │   ├── command.md
    │   ├── state.md
    │   ├── visitor.md
    │   ├── repository.md
    │   └── unit-of-work.md
    ├── refactoring/
    │   ├── index.md
    │   ├── fowler-refactoring.md
    │   ├── code-smells.md
    │   ├── safe-refactoring.md
    │   ├── long-function.md
    │   ├── duplicated-code.md
    │   ├── primitive-obsession.md
    │   ├── feature-envy.md
    │   ├── shotgun-surgery.md
    │   ├── divergent-change.md
    │   ├── thin-wrapper-function.md
    │   ├── extract-function.md
    │   ├── inline-function.md
    │   └── move-function.md
    ├── programming-paradigms/
    │   ├── index.md
    │   ├── imperative.md
    │   ├── declarative.md
    │   ├── object-oriented.md
    │   ├── functional-core.md
    │   ├── data-oriented.md
    │   ├── event-driven.md
    │   ├── state-machine.md
    │   ├── resource-lifecycle.md
    │   └── async-concurrency.md
    └── agentic-coding/
        ├── index.md
        └── config-smells.md
```

## Domain Responsibilities

- **design-principles** — Judgment frameworks. Each principle document explains the principle, its assumptions, when it applies, when it conflicts with other principles, and how to evaluate code against it.
- **design-patterns** — Concrete named patterns. Each document explains the problem the pattern solves, typical implementation, when to use it, when not to use it, and how to identify misuse.
- **refactoring** — Fowler-style behavior-preserving improvement. Code smells, named refactorings, and the discipline of safe refactoring.
- **programming-paradigms** — Problem-shape to paradigm matching. Each paradigm document explains what it is, what it assumes, when it fits, and how to evaluate whether code uses it appropriately.
- **agentic-coding** — Configuration smells in agent rules, Skills, prompts, and workflow documents. Separate from code quality because the "code" being reviewed is configuration, not application logic.
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
