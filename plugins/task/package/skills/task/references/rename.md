# Rename a Task Safely

Read this reference before every Task rename. Rename is a project-wide low-frequency CLI operation, not a `task_update` field change or a frontmatter-only edit.

## Contents

- [Understand rename invariants](#understand-rename-invariants)
- [Prepare the worksite](#prepare-the-worksite)
- [Run a dry-run](#run-a-dry-run)
- [Interpret reference updates](#interpret-reference-updates)
- [Resolve manual review](#resolve-manual-review)
- [Execute the rename](#execute-the-rename)
- [Verify the result](#verify-the-result)
- [Handle failures](#handle-failures)

## Understand rename invariants

Rename preserves:

- immutable UUIDv7;
- top-level creation-date partition;
- sibling/day sequence number;
- parent topology;
- status, archive, relations, body, materials, and historical WAL.

Rename changes:

- `TASK.md.name`;
- the leaf slug when the normalized slug changes;
- project references that Core can determine exactly;
- current WAL by appending one rename entry.

It does not leave an alias or symlink at the old path. It does not rewrite historical WAL. If the new name produces the same slug, only the display name and WAL change.

The new name follows the normal Task name constraints: NFC, trimmed, no NUL/newline, at most 40 display columns and 96 UTF-8 bytes. Core derives the slug; do not specify one.

## Prepare the worksite

Before dry-run:

1. Resolve the intended Task uniquely by full ID or clear path/name.
2. Confirm the rename is in scope and understand why the name should change.
3. Inspect Git and working-tree status so unrelated edits remain visible.
4. Identify external systems or untracked material that Core cannot scan.
5. Avoid running another project-wide Task operation concurrently.

Do not edit `TASK.md.name` or move the directory first. That creates a mismatch without updating references.

## Run a dry-run

Run from the project/worktree directory:

```bash
task-core rename <task-ref> <new-name> --dry-run
```

Use proper shell quoting for names and paths. The structured plan includes:

- Task ID;
- old/new name;
- old/new path;
- count of reference updates;
- `manual_review` entries.

Review the exact plan before any write. A dry-run does not reserve the destination; Core re-scans and revalidates under locks during execution.

## Interpret reference updates

Core scans project root and the full Task root while excluding `.git`, `.cache`, and historical WAL content. It considers supported text files and symlinks.

It can update exact references to the old absolute path and, when the Task is inside the project, exact project-relative paths. A symlink that resolves into the renamed Task can be retargeted.

Core does not promise semantic parsing of every possible reference format. Dynamic path construction, bare slugs, ambiguous prose, encoded paths, binaries, unsupported file types, external repositories, and remote systems may remain unresolved.

Treat `reference_updates` as exact replacements Core plans to make, not proof that every reference has been found.

## Resolve manual review

When `manual_review` is non-empty, default execution stops with `rename_manual_review_required`.

For each item:

1. Open the file or symlink without changing it.
2. Determine whether it refers to this Task, another object with the same slug, or historical prose.
3. Decide whether to update before rename, update after rename, or intentionally preserve it.
4. Record any external/manual follow-up that Core cannot perform.

Proceed with unresolved items only after the user explicitly accepts them. That agreement authorizes:

```bash
task-core rename <task-ref> <new-name> --allow-unresolved
```

It does not authorize deleting ambiguous references or unrelated edits. Show the remaining review items and expected consequences before asking.

## Execute the rename

If dry-run has no unresolved items:

```bash
task-core rename <task-ref> <new-name>
```

Add `--actor` with the most specific model information currently available, following the same best-effort actor rule as `task_log`.

Core acquires the project lock and all top-level Task locks in stable order, then re-resolves the Task, re-scans references, updates managed name, moves the leaf when needed, updates exact references, and appends a rename WAL entry.

Do not run a second rename merely because the path changed. Use the returned canonical `new_path` and immutable ID for follow-up.

## Verify the result

After success:

1. Read the Task by immutable ID and confirm name, path, parent, status, and relations.
2. Run `task-core check` from the project directory.
3. Inspect the returned `manual_review` list, even when unresolved continuation was authorized.
4. Search project and Task materials for stale old absolute/relative paths and intentional bare references.
5. Confirm symlink targets and important Markdown/wiki/reference links.
6. Inspect Git status and diff; ensure no unrelated file changed.
7. Confirm the rename WAL records old/new name, paths, update count, and manual-review count.

Do not edit historical WAL that still mentions the old path. It is historical evidence.

## Handle failures

- `directory_exists`: choose a clearer name or resolve the actual destination conflict; do not delete the target automatically.
- `rename_manual_review_required`: inspect and obtain user agreement before `--allow-unresolved`.
- `external_write_race`: re-read the changed file and repeat dry-run after reconciling edits.
- `lock_target_changed` or identity ambiguity: resolve the current Task by UUID/path again; do not guess.
- success with `committed: true` and `wal_write_failed`: the rename already happened. Verify by ID/new path, repair WAL, and append the missing entry; do not repeat rename.
- unexpected partial worksite after process/OS failure: stop, inventory old/new paths and all planned reference updates, and read [Diagnostics and Repair](diagnostics-and-repair.md). Core has no general rename rollback.
