# Recover and Maintain Task Context

Read this reference when resuming work, resolving an ambiguous Task, choosing a read view, preparing a handoff or checkpoint, or assigning Task work to another Agent.

## Contents

- [Start unbound](#start-unbound)
- [Resolve from explicit references](#resolve-from-explicit-references)
- [Recover from worksite evidence](#recover-from-worksite-evidence)
- [Choose a read view](#choose-a-read-view)
- [Read ordinary materials](#read-ordinary-materials)
- [Continue within one conversation](#continue-within-one-conversation)
- [Apply assignment boundaries](#apply-assignment-boundaries)
- [Prepare handoff and compaction context](#prepare-handoff-and-compaction-context)
- [Handle difficult recovery](#handle-difficult-recovery)

## Start unbound

Treat every new session as unbound. Do not restore a current Task from the previous session, project, branch, worktree, recent Task, or host state.

Pass the current absolute workspace `cwd` on every Task tool call. The installed MCP server starts from its plugin directory, so process cwd is not project context. Recompute cwd after switching worktrees or directories.

An explicit user reference or a uniquely resolved request establishes only the current conversation's context. Do not persist that binding.

## Resolve from explicit references

When the user gives a full ID, exact name, path, directory name, or branch:

1. Use `task_read` directly for a unique ID/path/name/directory reference, or `task_find` when candidates need to be inspected.
2. Use the dedicated exact `branch` filter for branch evidence; do not hide it inside a fuzzy query.
3. If more than one Task matches, show compact candidates with name, status, path, branch, and full ID as needed.
4. Ask the user to choose. Never select by similarity or recency.
5. Read the selected Task with `summary` before loading detailed history.

Unique operations accept exact references; UUID prefixes are unsupported. A `task_find` query may return exact, prefix, or substring evidence, but a search result is not permission to guess among plausible Tasks.

Archived Tasks are excluded by default. Include archived Tasks deliberately when the user references one or the search is historical.

## Recover from worksite evidence

When the user only says “continue” or otherwise provides no durable reference, use evidence in this order:

1. current absolute project/worktree path;
2. current Git branch;
3. uncommitted changes and relevant files;
4. existing Task candidates from `task_find`;
5. names and material links that match the visible worksite.

Use evidence to find an existing Task, not to create a new one. If one Task is uniquely supported by strong evidence, read it and briefly state what was resolved. If evidence is heuristic or multiple Tasks remain plausible, ask before treating one as current.

Do not create a Task merely because no existing candidate was found. Top-level creation still follows project `creation_policy` and the user's actual intent.

Closed parents normally stop ordinary descendant discovery. A full descendant ID or explicit path can penetrate that boundary. Use this deliberately when repairing or reviewing a force-closed tree; do not make closed descendants part of ordinary active search.

## Choose a read view

Use the smallest sufficient view:

- `metadata`: inspect status, managed fields, parent/children, dependencies, related Tasks, warnings, and path without loading body or WAL.
- `summary`: recover normal work from metadata, the current body, and the first paragraph of recent WAL entries.
- `detailed`: inspect full selected WAL entries when the summary omits necessary reasoning or handoff detail.

WAL character and entry budgets are independent. A truncated response means older or longer activity remains on disk. Increase a budget or read specific WAL files only when the current decision needs it.

An explicit path read of a damaged candidate may return body and validation errors with `managed_valid: false`. Treat that as diagnostic context, not a writable Task.

## Read ordinary materials

Core returns the canonical absolute `task_dir` but does not inventory ordinary files. After reading `TASK.md`:

1. Follow the important material entry points in the body or recent WAL.
2. Inspect only files relevant to the current request.
3. Use project/Git state for code facts rather than expecting Task to contain a code snapshot.
4. Keep substantial plans, research, checkpoints, and outputs in ordinary files rather than expanding `TASK.md` or WAL indefinitely.

Task materials are user-owned. Preserve existing organization and links. Do not impose a fixed handoff filename or schema.

## Continue within one conversation

After a Task is uniquely resolved, semantically continuous turns in the same conversation may keep using it without repeating the ID. This is ordinary language context, not a persisted active Task.

Re-resolve when:

- the user names another Task;
- the topic changes materially;
- “this Task” could refer to more than one object;
- cwd/worktree changes;
- compaction removed the evidence needed to retain a unique reference.

Do not write current Task state into project config, Task frontmatter, WAL, or host metadata merely to preserve conversational convenience.

## Apply assignment boundaries

Runtime assignment is contextual and is not stored or enforced by Core:

- An Agent assigned to Task X may write X and its descendants.
- Parent and sibling Task data are read-only.
- An Agent assigned to a top-level Task may write the whole Task tree.
- This boundary applies to Task data, not normal project work files.
- A subagent assigned to a subtask does not write the parent WAL; the parent Agent records the observed result.

Give a delegated Agent a unique Task reference and the minimum necessary material entry points. Do not assume creating a subagent creates a subtask, or vice versa.

When integrating delegated results, inspect actual project and Task changes. Record the result at the appropriate Task level rather than copying tool chatter.

## Prepare handoff and compaction context

Before ending a session with unfinished work, append one concise WAL entry covering:

- completed work;
- current blocker or unresolved decision;
- the next useful step.

When that does not fit a useful WAL entry, create an ordinary handoff/checkpoint file under `task_dir` and link it from `TASK.md` or WAL. Include the current code/worktree references that a future Agent must inspect, but do not copy complete diffs or source files as backup.

If the host exposes imminent context compaction, make a best-effort checkpoint. A host that cannot signal compaction does not violate the Task contract; normal recovery must still work from current truth, materials, WAL, and the project worksite.

Read [WAL](wal.md) before logging a complex handoff or correcting historical activity.

## Handle difficult recovery

If Task state and the worksite disagree:

1. Treat files, Git, and current Core reads as facts.
2. Distinguish stale prose from structural metadata and actual code state.
3. Do not rewrite WAL history to make it appear consistent.
4. Update `TASK.md` body to current truth, then append a WAL correction explaining the observed change.
5. Ask the user when multiple Tasks, branches, or intended continuations remain plausible.

If warnings indicate invalid metadata, duplicate identity, missing roots, or filesystem races, stop normal recovery and read [Diagnostics and Repair](diagnostics-and-repair.md).
