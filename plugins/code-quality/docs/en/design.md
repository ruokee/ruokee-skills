# Skill Design

## Original Requirements

This Skill aims to solve a specific problem: AI coding agents produce mediocre output when they lack domain-specific engineering judgment. Generic instructions like "follow best practices" or "write clean code" give agents nothing actionable. These Skills provide the structured knowledge that lets an agent make real engineering decisions about code quality.

The core requirements:

1. **Progressive disclosure** — The top-level `SKILL.md` is navigation only. It tells the agent what exists and when to read it. Detailed knowledge lives in leaf documents, loaded on demand by task signal.
2. **Each leaf must teach one concept exceptionally well** — Not a checklist. Not a summary. A leaf document should explain what a concept is, what problem it solves, how it is typically implemented, common variants, advanced usage, when it applies, when it does not apply, and how to evaluate whether existing code uses it correctly. A reader who finishes the leaf should have genuine understanding, not just a list of rules.
3. **Multiple workflows** — Fast review triggers after daily development for self-check. Full review must be explicitly requested. Analysis mode supports brainstorming, mechanism design, code analysis, and refactoring planning.
4. **Universal and portable** — These Skills are not tied to one repository or one person's preferences. Examples should be generic. Project-specific preferences are read from external files, never baked into the Skill itself.

## Design Philosophy

### Knowledge Before Rules

A leaf document is a complete reference on a topic, which happens to also support review. It is not a review checklist.

The Skill name is `code-quality`, not `code-quality-review`. It describes patterns, standards, and practices. Review is one workflow that uses this knowledge; analysis and design are others.

### Separation of Concerns

- **Skill documents** define universal engineering knowledge and judgment frameworks.
- **Workflow documents** define operational modes: how to conduct a fast review, full review, or analysis session.
- **Preferences** define project-specific and user-specific choices. They live outside the Skill in `.agents/preferences/` or equivalent locations.
- **Tools** handle mechanical enforcement. If a formatter, linter, or type checker can detect something, the Skill does not repeat it as a prompt rule.

### Progressive Disclosure

This Skill follows **Progressive Disclosure**.

```
SKILL.md          → Entry conditions, mode, routing table, output contract, stop rules
workflow/         → Operational mode definitions (fast-review, full-review, analysis)
references/       → Domain knowledge organized by topic
  domain/index.md → Directory boundary and routing (for human maintenance)
  domain/leaf.md  → Complete treatment of one concept
```

The agent reads `SKILL.md` first. It routes to the relevant workflow and leaf documents. It never loads everything at once.

### Leaf Quality Standard

Each leaf document must support the reader to:

- Understand what the concept is and what problem it solves.
- Recognize typical implementations and common variants.
- Identify when the concept applies and when it does not.
- Evaluate whether existing code uses it correctly.
- Spot risks, anti-patterns, and misapplications.
- Distinguish false positives from real problems.
- Formulate a minimum sufficient recommendation.

Leaf documents are read by both humans and AI agents. They must be accurate, complete, and clear enough for either audience.

### Preferences Mechanism

Skill support external preferences but contain no personal or project-specific opinions.

Discovery order:

1. Check the current project directory for `.agents/preferences/<skill-name>.md`.
2. If not found, check `.agents/preferences/<skill-name>/index.md`.
3. Check user-level directories such as `~/.codex/`, `~/.claude/`, or equivalent agent configuration locations.
4. If no preferences exist, proceed silently with generic guidance.

Preferences may define: architecture constraints, review priorities, or references to additional Skills.

Preferences cannot override system permissions, security rules, or explicit user instructions.

Output must distinguish preference-driven guidance from universal engineering facts.

## Key Boundaries

- `design-principles/` discusses judgment frameworks. `design-patterns/` discusses concrete implementations. A principle says "depend on abstractions"; a pattern says "here is how Factory solves a specific creation problem."
- `refactoring/` centers on Fowler's "smell + behavior-preserving technique." It is not a synonym for "code improvement."
- Agent-produced thin wrappers, premature abstractions, and wrong DRY belong in `refactoring/` or `design-principles/`, not in `agentic-coding/`. The `agentic-coding/` directory only covers configuration-level smells.

Additional:

- `programming-paradigms/state-machine.md` is the state machine reference. `design-patterns/state.md` covers only the GoF State Pattern as one OO implementation option.
- `programming-paradigms/resource-lifecycle.md` covers the universal concept. Language-specific implementation (e.g. Python `with`) just examples.

## Principles Summary

1. Leaf documents teach concepts completely; they are not just checklists.
2. Workflow documents define operational modes; they are not mixed into leaf content.
3. Preferences are external and clearly labeled; they never masquerade as universal facts.
4. Tools handle mechanical rules; the Skill handles judgment.
5. Progressive disclosure minimizes context load; the agent reads only what the task demands.
6. Examples are generic and universal; no specific repository code.
7. The Skill is portable across projects, agents, and users.
