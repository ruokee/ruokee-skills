# Presets, Agent Config, and Pane Naming

This reference owns the private preset schema and lifecycle, the `config.json` Agent registry, the pane-name sources, and the secret guard. Read it when creating, using, or maintaining a preset, when using `--name-suffix`, or when registering a new Agent type.

## Contents

- [Pane-name sources](#pane-name-sources)
- [Preset schema and location](#preset-schema-and-location)
- [Managing presets](#managing-presets)
- [The secret guard](#the-secret-guard)
- [config.json Agent registry](#configjson-agent-registry)
- [Failure and recovery](#failure-and-recovery)

## Pane-name sources

`launch` resolves the new pane name from exactly one of four mutually exclusive sources — there is no implicit precedence chain:

```text
launch [--cwd DIR] [--session SESSION | --split TARGET]
       (--preset PRESET [--name FULL | --name-suffix SUFFIX]
        | --name FULL -- ARGV...)
```

1. `--preset PRESET --name FULL` — use the full name verbatim.
2. `--preset PRESET --name-suffix SUFFIX` — look up the preset's `agent_type` in the current registry and build `<prefix>-<suffix>`.
3. `--preset PRESET` alone — use the preset's saved `pane_name`.
4. `--name FULL -- ARGV...` — direct argv launch; the full name is required.

Conflicts fail before the pane is created:

| Situation | Error |
| --- | --- |
| Both `--name` and `--name-suffix` | `pane_name_source_conflict` |
| `--name-suffix` without `--preset` | `name_suffix_requires_preset` |
| Preset `agent_type` has no configured prefix | `agent_prefix_not_configured` |

```bash
<skill-root>/scripts/launch-agent --preset ds-flash --name-suffix trans   # pi-trans
<skill-root>/scripts/launch-agent --preset ds-flash --name-suffix worker  # pi-worker
<skill-root>/scripts/launch-agent --preset ds-flash --name one-off-review # one-off-review
<skill-root>/scripts/launch-agent --preset ds-flash                       # the preset's pane_name
```

The prefix is resolved fresh from `config.json` on every suffix launch — it is never written into the preset, so changing a prefix does not require rewriting presets and does not change any preset digest. Changing a prefix never renames an existing pane. Suffix, prefix, and the final name are each validated as restricted ASCII, and the full name must still pass the 1–64 character pane-name rule. Duplicate readable names remain allowed; the controller refuses to guess when a name resolves ambiguously, so identify panes by the pane ID or run ID that `launch` returns. `restart` keeps the existing pane name and takes no name argument; `create` accepts only a full `--name`.

## Preset schema and location

Presets are private and live outside this repository:

```text
${XDG_CONFIG_HOME:-~/.config}/with-agents/presets/<name>.json
```

The schema is version 1:

```json
{
  "version": 1,
  "agent_type": "pi",
  "pane_name": "pi-default",
  "argv": ["pi", "--provider", "deepseek", "--model", "deepseek-v4-flash", "--thinking", "max"]
}
```

`pane_name` is only the default used when no naming argument is given. `argv` is the exact launch vector; the controller passes it to `execvp` and never runs it through a shell. There is no project-local preset inheritance. The repository must never contain a real preset — only schema, defaults, and examples.

## Managing presets

Create from the actual launch record of an owned pane, so the saved argv is the verified one rather than a recollection:

```bash
"$wa" preset save reviewer-model --from reviewer
"$wa" preset save reviewer-model --from reviewer --dry-run
"$wa" preset show reviewer-model
"$wa" preset list
```

`save` refuses an existing name with `preset_exists`. Updating stays one deterministic call but demands explicit replacement:

```bash
"$wa" preset update reviewer-model --from reviewer --replace   # --replace is required
"$wa" preset remove reviewer-model
```

Successful and `--dry-run` results include the normalized JSON, the actual argv, the target path, the source pane, and a SHA-256 digest. Writes are atomic. Do not mutate presets after an ordinary temporary launch unless the user asked for preset maintenance or already granted that scope.

## The secret guard

`preset save`/`update` refuse an argv that carries a credential-like flag or assignment — API keys, access or auth tokens, client secrets, passwords, and credentials — with `preset_secret_suspected`. This is a guard, not a full secret scanner: keep authentication out of argv entirely and let the target CLI use its own credential store or environment.

## config.json Agent registry

The registry maps an `agent_type` to a pane prefix and the executable basenames that identify it. It lives next to presets:

```text
${XDG_CONFIG_HOME:-~/.config}/with-agents/config.json
```

Because the controller stays Python 3.10+ and standard-library only, the file is JSON, not TOML:

```json
{
  "version": 1,
  "agents": {
    "codex": { "pane_prefix": "cdx" },
    "opencode": { "pane_prefix": "oc", "executables": ["opencode"] }
  }
}
```

The built-in table is always present without a file:

| agent_type | pane_prefix | executables |
| --- | --- | --- |
| `codex` | `cx` | `codex` |
| `claude` | `cc` | `claude` |
| `pi` | `pi` | `pi` |

Merge order is fixed: built-in defaults, then per-`agent_type` field override, then normalization, then a whole-table validation. A built-in type may override `pane_prefix` alone; an explicit `executables` list replaces the built-in list entirely rather than appending. A new type must supply both `pane_prefix` and at least one executable. One normalized executable basename may belong to only one type. `external` and `generic` are reserved and cannot be registered.

Registration has exactly two effects: `preset save`/`update` can record the new `agent_type` and generate suffix names for it, and — separately — a caller whose live foreground process matches a registered executable can receive a *generic* best-effort doorbell. Registration never grants the Codex/Pi specialized composer recognizer, a multiline-safety guarantee, or any TUI-acceptance claim. Those specialized capabilities remain code-defined; see [adapters.md](adapters.md).

The Agent kind is resolved by executable, never by scanning task text: the launcher is unwrapped for `env`, `node`, `nodejs`, `python`, `python3` (skipping options and env assignments) and the first real executable basename is matched. A task argument that merely mentions an Agent name cannot register a type.

## Failure and recovery

Missing config means the built-in table only; no config directory is created. A corrupt file, a symlink, an unknown version or field, an invalid value, a duplicate executable, or an incomplete new type makes config-consuming commands fail with `invalid_agent_config`. Commands that do not need the registry — `list`, `read`, `send`, full-name direct `launch`, preset-default `launch`, and `version` — keep working when the config is broken. `preset save`/`update` and suffix `launch` read the merged table and fail on an invalid one; `doctor` reports the problem.

There is no config-write command in this version. Maintain this low-frequency private file with an ordinary editor and an atomic replace. Neither the preset directory nor `config.json` is ever committed to the repository.
