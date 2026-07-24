# with-agents CLI Contract

This reference owns the invocation model, the global options, the command index by frequency, the JSON envelope, and the representative error index. Each command's deeper behavior lives in a dedicated reference linked below; this file does not restate those contracts.

## Contents

- [Invocation and global options](#invocation-and-global-options)
- [Command index](#command-index)
- [The JSON envelope](#the-json-envelope)
- [Representative error codes](#representative-error-codes)
- [Reference routing](#reference-routing)

## Invocation and global options

Call the executable from the installed Skill root:

```bash
wa="<skill-root>/scripts/with-agents"
"$wa" <command> ...
```

The controller is a single standard-library Python file plus tmux. It requires Python 3.10+ and tmux 3.2+, reported by `doctor`. Report the controller version with `with-agents --version`.

Global options may appear before or right after a command:

| Option | Meaning |
| --- | --- |
| `--json` | Emit the machine-readable envelope |
| `--socket PATH` | Override socket selection with this exact tmux socket |

Inside tmux the controller inherits the exact socket from `$TMUX`. Outside tmux it uses the default server unless `--socket` is given. When no server exists, `launch` may start a minimal detached session named `with_agents` (an underscore, so it is never confused with the `with-agents:` route scheme). An unresolved caller with several sessions requires `--session` or `--split`.

`WITH_AGENTS_RUNTIME_DIR` and `WITH_AGENTS_CONFIG_DIR` (or `--runtime-dir` / `--config-dir`) override the runtime and config roots for isolated testing; do not point them at shared or untrusted directories.

## Command index

Commands are ordered by how often you reach for them. Every command that names a pane takes the same `TARGET` grammar — a `%pane-id`, a bare live `window_name`, an explicit `session:window.pane`, or a with-agents route — resolved the same way (see [panes-and-lifecycle.md](panes-and-lifecycle.md)).

| Command | One-line contract | Detail |
| --- | --- | --- |
| `read TARGET [--lines N]` | Capture the current screen | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `send TARGET [--no-header] [--request] [--correlation-id ID] [--params JSON] -- MESSAGE` | Paste one complete body, press Enter, and return the latest screen | [messaging.md](messaging.md), [operation-states.md](operation-states.md) |
| `list [--detail]` | List panes with stable targets, process hints, paths, live names, and a canonical socket-qualified route; `--detail` adds repair diagnostics | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `launch [--cwd DIR] [--no-wait] [--ready-timeout S] [--session S \| --split TARGET] (--preset ... \| -- ARGV...)` | Create a pane and launch an exact argv, waiting for a readable startup screen | [presets.md](presets.md), [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `wait TARGET [--timeout S] [--interval S] [--lines N]` | Wait for a screen change or the pane's process to exit or disappear, or until the timeout expires | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `key TARGET -- KEY...` | Send explicit tmux key names and return the latest screen | [panes-and-lifecycle.md](panes-and-lifecycle.md), [operation-states.md](operation-states.md) |
| `close TARGET [--lines N]` | Capture the final screen, then close the pane | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `preset list \| show \| save \| update \| remove` | Manage private JSON launch presets | [presets.md](presets.md) |
| `doctor` | Report Python, tmux, runtime, and agent-config diagnostics | [presets.md](presets.md) |
| `route [TARGET]` | Print a portable, socket-qualified route for the target, or for the caller when no argument is given | [panes-and-lifecycle.md](panes-and-lifecycle.md) |

`MESSAGE`, `ARGV`, and `KEY` are ordinary positional arguments. Place a `--` before them so the parser accepts leading-dash text or argv as positional content. Run `"$wa" <command> --help` for exact placement.

`launch` takes one of three forms, and the naming rule differs by form:

- **Preset:** `launch --preset NAME [--name FULL | --name-suffix SUFFIX]` — the name is optional (it falls back to the preset's `pane_name` or a generated one).
- **Non-split direct argv:** `launch --name FULL -- ARGV...` — `--name` is required, because a new window needs a name and there is no preset to fall back to.
- **Split direct argv:** `launch --split TARGET -- ARGV...` — `--name`/`--name-suffix` must be omitted; the new pane inherits the target window's live name. See [presets.md](presets.md).

## The JSON envelope

Default text output is rendered from the same data as `--json`. The top-level fields are always present, in this order:

```text
ok, event, stage, target, screen, error, recovery
```

- `ok` is the success boolean; the process exit status matches it.
- `event` is the command name; `stage` is the reached phase (for example `observed`, `submitted`, `listed`, `closed`).
- `target` carries pane, preset, route, or diagnostic detail; `screen` carries a bounded `{tail, lines}` capture.
- `error` is `{code, message[, details]}` on failure, `null` otherwise; `recovery` is a one-line next step or `null`.

Inapplicable fields are `null`. Command-specific values live inside `target`; there is no second top-level envelope family. For `send`, `target.message` describes only the input the controller constructed — the sender route it built, the final params, the correlation ID, and whether a header was used. `send` and `key` report the reached stage and the post-action screen; the controller never claims a field it cannot prove, such as `delivered` or `accepted_by_tui`.

## Representative error codes

This index lists representative codes. The owning reference defines each code's meaning and recovery.

| Code | Owner |
| --- | --- |
| `target_not_found`, `target_ambiguous`, `route_invalid`, `caller_identity_unavailable`, `self_target_denied`, `self_target_unverified`, `target_process_exited` | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `interrupted`, `post_action_observation_failed`, `launch_timeout`, `executable_not_found`, `launch_process_exited` | [operation-states.md](operation-states.md) |
| `params_invalid`, `params_source_conflict` | [messaging.md](messaging.md) |
| `pane_name_source_conflict`, `name_suffix_requires_preset`, `agent_prefix_not_configured`, `invalid_agent_config`, `preset_not_found`, `preset_exists`, `preset_secret_suspected`, `replace_required`, `launch_source_conflict` | [presets.md](presets.md) |
| `tmux_unavailable`, `tmux_timeout`, `tmux_command_failed`, `lock_timeout` | [tmux-recovery.md](tmux-recovery.md) |

`stage` and `code` are distinct. `text_not_written`, `text_written_not_submitted`, `submitted_state_unknown`, `key_state_unknown`, and the other `*_state_unknown` values are *stages* on the `stage` field — they describe how far an action reached. The `error.code` that accompanies a failed action is a separate value: a failed paste or submit surfaces as `tmux_command_failed`, `tmux_timeout`, or `interrupted` carrying the matching partial stage; a post-action capture failure is `post_action_observation_failed`. Do not treat a stage name as an error code. See [operation-states.md](operation-states.md) for the full stage-versus-code distinction.

## Reference routing

- [messaging.md](messaging.md) — the send header grammar, params, the input queue, the post-action snapshot, and replying.
- [operation-states.md](operation-states.md) — the three technical states, partial stages, and no-blind-replay recovery.
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — TARGET resolution, the live window name, the canonical route, the pane lock, launch/wait/close, and self-target.
- [presets.md](presets.md) — preset and `config.json` schema, pane-name sources, Agent registration, and the secret guard.
- [adapters.md](adapters.md) — per-CLI clear-input and new-conversation differences.
- [tmux-recovery.md](tmux-recovery.md) — raw-tmux recovery when the controller cannot finish an action.
