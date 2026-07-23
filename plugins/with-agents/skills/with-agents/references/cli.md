# with-agents CLI Contract

The `cli.md` reference owns the invocation model, the global options, the exact command index, the frozen JSON envelope, and the representative error index. Each command's deeper behavior lives in a dedicated reference linked from the index below; this file does not restate those contracts.

## Contents

- [Invocation and global options](#invocation-and-global-options)
- [Command index](#command-index)
- [The JSON envelope](#the-json-envelope)
- [Representative error codes](#representative-error-codes)
- [Where each contract lives](#where-each-contract-lives)

## Invocation and global options

Call the executable from the installed Skill root:

```bash
wa="<skill-root>/scripts/with-agents"
"$wa" <command> ...
```

The controller is a single standard-library Python file plus tmux. It requires Python 3.10+ and tmux 3.2+, reported by `doctor`. `scripts/launch-agent` is exactly `scripts/with-agents launch` and takes the same options.

Global options may appear before or right after a command:

| Option | Meaning |
| --- | --- |
| `--json` | Emit the machine-readable envelope instead of the rendered text |
| `--socket PATH` | Use this exact tmux socket rather than `$TMUX` or the default server |
| `--caller-id ID` | Keep observation and caller-route identity distinct for concurrent callers outside tmux |

Inside tmux the controller inherits the exact socket from `$TMUX`. Outside tmux it uses the default server unless `--socket` is given. When no server exists, `create` and `launch` may start a minimal detached `with-agents` session. When a caller session cannot be resolved and several exist, `--session` or `--split` is required rather than a guess.

`WITH_AGENTS_RUNTIME_DIR` and `WITH_AGENTS_CONFIG_DIR` override the runtime and config roots for isolated testing; do not point them at shared or untrusted directories.

## Command index

| Command | One-line contract | Detail |
| --- | --- | --- |
| `list` | List panes with stable targets, process hints, paths, ownership, names, and run IDs | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `read TARGET [--lines N]` | Capture the current screen and record a caller-scoped observation | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `create --name NAME [--cwd DIR] [--session S \| --split TARGET]` | Create an owned shell pane and observe it | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `launch [--cwd DIR] [--session S \| --split TARGET] (--preset NAME [--name FULL \| --name-suffix SUFFIX] \| --name FULL -- ARGV...)` | Create an owned pane and launch an exact argv | [presets.md](presets.md), [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `send TARGET [--allow-foreign] MESSAGE` | Write one complete message plus its submit key | [messaging.md](messaging.md), [operation-states.md](operation-states.md) |
| `key TARGET [--allow-foreign] KEY...` | Send explicit tmux key names after an observation | [panes-and-lifecycle.md](panes-and-lifecycle.md), [operation-states.md](operation-states.md) |
| `wait TARGET [--timeout S] [--interval S] [--lines N]` | Wait for one screen or process change, or until the timeout expires | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `restart TARGET [--force-foreign] (--preset NAME \| -- ARGV...)` | Respawn a pane in place under a new run identity | [panes-and-lifecycle.md](panes-and-lifecycle.md), [operation-states.md](operation-states.md) |
| `close TARGET [--lines N] [--force-foreign]` | Capture the final screen, then close the pane | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `request TARGET [--allow-foreign] [--notify spool\|pane] [--reply-to TARGET [--reply-socket PATH]] [--reply-ttl SECONDS] MESSAGE` | Dispatch a task and open an asynchronous outcome stream | [messaging.md](messaging.md) |
| `reply REQUEST_ID --status progress\|question\|done\|blocked\|failed [--message M] [--file PATH]` | Append one outcome event and optionally ring the caller | [messaging.md](messaging.md) |
| `inbox [REQUEST_ID]` | List a caller's eventful requests, or one request's full event stream | [messaging.md](messaging.md) |
| `preset list \| show \| save \| update \| remove` | Manage private JSON launch presets | [presets.md](presets.md) |
| `gc [--stale [DAYS]] [--delete-stale]` | Remove terminal request scratch, or inspect explicit stale requests | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `doctor` | Report Python, tmux, runtime, notification-adapter, and agent-config diagnostics | [adapters.md](adapters.md) |
| `version` | Report the controller version | — |

`MESSAGE`, `ARGV`, and `KEY` are ordinary positional arguments. Place a `--` before them so text or an argv that begins with a dash is not read as an option. Run `"$wa" <command> --help` for exact placement.

## The JSON envelope

Default text output is rendered from the same data as `--json`. The top-level fields are always present, in this order:

```text
ok, event, stage, target, request, notification, screen, error, recovery
```

- `ok` is the success boolean; the process exit status matches it.
- `event` is the command name; `stage` is the reached phase (for example `observed`, `submitted`, `outcome_persisted`, `listed`, `closed`).
- `target` carries pane, preset, or diagnostic detail; `request` carries request/event/inbox detail; `notification` carries doorbell diagnostics; `screen` carries a bounded `{tail, lines}` capture.
- `error` is `{code, message[, details]}` on failure, `null` otherwise; `recovery` is a one-line next step or `null`.

Inapplicable fields are `null`. Command-specific values live inside `target` or `request`; no second top-level envelope family is added. Text and key results report `tmux_accepted` and `tui_acceptance: "unverified"` — the controller never claims a field it cannot prove, such as `delivered` or `accepted_by_tui`.

## Representative error codes

This index is representative, not an exhaustive enum. The owning reference defines each code's meaning and recovery.

| Code | Owner |
| --- | --- |
| `observation_required`, `observation_expired`, `target_identity_changed`, `foreign_write_denied`, `self_target_denied`, `target_process_exited`, `foreign_restart_denied`, `foreign_close_denied` | [panes-and-lifecycle.md](panes-and-lifecycle.md) |
| `submitted_state_unknown`, `key_state_unknown`, `multiline_not_safe`, `interrupted` | [operation-states.md](operation-states.md) |
| `pane_name_source_conflict`, `name_suffix_requires_preset`, `agent_prefix_not_configured`, `invalid_agent_config`, `preset_not_found`, `preset_exists`, `preset_secret_suspected`, `replace_required`, `launch_source_conflict` | [presets.md](presets.md) |
| `reply_ticket_invalid`, `reply_stream_terminated`, `reply_event_limit`, `reply_result_budget_exhausted`, `reply_ticket_expired`, `already_replied`, `reply_route_invalid`, `invalid_reply_ttl`, `result_file_invalid`, `result_file_too_large` | [messaging.md](messaging.md) |
| `notify_prerequisite_missing`, `tmux_unavailable`, `tmux_timeout`, `tmux_command_failed`, `lock_timeout` | [messaging.md](messaging.md), [adapters.md](adapters.md), [tmux-recovery.md](tmux-recovery.md) |

Not every `stage` is an error code. `text_not_written`, `text_written_not_submitted`, and the lifecycle `*_state_unknown` values are partial `send`/mutation *stages* reported on the envelope's `stage` field; some of them (`submitted_state_unknown`, `key_state_unknown`) are also stable error codes when the operation fails at that point. See [operation-states.md](operation-states.md) for the full stage-versus-code distinction.

## Where each contract lives

- [presets.md](presets.md) — preset and `config.json` schema, pane-name sources, Agent registration, secret guard.
- [messaging.md](messaging.md) — `send`, and the `request`/`reply`/`inbox` asynchronous event stream.
- [operation-states.md](operation-states.md) — every atomic operation's partial stages and no-blind-replay recovery.
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — identity, observation, ownership, locks, `gc`, and the pane lifecycle commands.
- [adapters.md](adapters.md) — Agent/launcher detection, notification strategy, composer recognition, version diagnostics.
- [tmux-recovery.md](tmux-recovery.md) — raw-tmux recovery when the controller cannot finish an event.
