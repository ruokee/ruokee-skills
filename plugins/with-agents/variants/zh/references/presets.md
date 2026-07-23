# Preset、Agent 配置与 Pane 命名

本参考文档涵盖私有 preset 的 schema 和生命周期、`config.json` Agent 注册表、pane 名称来源以及秘密值守卫。在创建、使用或维护 preset 时，使用 `--name-suffix` 时，或注册新 Agent 类型时阅读。

## 目录

- [Pane 名称来源](#pane-名称来源)
- [Preset schema 与位置](#preset-schema-与位置)
- [管理 preset](#管理-preset)
- [秘密值守卫](#秘密值守卫)
- [config.json Agent 注册表](#configjson-agent-注册表)
- [失败与恢复](#失败与恢复)

## Pane 名称来源

`launch` 从四个互斥来源之一解析新的 pane 名称——不存在隐式优先级链：

```text
launch [--cwd DIR] [--session SESSION | --split TARGET]
       (--preset PRESET [--name FULL | --name-suffix SUFFIX]
        | --name FULL -- ARGV...)
```

1. `--preset PRESET --name FULL` — 直接使用完整名称。
2. `--preset PRESET --name-suffix SUFFIX` — 在当前注册表中查找 preset 的 `agent_type`，构造 `<prefix>-<suffix>`。
3. `--preset PRESET` 单独使用 — 使用 preset 保存的 `pane_name`。
4. `--name FULL -- ARGV...` — 直接 argv 启动；必须提供完整名称。

冲突在 pane 创建前失败：

| 情况 | 错误 |
| --- | --- |
| 同时指定 `--name` 和 `--name-suffix` | `pane_name_source_conflict` |
| 使用 `--name-suffix` 但未提供 `--preset` | `name_suffix_requires_preset` |
| Preset 的 `agent_type` 未配置 prefix | `agent_prefix_not_configured` |

```bash
<skill-root>/scripts/launch-agent --preset ds-flash --name-suffix trans   # pi-trans
<skill-root>/scripts/launch-agent --preset ds-flash --name-suffix worker  # pi-worker
<skill-root>/scripts/launch-agent --preset ds-flash --name one-off-review # one-off-review
<skill-root>/scripts/launch-agent --preset ds-flash                       # the preset's pane_name
```

每次 suffix 启动时，prefix 从 `config.json` 中实时解析——它从不写入 preset 中，因此更改 prefix 无需重写 preset，也不会改变 preset 的摘要。更改 prefix 不会重命名现有 pane。Suffix、prefix 和最终名称均按受限 ASCII 验证，完整名称必须符合 1-64 字符的 pane 命名规则。重复的可读名称仍然允许；控制器在名称解析有歧义时拒绝猜测，因此请使用 `launch` 返回的 pane ID 或 run ID 来标识 pane。`restart` 保留现有 pane 名称且不接受名称参数；`create` 只接受完整的 `--name`。

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

`pane_name` 仅为未提供命名参数时的默认值。`argv` 是精确的启动向量；控制器将其传递给 `execvp`，绝不通过 shell 运行。不存在项目级 preset 继承。仓库中绝不能包含真实 preset——只应有 schema、默认值和示例。

## 管理 preset

从 owned pane 的实际启动记录创建，这样保存的 argv 是经过验证的而非回忆：

```bash
"$wa" preset save reviewer-model --from reviewer
"$wa" preset save reviewer-model --from reviewer --dry-run
"$wa" preset show reviewer-model
"$wa" preset list
```

`save` 拒绝已有名称（`preset_exists`）。更新仍为一次确定性调用，但要求显式替换：

```bash
"$wa" preset update reviewer-model --from reviewer --replace   # --replace is required
"$wa" preset remove reviewer-model
```

成功和 `--dry-run` 结果包含规范化 JSON、实际 argv、目标路径、源 pane 和 SHA-256 摘要。写入是原子的。除非用户要求 preset 维护或已授予该范围，否则不要在普通临时启动后修改 preset。

## 秘密值守卫

`preset save`/`update` 拒绝携带类似凭据标志或赋值的 argv——API key、access token、auth token、client secret、password、credential——错误码为 `preset_secret_suspected`。这是守卫，而非完整的机密扫描器：请将认证信息完全排除在 argv 之外，让目标 CLI 使用自己的凭据存储或环境。

## config.json Agent 注册表

注册表将 `agent_type` 映射到 pane prefix 和用于识别它的可执行文件 basename。它位于 preset 旁边：

```text
${XDG_CONFIG_HOME:-~/.config}/with-agents/config.json
```

由于控制器仅依赖 Python 3.10+ 和标准库，文件格式为 JSON 而非 TOML：

```json
{
  "version": 1,
  "agents": {
    "codex": { "pane_prefix": "cdx" },
    "opencode": { "pane_prefix": "oc", "executables": ["opencode"] }
  }
}
```

无需文件即可使用的内置表：

| agent_type | pane_prefix | executables |
| --- | --- | --- |
| `codex` | `cx` | `codex` |
| `claude` | `cc` | `claude` |
| `pi` | `pi` | `pi` |

合并顺序是固定的：内置默认值，然后按 `agent_type` 逐字段覆盖，然后规范化，然后整表验证。内置类型仅可覆盖 `pane_prefix`；显式的 `executables` 列表完全替换内置列表而非追加。新类型必须同时提供 `pane_prefix` 和至少一个可执行文件。一个规范化后的可执行文件 basename 只能属于一个类型。`external` 和 `generic` 为保留名称，不可注册。

注册的精确影响有两个：`preset save`/`update` 可以记录新的 `agent_type` 并为其生成 suffix 名称；此外，其活跃前台进程与已注册可执行文件匹配的 caller 可以收到**通用**的尽力门铃。注册从不授予 Codex/Pi 专用 composer 识别器、多行安全保证或任何 TUI 接受性声明。那些专用能力仍由代码定义，参见 [adapters.md](adapters.md)。

Agent 种类由可执行文件解析，绝不扫描任务文本：launcher 对 `env`、`node`、`nodejs`、`python`、`python3` 解包（跳过选项和环境变量赋值），然后匹配第一个真实的可执行文件 basename。仅提及 Agent 名称的任务参数不能注册类型。

## 失败与恢复

缺少配置文件意味着仅使用内置表；不会创建配置目录。损坏的文件、符号链接、未知版本或字段、无效值、重复的可执行文件或不完整的新类型会导致需要配置的命令以 `invalid_agent_config` 失败。不需要注册表的命令——`list`、`read`、`send`、完整名称直接 `launch`、preset 默认 `launch` 和 `version`——在配置损坏时仍正常工作。`preset save`/`update` 和 suffix `launch` 读取合并后的表，并在配置无效时失败；`doctor` 报告问题。

此版本中没有配置写入命令。使用普通编辑器以原子替换方式维护这个低频私有文件。Preset 目录和 `config.json` 都不允许提交到仓库中。
