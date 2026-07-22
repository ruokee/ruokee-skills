# Work Activity Log

Read this reference when deciding what to record, recovering older activity, handling WAL warnings or truncation, writing a handoff, correcting history, or responding to a committed update whose automatic WAL append failed.

## Contents

- [Use WAL for activity](#use-wal-for-activity)
- [Understand the file format](#understand-the-file-format)
- [Separate Core and Agent entries](#separate-core-and-agent-entries)
- [Decide what to log](#decide-what-to-log)
- [Write useful entries](#write-useful-entries)
- [Correct history by appending](#correct-history-by-appending)
- [Read within budgets](#read-within-budgets)
- [Handle handoff and session end](#handle-handoff-and-session-end)
- [Handle closed and archived Tasks](#handle-closed-and-archived-tasks)
- [Recover from WAL failures](#recover-from-wal-failures)

## Use WAL for activity

WAL means work activity log. Use it to preserve what happened while a Task advanced and why that history matters to future work.

Do not treat WAL as:

- the source of current Task status;
- a command transcript;
- an audit log with immutability guarantees;
- a replacement for plans, research, or large handoff files;
- an event stream that must replay into current state.

`TASK.md` body states current truth. WAL explains durable activity over time. Ordinary files hold detailed analysis, plans, checkpoints, and outputs.

## Understand the file format

Core appends to a file based on the system's current local date:

```text
<task-dir>/wal/YYYY-MM-DD.md
```

A canonical entry is:

```markdown
## 2026-07-21T15:04:05.123+08:00 · codex:gpt-5.6-sol

Completed Task discovery and reference resolution.

Optional multi-line detail.
```

Only a strict H2 line with timestamp and actor starts a parsed entry. The timestamp must include a timezone. A `task_log` message is a non-empty single-line summary; optional `extra_body` may contain multiple lines.

Actor must be a single line and must not contain ` · `. Prefer `codex:<model>`, `claude:<model>`, `pi:<model>`, or a subagent form such as `codex:<subagent-name>:<model>`. When exact context is unavailable, Core uses `<host>:unknown`.

Do not create entry IDs, JSON payloads, or end sentinels. Do not hand-build WAL when `task_log` can append safely.

## Separate Core and Agent entries

Core automatically records mechanical structured changes:

- Task creation;
- branch, relation, and `extra` changes;
- lifecycle transitions and archive actions;
- rename;
- parent summaries for batched subtask creation.

Do not duplicate those facts with an immediate `task_log` entry unless additional durable reasoning is needed.

Use Agent-authored entries for semantic activity that Core cannot infer:

- research findings and analysis outcomes;
- decisions and their downstream effects;
- meaningful user or external-tool changes;
- subagent and handoff results;
- discrepancies between Task prose and actual project state;
- unfinished session state and next step.

## Decide what to log

Log an activity when losing it at the next session would force rediscovery or could cause the wrong next action.

Usually log:

- a decision that changes scope or implementation direction;
- a finding that rules out an approach;
- a completed milestone whose result is not obvious from current files;
- an external change that explains why Task/project state moved;
- a blocker and the evidence needed to resume;
- a delegated result after the parent Agent verifies it;
- a concise session-end checkpoint for unfinished work.

Usually do not log:

- routine reads and searches;
- every shell command or tool call;
- temporary todo lists;
- speculative thoughts not used in a decision;
- status already auto-recorded by Core;
- repeated “still working” messages.

When detail belongs in an ordinary file, log the durable conclusion and link the file instead of copying its contents.

## Write useful entries

Make `message` a compact completed fact or current condition. Use `extra_body` only for information that changes interpretation or resumption.

Good pattern:

```text
message: Confirmed detached registry conflict comes from the old project path.
extra_body: Registry entry ... remains authoritative. Update it only after the user confirms the project move.
```

Weak patterns include “made progress,” a list of commands, or an entire discussion transcript.

Write one entry per coherent activity. `task_log` intentionally does not accept a batch of entries or an entry ID.

## Correct history by appending

WAL is append-only by convention and Core behavior. When an old entry is wrong:

1. Leave the old text intact.
2. Append a correction that identifies the affected conclusion.
3. State the new evidence and replacement conclusion.
4. Explain any downstream work that must change.

Do not rewrite yesterday's WAL to make the history appear error-free. Users may edit files manually, but Agents should preserve the activity record unless explicitly asked to repair accidental corruption.

## Read within budgets

`task_read` offers:

- `metadata`: no body or WAL;
- `summary`: body plus the first paragraph of selected WAL entries;
- `detailed`: body plus full selected WAL entries.

WAL has independent character and entry budgets. Defaults come from effective configuration. Core selects from newest to oldest and returns the selected entries in chronological order.

`wal_truncated: true` means more content exists on disk. If the latest single entry exceeds the character budget, Core may return a marked truncated entry. Increase budgets or read a specific WAL file only when the current decision needs more context.

Do not copy old WAL into `TASK.md` to avoid budgets. Keep current truth compact and load history progressively.

## Handle handoff and session end

Before ending with unfinished work, write one concise WAL entry that covers:

- what was completed;
- the current blocker or important decision;
- the next useful step.

If this would become a long entry, create a normal handoff/checkpoint file under `task_dir`, link it from `TASK.md` or WAL, and keep the WAL summary small.

A subagent assigned to a subtask writes only within its assignment boundary. It does not write the parent WAL; the parent Agent inspects the result and records the parent-level consequence.

## Handle closed and archived Tasks

`task_log` remains available for closed and archived Tasks so later facts, corrections, migration notes, or external outcomes can be preserved.

Logging does not reopen or unarchive a Task. Do not use an activity entry to imply a lifecycle transition; use `task_update` with the required reason and authorization.

Managed frontmatter must remain valid before Core will append WAL, even when the Task is closed.

## Recover from WAL failures

Core requires the WAL directory and target file to be normal writable filesystem objects. It rejects a symlink/non-directory WAL root, a symlink/non-regular target file, and non-UTF-8 existing content.

Unparsed manual text may produce `wal_unparsed_text` or timestamp warnings during read. Core may still append when the target is a regular UTF-8 file; preserve the manual text and diagnose whether it needs an explicit correction.

Structured Task state is committed before an automatic WAL append. If a create/update/rename result is successful with `committed: true` and `wal_write_failed`:

1. Do not repeat the original state-changing operation.
2. Re-read Task metadata to confirm the committed state.
3. Inspect the WAL path and exact warning.
4. Repair only the file condition with the user's authorization when data could be overwritten.
5. Append a concise missing activity entry after the WAL is safe.

For invalid UTF-8, symlinks, duplicate identity, or uncertain staging, read [Diagnostics and Repair](diagnostics-and-repair.md) before changing files.
