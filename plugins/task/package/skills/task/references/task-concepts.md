# Task Concepts and Lifecycle

Read this reference when creating a nontrivial Task tree, editing `TASK.md`, changing relations or lifecycle, interpreting topology, or deciding whether work belongs in Task at all.

## Contents

- [Define the durable object](#define-the-durable-object)
- [Create top-level Tasks and subtasks](#create-top-level-tasks-and-subtasks)
- [Use stable identity and human references](#use-stable-identity-and-human-references)
- [Maintain names and paths](#maintain-names-and-paths)
- [Maintain TASK.md](#maintain-taskmd)
- [Organize ordinary materials](#organize-ordinary-materials)
- [Model relations](#model-relations)
- [Apply lifecycle transitions](#apply-lifecycle-transitions)
- [Handle archive](#handle-archive)
- [Update through the right surface](#update-through-the-right-surface)

## Define the durable object

A Task is a temporary effort the user has already decided to pursue and that benefits from durable state across sessions, agents, or context compaction. It belongs to one project and remains understandable without a particular model or host.

Do not use Task for:

- ideas, TODO capture, or backlog;
- one-off answers or quick edits;
- the host's temporary todo/plan;
- an implicit current Task;
- a global item with no project;
- code snapshots, synchronization, or external issue tracking.

Task files belong to the user. Let deterministic Core own managed metadata, relations, lifecycle, discovery, locking, and WAL appends. Use ordinary files for flexible task-owned material.

## Create top-level Tasks and subtasks

Top-level creation follows effective `creation_policy`:

- Under `strict`, create only after the user explicitly asks for or confirms a top-level Task in the current conversation. Pass `user_confirmed: true` only for that fact.
- Under `permissive`, create for work that is clearly sustained, multi-stage, or cross-session, and tell the user in the same turn.

Never create automatically for quick work, undecided ideas, ordinary TODOs, or work that has not started. If Core reports that the project is uninitialized, stop and read [Project Setup](project-setup.md).

Create subtasks inside an assigned Task tree without a new top-level confirmation. Use a single batch for sibling subtasks that should be created together. The parent must be open or paused; a batch contains 1..50 siblings and is all-or-nothing on normal validation failures.

Do not assume a subagent requires a subtask or that every subtask requires a subagent. Use subtasks when the work itself has a durable independent state or materials.

For ordinary creation, omit `created_at` so Core uses the actual creation time consistently. Set it only for a historical migration with a reliable timezone-aware original instant; read the migration guide before doing so.

## Use stable identity and human references

UUIDv7 is permanent identity. Names, directory paths, directory names, and branches are mutable human entry points.

Unique operations accept:

- a full UUIDv7;
- an absolute Task path or `TASK.md` path;
- a clear path relative to project root;
- an exact name;
- an exact directory name.

Do not use UUID prefixes. When a name or directory reference is ambiguous, show the candidates and ask the user. Never resolve by similarity, recency, or an assumed current Task.

Structured relations store full IDs, not names or paths. Use the absolute `task_dir` returned by Core for host file operations.

## Maintain names and paths

Core normalizes a Task name with NFC and trims outer whitespace. A name must be non-empty, contain no NUL or newline, fit within 40 display columns, and fit within 96 UTF-8 bytes.

Core derives the directory slug. Callers never supply a slug or destination directory. A directory collision fails instead of receiving a random suffix; choose a clearer name.

Top-level Tasks normally live at:

```text
<task-root>/YYYY-MM/DD/NN--<slug>/
```

Subtasks normally live at:

```text
<parent>/subtasks/NN--<slug>/
```

UUID is authoritative when a user moves a Task by hand. Core re-derives parent from the nearest valid ancestor and may emit `name_slug_mismatch` or `noncanonical_task_path`; these warnings do not normally block read/update/log. Duplicate UUID, cross-project paths, invalid managed fields, and destination conflicts do block writes.

Do not change `name` with `task_update` or by editing only frontmatter. Load [Rename](rename.md) before any name change.

## Maintain `TASK.md`

`TASK.md` contains managed YAML frontmatter and a user/Agent-maintained body.

Managed fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | current Task data schema |
| `id` | immutable UUIDv7 |
| `name` | display name |
| `status` | `open`, `paused`, or `closed` |
| `archived` | boolean; true only while closed; omitted means false |
| `created_at` | timezone-aware RFC 3339 timestamp |
| `branch` | optional branch name; existence is not guaranteed |
| `depends_on` | full same-project Task IDs; omitted means empty |
| `related_to` | full same-project Task IDs; omitted means empty |
| `last_transition_reason` | latest lifecycle reason |
| `extra` | optional shallow extension mapping |

Do not add parent, path, project, Task type, assignee, session, active state, revision, etag, or derived timestamps as new first-class semantics.

Use Core operations for managed fields whenever an equivalent operation exists. Core preserves unknown top-level fields and attempts to preserve YAML order, comments, quoting, anchors, and the exact body bytes while changing managed fields.

New Tasks use sparse frontmatter: Core omits `archived` while false and omits an empty `depends_on` or `related_to`. Archiving writes `archived: true` and unarchiving removes the node; adding the first relation creates the field and removing the last one deletes it. An explicit `archived: false` or `[]` in an older file stays valid, and an unrelated update never strips those defaults in passing. Read views still report `archived` as a boolean and relations as arrays, so callers never see the on-disk difference.

If managed fields or frontmatter are invalid, an explicit path read can return `managed_valid: false`, validation errors, and readable content. The candidate cannot join the relation graph, update, or log until repaired. Do not let Core overwrite duplicate keys, unsafe custom tags, or unparseable YAML; read [Diagnostics and Repair](diagnostics-and-repair.md).

Write the body as current truth. Replace “we used A and later changed to B” with the current choice B; record the change history in WAL. Keep the body compact enough to explain the current goal, scope, state, and important material entry points.

## Organize ordinary materials

Store plans, research, detailed decisions, checkpoints, handoffs, results, and other durable task-owned artifacts as ordinary files under `task_dir`. Link important entry points from the body or WAL.

Core deliberately does not inventory these materials. Read and edit them with host file tools. Do not put complete diffs or source copies in Task just to back up the codebase; Git and project files remain the code facts.

Task material symlinks may exist, but discovery never follows directory symlinks and `TASK.md` must be a regular file. Treat non-portable or unclear links as diagnostic concerns.

## Model relations

Task has three relation types:

| Relation | Representation | Effect |
| --- | --- | --- |
| parent/child | nearest valid ancestor directory | topology only; no automatic dependency or state cascade |
| dependency | `depends_on` full IDs | directed; blocks normal close until resolved and closed |
| related | `related_to` full IDs | non-lifecycle association |

Relations remain inside one project. Express cross-project weak context in prose rather than managed relation fields.

Use add/remove deltas through `task_update`; do not replace relation arrays from a stale read. Core rejects self-relations, unknown new targets, and dependency cycles. `related_to` is stored as a one-way outgoing list; read can derive `related_from` without writing the reverse edge.

A manually introduced missing dependency warns and blocks normal close. A missing related target warns but does not block other updates. Do not remove unresolved IDs merely to silence warnings without understanding the intended relation.

## Apply lifecycle transitions

The state machine is:

```text
open ⇄ paused
  │       │
  └───┬───┘
      ▼
    closed ──reopen──> open
```

Provide a non-empty reason for every transition. Core updates `last_transition_reason` and appends a mechanical WAL entry. Reopen always returns to open.

Before normal close, Core verifies recursively that:

- every descendant is closed;
- every dependency resolves and is closed;
- no dependency cycle prevents satisfaction.

Paused or missing dependencies are not complete. Related Tasks do not affect close.

Use force close only when the user explicitly asks to bypass the checks. Force closes only the target; it does not close descendants or dependencies. Core records the bypassed checks. A closed parent hides descendants from ordinary discovery, but a full ID, explicit path, or check can still reach them.

When close is blocked, present the descendants/dependencies/cycle evidence. Do not silently convert force into a cleanup mechanism.

## Handle archive

Archive is a boolean orthogonal to the three states and never moves the Task directory.

- Archive only a closed Task and provide a reason.
- Do not reopen an archived Task.
- Unarchive only with a reason and the user's current explicit agreement.
- After unarchive, the Task remains closed. Reopen separately if work should continue.

Consider creating a new related Task instead of reopening when preserving the old completion boundary is more useful.

## Update through the right surface

Use `task_update` for:

- branch set/clear;
- dependency and related add/remove deltas;
- shallow `extra` set/remove;
- at most one lifecycle action.

Edit the `TASK.md` body and ordinary materials with host file tools. Use rename CLI for names. Use `task_log` for durable work activity. When an update returns `changed: false`, do not add a mechanical WAL record for a change that did not occur.

If a committed update reports WAL failure, do not repeat the update. Read [WAL](wal.md) and repair only the missing activity record.
