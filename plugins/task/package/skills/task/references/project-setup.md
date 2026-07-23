# Set Up Task Storage for a Project

Read this reference before initializing Task, when Core reports that a project is not initialized, or when project-root, storage-mode, registry, or Git-policy evidence conflicts.

## Contents

- [Decide before writing](#decide-before-writing)
- [Configuration](#configuration)
- [Initialize embedded storage](#initialize-embedded-storage)
- [Initialize detached storage](#initialize-detached-storage)
- [Understand project discovery](#understand-project-discovery)
- [Handle Git policy](#handle-git-policy)
- [Resolve setup failures](#resolve-setup-failures)
- [Respect migration boundaries](#respect-migration-boundaries)

## Decide before writing

Task storage always belongs to one project. Do not create a global unbound Task root, and do not let `task_create` silently initialize storage.

Before running init:

1. Resolve the intended project root. Use the Git root by default; in a monorepo, use the repository root unless the user deliberately wants another worksite boundary.
2. Choose `embedded` or `detached`.
3. For embedded storage, choose `ignore`, `track`, or `none` deliberately.
4. Check whether `.agents/task.yaml`, an embedded Task root, or a detached registry entry already exists.
5. Explain any new tracked/ignored files or global registry write, then obtain the user's agreement.

If Core returns `project_not_initialized` during create, stop that create operation and ask whether to initialize. The original top-level creation confirmation does not by itself choose a storage mode or Git policy.

## Configuration

Core merges configuration in this order:

```text
built-in defaults < user config < project config
```

User config:

```text
${XDG_CONFIG_HOME:-~/.config}/task/config.yaml
```

Optional project config:

```text
<project-root>/.agents/task.yaml
```

The project file is an override, not an initialization marker. It may be absent, empty, or an empty mapping. Only create it when the project needs a non-default value.

Managed settings:

| Setting | Default | Meaning |
| --- | --- | --- |
| `data_dir` | `${XDG_DATA_HOME:-~/.local/share}/task/` | detached data root |
| `mode` | `embedded` | `embedded` or `detached` |
| `task_root` | `.task` | embedded root relative to project root |
| `git_policy` | `ignore` | `ignore`, `track`, or `none` |
| `creation_policy` | `strict` | top-level creation policy |
| `wal_max_length` | `2000` | default WAL character budget |
| `wal_max_entries` | `20` | default WAL entry budget |

Core ignores unknown config fields. It validates every managed value it sees. `data_dir` expands `~` and must then be absolute; it does not expand arbitrary environment variables. `task_root` must remain inside the project and cannot contain a parent traversal.

Write a project override before init when init must use a custom `task_root`, `data_dir`, or creation policy. Do not hand-create managed Task data as a substitute for init.

## Initialize embedded storage

Embedded storage keeps the Task root inside the project, making Tasks easy to discover and open from an editor.

Typical local-only setup:

```bash
task-core init --project-root /absolute/project --mode embedded --git-policy ignore
```

Tracked Task state:

```bash
task-core init --project-root /absolute/project --mode embedded --git-policy track
```

Fully user-managed Git behavior:

```bash
task-core init --project-root /absolute/project --mode embedded --git-policy none
```

The resolved Task-root directory is initialization evidence. Core does not create a ROOT marker; a directory created by hand is also treated as initialized, even though Core cannot prove how it was created.

The default layout begins at:

```text
<project-root>/.task/
├── .cache/
└── YYYY-MM/DD/NN--<slug>/
```

After init, inspect the structured result and Git status. Do not assume a successful process created a project config file; Core only needs that file for overrides.

## Initialize detached storage

Detached storage keeps Task data under the user data directory while binding it to a project through the authoritative registry:

```text
${XDG_CONFIG_HOME:-~/.config}/task/projects.yaml
```

Initialize with the default project-directory basename as slug:

```bash
task-core init --project-root /absolute/project --mode detached
```

Or choose an explicit slug:

```bash
task-core init --project-root /absolute/project --mode detached --project-slug stable-project-name
```

The resulting root is:

```text
<data_dir>/<project_slug>/
```

Re-initializing the same canonical project path reuses its existing slug. If another project already owns the requested slug, Core returns `project_slug_conflict`; choose a meaningful alternative instead of inventing an implicit hash.

Treat `projects.yaml` as authoritative user-editable configuration, not a disposable index. If the project moves or is renamed, update the mapping deliberately. Core has no project-registry migration command.

`git_policy` does not make detached data part of the project repository. Treat the detached root and its backup/synchronization policy separately.

## Understand project discovery

Pass the current absolute workspace `cwd` on every Task tool call. MCP and package processes start from the plugin directory, which is not project context.

Core walks upward from cwd to the nearest consistent evidence, stopping at the Git root when one exists. Evidence includes an embedded Task-root directory and a detached registry mapping. Git itself is a search boundary and default init root, not proof that Task was initialized.

Core stops instead of guessing when the nearest evidence disagrees about root or mode. A worksite resolves to one project Task root; hierarchy and structured relations never cross project boundaries.

After changing worktrees or workspace directories, pass the new cwd. Do not persist a project or Task binding in host state.

## Handle Git policy

For embedded storage:

- `ignore` creates or appends `*` in the Task root's own `.gitignore`. If `.agents/task.yaml` exists, Core also appends that filename and `.gitignore` to `.agents/.gitignore`.
- `track` leaves normative Task data visible to Git while `.cache/` remains ignored.
- `none` makes no Git-management changes.

Core does not edit the project-root `.gitignore`, stage files, remove already tracked files, or commit. It appends idempotently and preserves existing content.

If `track` conflicts with an existing ignore rule or Task-root ignore file, Core stops. Show the conflict and let the user decide how to change Git state. Do not silently delete ignore rules or run `git rm`.

Check Git status after init and confirm that the observed tracked/ignored behavior matches the chosen policy.

## Resolve setup failures

Use the structured error and inspect only the relevant configuration and paths:

- `project_not_initialized`: confirm project root, mode, and Git policy before init.
- `root_conflict`: inspect the nearest project config, embedded root, and detached registry entry; do not choose one silently.
- `task_root_missing`: preserve the detached registry and determine whether the data root moved, was deleted, or was never synchronized.
- `project_slug_conflict`: select another explicit slug or correct a stale registry entry with user approval.
- `task_root_outside_project` or config errors: correct the managed setting; do not weaken the containment rule.
- `git_policy_conflict`: reconcile Git ignore/tracking state explicitly.

Do not edit Task IDs, generated Task directories, or managed frontmatter to fix project discovery. For damaged Task data after project discovery succeeds, read [Diagnostics and Repair](diagnostics-and-repair.md).

## Respect migration boundaries

Core does not migrate:

- embedded to detached or the reverse;
- one `task_root` to another;
- one Git policy to another;
- detached registry entries after a project move;
- data schemas.

Plan these as explicit, user-approved migrations. For Trellis data, read [Migrate Trellis Tasks](migrate-from-trellis.md); do not hand-construct destination Task metadata or paths.
