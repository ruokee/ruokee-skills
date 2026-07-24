# Preset、Agent 配置与 Pane 命名

本参考文档涵盖私有 preset 的 schema 和生命周期、`config.json` Agent 注册表、pane 名称来源以及秘密值守卫。在创建、使用或维护 preset 时，使用 `--name-suffix` 时，或注册新 Agent 类型时阅读。

## 目录

- [Pane 名称来源](#pane-名称来源)
- [Preset schema 与位置](#preset-schema-与位置)
- [管理 preset](#管理-preset)
- [秘密值守卫](#秘密值守卫)
- [config.json Agent 注册表](#configjson-agent-注册表)
- [失败与恢复](#失败与恢复)
- [参考导航](#参考导航)

## Pane 名称来源

`launch` 从恰好一个来源解析新 pane 名称，按此顺序：

1. 显式 `--name FULL`——直接使用完整名称；
2. `--preset PRESET --name-suffix SUFFIX`——在注册表中查找 preset 的 `agent_type` prefix 并构建 `<prefix>-<suffix>`；
3. `--preset PRESET` 且保存了 `pane_name`——使用该名称；
4. 否则——生成 `<prefix>-NNNN`，其中 `NNNN` 为一次性选择的四位随机数字，不做实时名称检查且不重试。

```bash
"$wa" launch --preset ds-flash                       # the preset's pane_name, or a generated <prefix>-NNNN
"$wa" launch --preset ds-flash --name-suffix trans   # pi-trans
"$wa" launch --preset ds-flash --name one-off-review # one-off-review
"$wa" launch --name scratch -- some-cli --flag       # direct argv, explicit name
```

冲突在 pane 创建前失败：

| 情况 | 错误 |
| --- | --- |
| 同时指定 `--name` 和 `--name-suffix` | `pane_name_source_conflict` |
| 使用 `--name-suffix` 但未提供 `--preset` | `name_suffix_requires_preset` |
| Preset 的 `agent_type` 未配置 prefix | `agent_prefix_not_configured` |

生成的 prefix 恰好为两个 ASCII 字母数字字符，每次 launch 时从注册表实时解析——它从不写入 preset 中，因此更改 prefix 不会重写 preset 或重命名现有 pane。生成的 `--name-suffix` 恰好为 1-6 个 ASCII 字母数字字符，随机尾部固定为四位数字；结果名称必须仍符合 1-64 受限 ASCII 规则。显式 `--name` 和 preset 自身的 `pane_name` 是逃生口，仅需满足 1-64 规则。

`launch --split TARGET` 不创建窗口，也不获取自己的名称——新 pane 继承目标窗口的实时 `window_name`。Preset 保存的 `pane_name` 在 split launch 中不适用，直接 argv split launch 不需要名称。将 `--split` 与 `--name`/`--name-suffix` 结合使用会在 pane 创建前被拒绝。

## Preset schema 与位置

Preset 是私有的，位于本仓库之外：

```text
${XDG_CONFIG_HOME:-~/.config}/with-agents/presets/<name>.json
```

Schema 为版本 1：

```json
{
  "version": 1,
  "agent_type": "pi",
  "pane_name": "pi-default",
  "argv": ["pi", "--provider", "deepseek", "--model", "deepseek-v4-flash", "--thinking", "max"]
}
```

`agent_type` 和 `argv` 为必填；`pane_name` 为可选，省略时 JSON 中不包含该字段。Preset 不保存 cwd。`argv` 是精确的启动向量；控制器将其传递给 `execvp`，绝不通过 shell 运行。仓库中绝不能包含真实 preset——只应有 schema、默认值和示例。

## 管理 preset

Save 和 update 需要显式配置——不从实时 pane 或前台进程推断任何信息：

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

`save` 拒绝已有名称（`preset_exists`）；`update` 需要 `--replace`。添加 `--dry-run` 预览规范化 JSON 而不写入。成功和 `--dry-run` 结果包含规范化 JSON、实际 argv、目标路径和 SHA-256 摘要。写入是原子的。除非用户要求 preset 维护或已授予该范围，否则不要在普通临时启动后修改 preset。

## 秘密值守卫

`preset save`/`update` 拒绝携带类似凭据的标志或赋值的 argv——API key、access token、auth token、client secret、password、credential——错误码为 `preset_secret_suspected`。该启发式守卫覆盖上述凭据模式。请将认证信息完全排除在 argv 之外，让目标 CLI 使用自己的凭据存储或环境。

## config.json Agent 注册表

注册表将 `agent_type` 映射到 pane prefix。它位于 preset 旁边：

```text
${XDG_CONFIG_HOME:-~/.config}/with-agents/config.json
```

这个 Python 3.10+ 标准库实现使用 JSON 存储该文件：

```json
{
  "version": 1,
  "agents": {
    "codex": { "pane_prefix": "cd" },
    "opencode": { "pane_prefix": "oc" }
  }
}
```

`pane_prefix` 必须恰好为两个 ASCII 字母数字字符（`^[A-Za-z0-9]{2}$`——例如 `cd`、`oc`、`pi`）。三个字符的 prefix（如 `cdx`）会被拒绝并报 `invalid_agent_config`。无需文件即可使用的内置表：

| agent_type | pane_prefix |
| --- | --- |
| `codex` | `cx` |
| `claude` | `cc` |
| `pi` | `pi` |

合并顺序是固定的：内置默认值，然后按 `agent_type` 逐字段覆盖，然后规范化，然后整表验证。内置类型可覆盖其 `pane_prefix`；新类型必须提供一个。`external` 和 `generic` 为保留名称，不可注册。

注册的精确影响只有一个：`launch` 可以生成 `<prefix>-` 名称用于已注册的 `agent_type`。它不授予任何特殊输入处理——每个已注册或内置 CLI 都以相同通用方式驱动（粘贴、Enter、返回最新画面）；参见 [adapters.md](adapters.md)。`preset save`/`update` 按原样记录你传入的 `--agent-type TYPE`，不咨询注册表，因此存储的类型无需注册。仅当 `launch` 必须自动生成名称时才需要注册表 prefix；完整的 `--name` 或保存的 `pane_name` 完全不需要注册表。

## 失败与恢复

缺少配置文件意味着仅使用内置表；不会创建配置目录。损坏的文件、符号链接、未知版本或字段或无效值会导致配置解析命令以 `invalid_agent_config` 失败。唯一依赖注册表成功完成的业务操作是需要生成名称的 `launch`——即必须构建 `<prefix>-` 名称（来自 `agent_type`）的 launch；它读取合并后的表，并在无效时失败。`doctor` 也会解析注册表，但仅用于诊断和报告损坏的文件。其他一切在配置损坏时仍正常工作，包括 `list`、`read`、`send`、`preset save`/`update`（按原样记录类型）以及完整名称或 preset 命名的 `launch`。

没有配置写入命令。使用普通编辑器以原子替换方式维护这个低频私有文件。Preset 目录和 `config.json` 都不允许提交到仓库中。

## 参考导航

- [cli.md](cli.md) — 命令索引、全局选项、JSON 信封和代表性错误码。
- [panes-and-lifecycle.md](panes-and-lifecycle.md) — `launch` 命名、实时窗口名称和 TARGET 解析。
- [messaging.md](messaging.md) — 发送头部语法、params 和回复。
- [operation-states.md](operation-states.md) — launch state-unknown 和进程退出结果。
- [adapters.md](adapters.md) — 各 CLI 的清输入和开始新对话差异。
- [tmux-recovery.md](tmux-recovery.md) — 控制器无法完成操作时的原生 tmux 恢复。
