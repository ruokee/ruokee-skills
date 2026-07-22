# Migrate Trellis Tasks

Use this guide to migrate durable task state from `.trellis/tasks/` to embedded `.task/` storage. Keep `.trellis/` unchanged until the migrated Tasks have been verified and the user separately approves its removal.

## Contents

- [Scope](#scope)
- [Map the data](#map-the-data)
- [Migrate](#migrate)
- [Verify](#verify)
- [Cut over](#cut-over)

## Scope

Migrate task state and task-owned materials:

- `.trellis/tasks/<task>/task.json`
- `prd.md`, `research/`, handoffs, feedback, implementation or check logs, and other files owned by the task
- archived tasks under `.trellis/tasks/archive/`
- `.trellis/handoff/<task>/` when it clearly belongs to a migrated task

Do not treat `.trellis/spec/`, `.trellis/workspace/`, workflow scripts, session state, or runtime files as Task data. Move reusable project rules into the project's normal documentation or Agent instructions only as a separate, user-approved change.

There is no in-place format conversion. Create every destination through Task Core, then copy ordinary materials into the returned `task_dir`. Never construct Task paths, UUIDs, managed frontmatter, WAL files, or archive state by hand.

## Map the data

Inventory all source directories before writing anything. Parse `task.json` when present, but inspect the directory contents as well: older or manually migrated Trellis Tasks can contain useful state not represented in JSON.

Use these mappings:

| Trellis | Task | Rule |
| --- | --- | --- |
| `title` | `name` | Prefer the human title. Shorten it if it exceeds Task's 40-column or 96-byte limit, and preserve the full title in the body. |
| `description`, `prd.md` | `TASK.md` body or linked material | Keep the body as current truth. Preserve a substantial PRD as `prd.md` and link it from the body instead of duplicating it. |
| `branch` | `branch` | Omit null or stale branches. |
| `parent` / `children` | parent and subtasks | Recreate hierarchy by creating parents before children. Do not encode hierarchy as `related_to`. |
| `planning`, `in_progress` | `open` | Use `paused` only when the source evidence says work was deliberately paused. |
| `completed` | `closed` | Close after descendants have been created and closed. |
| `abandoned`, `cancelled` | `closed` | Record the original terminal state and reason; do not use force merely to represent it. |
| location under `tasks/archive/` | `archived: true` | Close first, then archive. Source status and source location are independent evidence. |
| `relatedFiles` | links in the body | Rewrite paths to copied task-owned materials. Keep project-file links as project-file links; do not copy their targets merely because they are listed. Report links into Trellis areas that are outside migration scope. |
| `priority`, `creator`, `assignee`, `base_branch`, `worktree_path`, commit or PR fields, `notes`, `meta` | body, ordinary material, or `extra.migration` | Preserve values that remain useful. Treat worktree paths as historical unless the worktree still exists. Do not invent first-class Task semantics for these fields. |
| `implement.jsonl`, `check.jsonl`, research and handoff files | ordinary files | Preserve raw history as material. Do not replay verbose historical logs into the WAL. |

Treat Trellis IDs and directory names as legacy references, not Task IDs. Store enough provenance to trace the migration, for example:

```json
{
  "extra": {
    "migration": {
      "source": ".trellis/tasks/06-16-example",
      "source_id": "example",
      "source_status": "in_progress",
      "source_created_at": "2026-06-16"
    }
  }
}
```

Task Core assigns a new UUIDv7 and `created_at`. Preserve the source creation time under `extra.migration`; do not overwrite the managed timestamp.

Resolve hierarchy from both sides. Trellis `parent` and `children` values may use an ID, a dated directory name, or an inconsistent legacy prefix. Build one source-directory-to-destination-ID map and report unresolved or contradictory edges instead of guessing. Do not infer `depends_on` or `related_to` from task order, nearby dates, branches, or prose.

Classify materials before copying. Trellis Task directories can contain complete workspaces, benchmark datasets, binary bundles, virtual environments, caches, and absolute symlinks in addition to durable documents:

- Preserve source, research, handoffs, decisions, scripts, configurations, compact results, and other non-reproducible task-owned material by default.
- Exclude reproducible caches and environments such as `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, compiled bytecode, and tool caches by default. Record every exclusion.
- Inventory large datasets, benchmark outputs, copied reference repositories, archives, binaries, and generated bundles by size. Ask the user whether to copy, leave in external storage with a link and checksum, or exclude them; size alone does not make them disposable.
- Do not dereference symlinks during migration. Recreate only intentional, portable relative symlinks. Record and exclude absolute, broken, environment-specific, or unclear links unless the user chooses another treatment.

Use Git-tracked files as useful evidence when the source project is a Git repository, but not as the whole inventory: untracked durable material may still matter, and some Trellis roots are not inside a Git worktree. For a nontrivial selection, write a migration manifest listing copied, linked, renamed, and excluded paths plus checksums for external large artifacts.

## Migrate

For a large migration, prefer a script for deterministic batch processing, then verify and confirm each migrated Task individually.

1. Confirm Task is installed and run `task-core --version`.
2. Initialize the project only after the user agrees. Choose the Git policy deliberately:
   - Run `task-core init --mode embedded --git-policy track` when the old task state was versioned and `.task/` should remain shared.
   - Run `task-core init --mode embedded --git-policy ignore` for local-only `.task/` state.
3. Do not silently accept the default policy during a migration. If the user instead wants detached storage or a custom `task_root`, stop using this `.task/` guide and plan that layout explicitly.
4. Inventory source Tasks, material sizes and symlinks; classify target status, archive state and material treatment; then resolve the complete parent-child graph.
5. Create all top-level Tasks with `task_create`. The user's explicit migration approval satisfies strict creation confirmation; pass `user_confirmed: true` only on that basis.
6. Create children with `task_create` using `type: "subtasks"` and the destination parent reference. Process the hierarchy from roots toward leaves. Batch siblings when they can be created atomically.
7. Record the returned `task_dir` and UUID for every source directory. Use only this map for later relations, lifecycle changes, file copies, and verification.
8. Copy the selected task-owned materials into each returned `task_dir` without changing the source and without dereferencing symlinks. Rename legacy `task.json` to `trellis-task.json` if preserving it; this distinguishes provenance from live Task state. Do not blindly recurse through a source directory.
9. Write or refine the `TASK.md` body with host file tools while leaving its YAML frontmatter unchanged. Link the preserved materials that a future Agent should read first.
10. Append one concise migration WAL entry with `task_log`. Include the source path, original status, migrated material summary, and any information intentionally not mapped. Do not replay `implement.jsonl` or `check.jsonl` entry by entry.
11. Recreate only explicit non-hierarchical relations with `task_update`, using destination UUIDs. Report relations whose targets were not migrated.
12. Apply terminal states from leaves toward roots with `task_update` transitions. Supply a reason such as `Migrated from completed Trellis task`. If the source requests a closed ancestor with an open descendant or otherwise violates Task lifecycle invariants, report the conflict and ask whether to keep the ancestor open, change a descendant's mapped state, or force the transition. Use force only for the user's explicit choice.
13. Archive Tasks whose source directories were under Trellis `tasks/archive/`, after they are closed. Preserve closed-but-unarchived Tasks as closed and unarchived.

For a single Task, follow the same sequence without building unrelated parts of the source tree. If it has a parent or children, ask whether to migrate the necessary connected hierarchy; flatten it only with the user's explicit choice.

## Verify

Run `task-core check`, then verify through Task Core rather than trusting the filesystem copy alone:

1. Use `task_find` with `include_archived: true` and compare the expected migrated count.
2. Use `task_read` on every migrated root and inspect topology, managed validation, status, archive state, branch, body, and recent WAL.
3. Confirm every migrated child has the intended parent and every explicit relation resolves to the new UUID.
4. Compare destination materials with the migration manifest or source inventory. Verify checksums when exact preservation matters. Account explicitly for renamed `task.json`, linked large artifacts, and every intentionally excluded path.
5. Search migrated bodies and materials for stale `.trellis/tasks/...` links. Rewrite links that should target migrated material; keep provenance references that are intentionally historical.
6. Confirm archived Tasks are closed and active source Tasks did not become archived merely because they were terminal.
7. Check Git status. Ensure the selected Git policy matches what is actually tracked or ignored and that no unrelated files were changed.

Stop and report discrepancies. Do not delete or rewrite the source to make verification pass.

## Cut over

Report the source-to-destination map, migrated and skipped Tasks, unresolved relationships, excluded materials, verification results, and the selected storage/Git policy.

Update project instructions, hooks, or entry points that still require Trellis only when that work is in scope. Task migration does not automatically replace Trellis specs, workflow automation, or session management.

Keep `.trellis/` during a review period. Removing it is a separate destructive action and requires explicit user approval after all migrated state and remaining non-Task responsibilities have been accounted for.
