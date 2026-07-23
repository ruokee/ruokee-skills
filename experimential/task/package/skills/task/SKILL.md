---
name: task
description: Manage persistent project Tasks across Codex, Claude Code, and Pi. Use when the user explicitly asks to create a Task, names an existing Task by ID/name/path/branch, asks to resume or hand off durable multi-session work, or when a permissive project has an obviously sustained multi-stage effort. Do not use Task as a todo list, backlog, temporary plan, or implicit current-task tracker.
---

# Task

Use the five Task tools for durable project state. Treat Task files as user-owned state and the deterministic Core as the authority for managed metadata, relations, lifecycle, discovery, locks, and WAL appends.

## Invocation

Use the Task tools exposed by the current host as the primary interface. In Codex and Claude Code, prefer the registered MCP tools; in Pi, use the native Task tools. Do not shell out to `task-core invoke` when an equivalent host tool is available and working.

Use the CLI only as a fallback when the equivalent host tool is unavailable or broken, or for management commands that have no Task tool: `init`, `check`, `rename`, and `version`. State the reason before falling back for one of the five ordinary operations.

## Resolve a Task

Start every new session unbound. Do not infer a persistent current Task from the previous session.

Pass the current absolute workspace `cwd` on every Task tool call. The packaged MCP server starts from its plugin directory so that its runtime is portable; process cwd is therefore not project context. Re-resolve `cwd` after switching worktrees or directories.

1. When the user gives an ID, exact name, path, directory name, or branch, call `task_find` or `task_read`.
2. When the user only says “continue”, use cwd, branch, worktree changes, and `task_find` as evidence.
3. If resolution is ambiguous, show the candidates and ask the user. Never silently choose by similarity.
4. Read `summary` first. Use `detailed` only when older/full WAL content is needed. Use `metadata` for status and relation checks.
5. Read ordinary files under the returned absolute `task_dir` with the host file tools as needed. Core deliberately does not inventory Task materials.

Continuous turns in the same session may retain the resolved Task in context; do not persist that binding.

## Create

Top-level creation follows project `creation_policy`:

- Under `strict`, create only after the user explicitly requests or confirms creation in the current conversation; pass `user_confirmed: true` only for that fact.
- Under `permissive`, create for clearly sustained, multi-stage, or cross-session work and tell the user in the same turn. Never create for quick edits, one-off answers, ideas, ordinary TODOs, or work not yet chosen.
- If Core returns `project_not_initialized`, ask whether to run `task-core init`. Never hide initialization inside create.
- Creating subtasks inside an already assigned Task tree needs no new top-level confirmation. Use one batch for siblings that should be all-or-nothing.

Write the Task body as current truth, not a chronology. Put plans, analysis, checkpoints, and handoffs in ordinary files under `task_dir`, and link important entry points from `TASK.md`.

## Update and log

Use `task_update` only for branch, relation deltas, shallow `extra` changes, and one lifecycle action. Edit the `TASK.md` body and ordinary materials with host file tools. Never edit Core-managed frontmatter directly when the equivalent Core operation exists.

Use `task_log` for durable work activity: findings, decisions, corrections, recoverable milestones, verification and verified collaboration results, meaningful user/external edits, and blockers that change the next step. Append each durable result the moment it forms, before starting the next line of work; never defer it to a later milestone, test, or session end. Research or correction conclusions, the implementation milestone that follows, and the verification result that follows are distinct events at distinct boundaries. Merge only facts formed together in one semantic event; do not fold a later milestone or verification back into an earlier entry to save calls. Do not log command streams, routine reads, temporary plans, still-working status, or mechanical mutations Core already records. A session-end checkpoint fills only gaps; if it would be this session's only entry, you skipped event-boundary records, so backfill those distinct events first. Append corrections instead of rewriting historical WAL.

Set an actor from the most specific information currently available: an exact runtime `model.id`, then the exact model from the Agent's own context, then the most specific model or model family the Agent can justify, then `<host>:unknown`. Prefer forms such as `codex:<model>`, `claude:<model>`, `pi:<model>`, or `codex:<subagent>:<model>`. Do not downgrade a known precise model without reason; actor is best-effort field context, not an authenticated runtime proof.

All lifecycle transitions require a reason. Close normally only after descendants and dependencies are closed; use force only on the user's explicit request and preserve the bypassed checks. Archive only closed Tasks. Unarchive only after the user's current explicit agreement, then reopen separately if work should continue.

Rename only through `task-core rename`. Run `task-core rename <ref> <name> --dry-run` first. If unresolved references remain, show them and proceed with `--allow-unresolved` only after the user agrees.

## Assignment boundary

Runtime assignment is contextual, not stored:

- An Agent assigned to Task X may write X and its descendants; parent and siblings are read-only.
- An Agent assigned to a top-level Task may write the whole Task tree.
- A subagent assigned to a subtask does not write the parent WAL. The parent Agent records the observed result.
- This boundary applies to Task data, not normal project work files.

Before ending with unfinished work, append one concise WAL entry covering what changed, current blockers or decisions, and the next useful step. Create a normal handoff/checkpoint file only when the detail does not fit a useful WAL entry.

## References

Load only the reference needed for the current situation. Each reference is complete for its topic; routine operations should remain possible from this file alone.

- Read [Project setup](references/project-setup.md) before init, after `project_not_initialized`, or when storage, root, registry, configuration, or Git policy is unclear.
- Read [Task concepts](references/task-concepts.md) for nontrivial creation, `TASK.md` boundaries, hierarchy, relations, lifecycle, archive, or manual path changes.
- Read [Context](references/context.md) when resuming, resolving ambiguity, choosing read views, handling handoff/compaction, or assigning Task work to another Agent.
- Read [WAL](references/wal.md) when deciding what to record, reading longer history, correcting activity, or handling WAL warnings and committed state.
- Read [Diagnostics and repair](references/diagnostics-and-repair.md) before changing damaged or ambiguous Task data, and when check, validation, race, staging, or filesystem errors occur.
- Read [Rename](references/rename.md) before every Task rename.
- Read [Trellis migration](references/migrate-from-trellis.md) before migrating any `.trellis` Task state.
