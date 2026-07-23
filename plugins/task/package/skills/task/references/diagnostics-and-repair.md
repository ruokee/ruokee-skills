# Diagnose Task Data and Repair Safely

Read this reference when `task-core check` reports issues, a Task tool returns structural warnings or filesystem failures, managed validation blocks writes, or manual moves/edits leave Task state uncertain.

## Contents

- [Preserve evidence first](#preserve-evidence-first)
- [Use the available diagnostics](#use-the-available-diagnostics)
- [Separate warnings from blocking errors](#separate-warnings-from-blocking-errors)
- [Diagnose project and root failures](#diagnose-project-and-root-failures)
- [Diagnose Task identity and metadata](#diagnose-task-identity-and-metadata)
- [Diagnose relations and lifecycle](#diagnose-relations-and-lifecycle)
- [Diagnose WAL](#diagnose-wal)
- [Diagnose races and partial writes](#diagnose-races-and-partial-writes)
- [Repair only what is proven](#repair-only-what-is-proven)
- [Recognize unsupported recovery](#recognize-unsupported-recovery)

## Preserve evidence first

Do not “fix” a Task merely to make a warning disappear. Before any repair:

1. Stop state-changing Task operations.
2. Record the exact structured error, warning, paths, and candidate IDs without exposing unrelated data.
3. Inspect Git status or create a recoverable copy when the affected Task data is not otherwise recoverable.
4. Read the explicit Task path with `metadata` or `summary` when possible.
5. Determine which fields/files are authoritative and whether the intended identity is unique.
6. Ask the user before deleting, overwriting, moving, or resolving an ambiguous identity.

Prefer a minimal local repair over broad normalization. Preserve unknown frontmatter, body bytes, WAL history, ordinary materials, and unrelated Tasks.

## Use the available diagnostics

Run `task-core check` from the intended project/worktree directory. Current check reports:

- resolved project and Task roots;
- total Task candidates;
- duplicate UUIDs;
- invalid Task candidates;
- residual `.*.tmp` staging files;
- discovery warnings such as noncanonical paths or name/slug mismatch.

It does not automatically repair anything. It is not a schema migrator and does not exhaustively validate every relation or WAL entry.

Use `task_read` on a specific Task to inspect:

- `managed_valid` and validation errors;
- topology and missing relations;
- name/path warnings;
- WAL parsing warnings;
- current body and recent activity.

Use `task_find` warnings to locate invalid candidates hidden from the normal candidate list. Use a full ID or explicit path when a closed parent would otherwise hide a descendant.

## Separate warnings from blocking errors

Common non-blocking warnings:

- `name_slug_mismatch`;
- `noncanonical_task_path`;
- a missing `related_to` target;
- unparsed manual WAL text;
- WAL budget truncation.

These require interpretation but do not normally justify moving or rewriting data.

Blocking conditions include:

- duplicate UUID or ambiguous identity;
- invalid managed fields/schema/frontmatter;
- cross-project Task paths;
- relationship additions to unknown/self/cyclic targets;
- lifecycle preconditions;
- non-regular or non-UTF-8 WAL targets;
- external write races;
- project root/storage conflicts.

Do not convert a blocking error into a warning through manual edits unless the intended corrected state is proven.

## Diagnose project and root failures

For `project_not_initialized`, `root_conflict`, `task_root_missing`, registry, config, or Git-policy failures, load [Project Setup](project-setup.md).

Inspect the nearest project config, embedded root, detached registry entry, and current absolute cwd. Do not choose between conflicting roots by whichever contains more recent files.

Do not create a new empty root over a missing detached root before determining whether the original data exists elsewhere. Do not delete a stale registry entry without the user's agreement.

## Diagnose Task identity and metadata

For an invalid candidate, use its explicit path. Core may return body and validation errors even when the candidate cannot join topology or accept writes.

Check:

- exact full UUIDv7 and duplicate occurrences in the project;
- supported `schema_version`;
- name, status, archive, timestamp, relation-list, branch, reason, and `extra` types;
- duplicate YAML keys;
- unsafe custom YAML tags;
- frontmatter delimiters and UTF-8;
- whether `TASK.md` is a regular file.

Unknown top-level fields are valid and should be preserved. Do not delete them as cleanup.

Duplicate UUID is an identity conflict, not a formatting problem. Determine which Task, if either, owns the original identity and ask the user how the other should be reconstructed. Never assign a hand-written replacement UUID while pretending it came from Core.

For a valid Task whose name and path disagree, use rename when the name should change. If the user intentionally moved the directory, preserve UUID identity and treat the path warning as informational unless a canonical move is explicitly requested.

## Diagnose relations and lifecycle

Read `metadata` to inspect resolved topology, dependencies, dependents, related Tasks, and missing IDs.

- A missing dependency blocks normal close. Recover the intended Task or remove the relation only when the user confirms it is stale.
- A missing related target warns but does not block unrelated work. Preserve it when it is still useful provenance.
- A dependency cycle must be resolved by changing the actual dependency model, not by force-closing arbitrary Tasks.
- Open descendants or dependencies correctly block normal close.

Force close is a user-owned lifecycle bypass, not a repair command. Do not use it to make `check` green or hide corrupted descendants.

## Diagnose WAL

Inspect the exact `wal/` directory and target date file. Core requires:

- `wal/` to be a real directory, not a symlink;
- the date file to be a regular file, not a symlink;
- existing content to be UTF-8;
- canonical entries to have a timezone-aware H2 header.

Preserve unparsed manual text unless the user asks to normalize it. Add a correction rather than rewriting valid history.

If structured state was committed before automatic WAL failed, re-read state and repair only WAL. Do not repeat the original update. See [WAL](wal.md) for the committed-warning sequence.

## Diagnose races and partial writes

`external_write_race` means Core detected that the file changed after it was read. Re-read the newest file, compare the intended semantic change, and retry only after reconciling external edits. Do not overwrite using stale bytes.

`lock_target_changed` means the directory used for locking disappeared or changed before lock acquisition. Resolve the current path and identity again.

Residual `.*.tmp` staging files can result from interrupted atomic writes. Their presence does not prove which content should win. Compare them with the canonical file, timestamps, Git history, and operation result before deciding whether to preserve or remove them. Removal is destructive and requires the user's approval.

A crash during multi-file rename or batch placement may leave a partial worksite even though normal validation paths are atomic enough for intended use. Inventory the whole affected Task tree and references before any follow-up rename.

## Repair only what is proven

Use this order:

1. Restore project/root discovery without moving Task data unnecessarily.
2. Establish a unique Task identity.
3. Repair only invalid managed metadata required for Core to read the Task.
4. Re-read through Core and inspect topology/warnings.
5. Repair WAL filesystem conditions without rewriting history.
6. Run `task-core check` again.
7. Verify the Task with `task_read`, then inspect Git status and ordinary materials.
8. Append a WAL correction or repair note after logging becomes safe.

Use Core operations for any repair they can express. Manual frontmatter repair is a last resort for data Core cannot write while invalid; preserve YAML/body structure and request user direction when multiple values are plausible.

## Recognize unsupported recovery

Core does not provide:

- automatic repair or a `doctor` command;
- schema migration;
- embedded/detached or Git-policy migration;
- distributed conflict resolution;
- crash-safe multi-file transaction replay;
- automatic UUID conflict resolution;
- rollback of project-wide rename;
- exhaustive recovery for arbitrary manual corruption.

Report these boundaries honestly. Preserve evidence and offer a scoped recovery plan instead of inventing commands or rewriting broad collections of Task data.
