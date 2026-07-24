# Presets, Agent config, and pane naming

This reference owns the private preset schema and lifecycle, the `config.json` Agent registry, the pane-name sources, and the secret guard. Read it when saving, using, or maintaining a preset, when using `--name-suffix`, or when registering a new Agent type.

## Contents

- [Pane-name sources](#pane-name-sources)
- [Preset schema and location](#preset-schema-and-location)
- [Managing presets](#managing-presets)
- [The secret guard](#the-secret-guard)
- [config.json Agent registry](#configjson-agent-registry)
- [Failure and recovery](#failure-and-recovery)
- [Reference routing](#reference-routing)

## Pane-name sources

`launch` resolves the new pane name from exactly one source, in this order:

1. explicit `--name FULL` — use the full name verbatim;
2. `--preset PRESET --name-suffix SUFFIX` — look up the preset's `agent_type` prefix in the registry and build `<prefix>-<suffix>`;
3. `--preset PRESET` with a saved `pane_name` — use that name;
4. otherwise — generate `<prefix>-NNNN`, where `NNNN` is four random digits chosen once, with no live-name check and no retry.

```bash
"$wa" launch --preset ds-flash                       # the preset's pane_name, or a generated <prefix>-NNNN
"$wa" launch --preset ds-flash --name-suffix trans   # pi-trans
"$wa" launch --preset ds-flash --name one-off-review # one-off-review
"$wa" launch --name scratch -- some-cli --flag       # direct argv, explicit name
```

Conflicts fail before the pane is created:

| Situation | Error |
| --- | --- |
| Both `--name` and `--name-suffix` | `pane_name_source_conflict` |
| `--name-suffix` without `--preset` | `name_suffix_requires_preset` |
| Preset `agent_type` has no configured prefix | `agent_prefix_not_configured` |

A generated prefix is exactly two ASCII alphanumeric characters, resolved fresh from the registry on every launch — it is never written into the preset, so changing a prefix never rewrites presets or renames an existing pane. A generated `--name-suffix` is exactly 1–6 ASCII alphanumeric characters, and the random tail is fixed at four digits; the resulting name must still pass the 1–64 restricted-ASCII rule. An explicit `--name` and a preset's own `pane_name` are the escape hatch and only have to satisfy that 1–64 rule.

A `launch --split TARGET` does not create a window and takes no name of its own — the new pane inherits the live `window_name` of the target's window. A preset's saved `pane_name` does not apply in a split launch, and a direct-argv split launch requires no name. Combining `--split` with `--name`/`--name-suffix` is rejected before the pane is created.

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

`agent_type` and `argv` are required; `pane_name` is optional, and omitting it leaves the field out of the JSON. A preset saves no cwd. `argv` is the exact launch vector; the controller passes it to `execvp` and never runs it through a shell. The repository must never contain a real preset — only schema, defaults, and examples.

## Managing presets

Save and update take explicit configuration — nothing is inferred from a live pane or a foreground process:

```text
preset save   PRESET [--dry-run] --agent-type TYPE [--pane-name NAME] -- ARGV...
preset update PRESET --replace [--dry-run] --agent-type TYPE [--pane-name NAME] -- ARGV...
```

```bash
"$wa" preset save reviewer-model --agent-type pi -- \
  pi --provider deepseek --model deepseek-v4-flash --thinking max
"$wa" preset save reviewer-model --agent-type pi --dry-run -- pi --provider deepseek
"$wa" preset show reviewer-model
"$wa" preset list
"$wa" preset update reviewer-model --replace --agent-type pi -- pi --provider deepseek
"$wa" preset remove reviewer-model
```

`save` refuses an existing name with `preset_exists`; `update` demands `--replace`. Add `--dry-run` to preview the normalized JSON without writing. Successful and `--dry-run` results include the normalized JSON, the actual argv, the target path, and a SHA-256 digest. Writes are atomic. Do not mutate presets after an ordinary temporary launch unless the user asked for preset maintenance or already granted that scope.

## The secret guard

`preset save`/`update` refuse an argv that carries a credential-like flag or assignment — API keys, access or auth tokens, client secrets, passwords, and credentials — with `preset_secret_suspected`. This heuristic guard covers the named credential patterns. Keep authentication out of argv entirely and let the target CLI use its own credential store or environment.

## config.json Agent registry

The registry maps an `agent_type` to a pane prefix. It lives next to presets:

```text
${XDG_CONFIG_HOME:-~/.config}/with-agents/config.json
```

The Python 3.10+ standard-library implementation stores this file as JSON:

```json
{
  "version": 1,
  "agents": {
    "codex": { "pane_prefix": "cd" },
    "opencode": { "pane_prefix": "oc" }
  }
}
```

A `pane_prefix` is exactly two ASCII alphanumeric characters (`^[A-Za-z0-9]{2}$` — for example `cd`, `oc`, `pi`). A three-character prefix such as `cdx` is rejected with `invalid_agent_config`. The built-in table is always present without a file:

| agent_type | pane_prefix |
| --- | --- |
| `codex` | `cx` |
| `claude` | `cc` |
| `pi` | `pi` |

Merge order is fixed: built-in defaults, then a per-`agent_type` override, then normalization, then a whole-table validation. A built-in type may override its `pane_prefix`; a new type must supply one. `external` and `generic` are reserved and cannot be registered.

Registration has exactly one effect: `launch` can generate a `<prefix>-` name for a registered `agent_type`. It grants no special input handling — every registered or built-in CLI is driven the same generic way (paste, Enter, return the latest screen); see [adapters.md](adapters.md). `preset save`/`update` record the `--agent-type TYPE` you pass verbatim and do not consult the registry, so the type you store need not be registered. A registry prefix is required only when `launch` must generate a name automatically; a full `--name` or a saved `pane_name` needs no registry at all.

## Failure and recovery

Missing config means the built-in table only; no config directory is created. A corrupt file, a symlink, an unknown version or field, or an invalid value makes a config-parsing command fail with `invalid_agent_config`. The only business operation that depends on the registry to succeed is a name-generating `launch` — one that must build a `<prefix>-` name from an `agent_type`; it reads the merged table and fails on an invalid one. `doctor` also parses the registry, but only to diagnose and report a broken file. Everything else keeps working when the config is broken, including `list`, `read`, `send`, `preset save`/`update` (which record the type verbatim), and a full-name or preset-named `launch`.

There is no config-write command. Maintain this low-frequency private file with an ordinary editor and an atomic replace. Neither the preset directory nor `config.json` is ever committed to the repository.

## Reference routing

- [cli.md](cli.md) — the command index, global options, the JSON envelope, and representative error codes.
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — `launch` naming, the live window name, and TARGET resolution.
- [messaging.md](messaging.md) — the send header grammar, params, and replying.
- [operation-states.md](operation-states.md) — launch state-unknown and process-exit results.
- [adapters.md](adapters.md) — per-CLI clear-input and new-conversation differences.
- [tmux-recovery.md](tmux-recovery.md) — raw-tmux recovery when the controller cannot finish an action.
