# 迁移 Trellis Task

使用本指南将持久 Task 状态从 `.trellis/tasks/` 迁移到嵌入的 `.task/` 存储。在已迁移的 Task 被验证且用户单独批准移除前，保持 `.trellis/` 不变。

## 目录

- [范围](#范围)
- [映射数据](#映射数据)
- [迁移](#迁移)
- [验证](#验证)
- [切换](#切换)

## 范围

迁移 Task 状态和 Task 自有材料：

- `.trellis/tasks/<task>/task.json`
- `prd.md`、`research/`、移交文件、反馈、实现或检查日志，以及任务自有的其他文件
- `.trellis/tasks/archive/` 下的已归档任务
- 明确属于被迁移任务的 `.trellis/handoff/<task>/`

不要将 `.trellis/spec/`、`.trellis/workspace/`、工作流脚本、会话状态或运行时文件视为 Task 数据。将可复用的项目规则移到项目的常规文档或 Agent 指令中，仅作为独立的、用户批准的更改。

不存在原地格式转换。所有目标都通过 Task Core 创建，然后将普通材料复制到返回的 `task_dir` 中。永远不要手动构造 Task 路径、UUID、受管 frontmatter、WAL 文件或归档状态。

## 映射数据

在写入任何内容前盘点所有源目录。存在 `task.json` 时解析它，但也检查目录内容：较旧或手动迁移的 Trellis Task 可能包含 JSON 中未体现的有用状态。

使用以下映射：

| Trellis | Task | 规则 |
| --- | --- | --- |
| `title` | `name` | 优先使用人类可读标题。如果超出 Task 的 40 列或 96 字节限制则缩短，并在 body 中保留完整标题。 |
| `description`、`prd.md` | `TASK.md` body 或链接材料 | 保持 body 为当前事实。将重要的 PRD 保留为 `prd.md` 并从 body 链接它，而非复制内容。 |
| `branch` | `branch` | 省略 null 或过时的分支。 |
| 可靠的原始创建或开始时间 | create-item 的 `created_at` | 仅当源证据能可靠识别原始时间点时，传递时区感知的 RFC 3339 时间戳。带日期的目录或仅日期值不足以发明时间或时区。 |
| `parent` / `children` | 父级和子任务 | 通过先创建父级再创建子级来重建层次结构。不要将层次结构编码为 `related_to`。 |
| `planning`、`in_progress` | `open` | 仅当源证据表明工作被有意暂停时使用 `paused`。 |
| `completed` | `closed` | 在后代被创建和关闭后再关闭。 |
| `abandoned`、`cancelled` | `closed` | 记录原始的终态和原因；不要仅为了表示它而使用 force。 |
| `tasks/archive/` 下的位置 | `archived: true` | 先关闭，然后归档。源状态和源位置是独立证据。 |
| `relatedFiles` | body 中的链接 | 将路径重写为已复制的 Task 自有材料。将项目文件链接保持为项目文件链接；不要仅因为被列出就复制其目标。报告指向迁移范围外的 Trellis 区域的链接。 |
| `priority`、`creator`、`assignee`、`base_branch`、`worktree_path`、commit 或 PR 字段、`notes`、`meta` | body、普通材料或 `extra.migration` | 保留仍然有用的值。除非工作树仍然存在，否则将工作树路径视为历史信息。不要为这些字段发明一等 Task 语义。 |
| `implement.jsonl`、`check.jsonl`、研究和移交文件 | 普通文件 | 将原始历史保留为材料。不要将冗长的历史日志逐条回放到 WAL 中。 |

将 Trellis ID 和目录名视为遗留引用，而非 Task ID。存储足够的来源信息以追踪迁移，例如：

```json
{
  "extra": {
    "migration": {
      "source": ".trellis/tasks/06-16-example",
      "source_id": "example",
      "source_status": "in_progress"
    }
  }
}
```

Task Core 始终分配新的 UUIDv7。当 create item 包含 `created_at` 时，Core 将其规范化为毫秒精度作为受管的 `created_at`，将同一时刻编码到 UUIDv7 中，并使用该时间戳偏移中表达的日历日期作为顶层 Task 的 `<task_root>/YYYY-MM/DD` 分区。初始 WAL 仍然记录实际的迁移时间。当原始时刻或时区不确定时省略 `created_at`；普通创建则继续对所有四个值使用实际创建时间。不要在 `extra.migration` 下重复提供的时间戳。

从两侧解析层次结构。Trellis 的 `parent` 和 `children` 值可能使用 ID、带日期的目录名或不一致的遗留前缀。构建一个源目录到目标 ID 的映射，并报告未解析或矛盾的边，而非猜测。不要从任务顺序、相近日期、分支或文字中推断 `depends_on` 或 `related_to`。

在复制前对材料进行分类。Trellis Task 目录除了持久文档外，还可能包含完整工作区、基准数据集、二进制包、虚拟环境、缓存和绝对符号链接：

- 默认保留源材料、研究、移交、决策、脚本、配置、紧凑结果和其他不可重现的 Task 自有材料。
- 默认排除可重现的缓存和环境，如 `.venv/`、`__pycache__/`、`.pytest_cache/`、`.ruff_cache/`、编译字节码和工具缓存。记录每个排除项。
- 按大小盘点大型数据集、基准输出、复制的参考仓库、归档、二进制文件和生成包。询问用户是复制、保留在外部存储并附加链接和校验和，还是排除它们；仅凭大小不足以使其成为可丢弃项。
- 迁移期间不解除符号链接引用。仅重新创建有意的、可移植的相对符号链接。记录并排除绝对的、损坏的、环境特定的或不明确的链接，除非用户选择其他处理方式。

当源项目是 Git 仓库时，将 Git 跟踪的文件作为有用证据，但不作为完整盘点依据：未跟踪的持久材料可能仍然重要，且某些 Trellis 根目录不在 Git 工作树内。对于非平凡的选择，编写迁移清单，列出复制的、链接的、重命名的和排除的路径，以及外部大型制品的校验和。

## 迁移

对于大型迁移，优先使用脚本进行确定性批量处理，然后单独验证和确认每个已迁移的 Task。

1. 确认 Task 已安装并运行 `task-core --version`。
2. 仅在用户同意后初始化项目。有目的地选择 Git 策略：
   - 当旧 Task 状态已版本化且 `.task/` 应保持共享时，运行 `task-core init --mode embedded --git-policy track`。
   - 对仅本地的 `.task/` 状态，运行 `task-core init --mode embedded --git-policy ignore`。
3. 在迁移过程中不要静默接受默认策略。如果用户反而想要分离存储或自定义 `task_root`，停止使用本 `.task/` 指南并显式规划该布局。
4. 盘点源 Task、材料大小和符号链接；分类目标状态、归档状态和材料处理方式；然后解析完整的父-子关系图。
5. 使用 `task_create` 创建所有顶层 Task。将每个可靠解析的原始时间戳放在该 Task item 的 `created_at` 中；宁可省略该字段也不合成缺失的精度或时区。用户的显式迁移批准满足严格的创建确认；仅在此基础上传递 `user_confirmed: true`。
6. 使用 `task_create` 并传 `type: "subtasks"` 和目标父级引用来创建子任务。对子项应用相同的逐项 `created_at` 规则。从根到叶处理层次结构。即使原始时间戳不同，也可批量创建可原子创建的同级子任务。
7. 记录每个源目录返回的 `task_dir` 和 UUID。仅使用此映射进行后续的关系、生命周期变更、文件复制和验证。
8. 将选定的 Task 自有材料复制到每个返回的 `task_dir` 中，不更改源且不解除符号链接引用。如果保留旧版 `task.json`，将其重命名为 `trellis-task.json`；这区分来源信息与实时 Task 状态。不要盲目递归遍历源目录。
9. 使用宿主文件工具编写或完善 `TASK.md` body，同时保持其 YAML frontmatter 不变。链接未来 Agent 应首先读取的保留材料。
10. 使用 `task_log` 追加一条简洁的迁移 WAL 记录。包括源路径、原始状态、迁移材料摘要以及有意未映射的任何信息。自动创建记录和本记录都使用实际迁移时间，即使 `created_at` 保留了更早的时间点。不要逐条回放 `implement.jsonl` 或 `check.jsonl`。
11. 仅使用 `task_update` 重新创建显式非层次关系，使用目标 UUID。报告目标未被迁移的关系。
12. 使用 `task_update` 从叶到根依次应用终态。提供原因，如 `Migrated from completed Trellis task`。如果源请求已关闭的祖先同时有打开的后代，或以其他方式违反 Task 生命周期不变性，报告冲突并询问是否保持祖先打开、更改某个后代的映射状态或强制转换。仅对用户的明确选择使用 force。
13. 归档其源目录在 Trellis `tasks/archive/` 下的 Task，归档前确保它们已关闭。将关闭但未归档的 Task 保持为已关闭且未归档。

对于单个 Task，遵循相同序列而不构建源树的无关部分。如果它有父级或子级，询问是否迁移必要的关联层次结构；仅在用户明确选择时才展平。

## 验证

运行 `task-core check`，然后通过 Task Core 验证，而非仅信任文件系统副本：

1. 使用 `include_archived: true` 的 `task_find` 并比较预期的迁移计数。
2. 在每个已迁移的根 Task 上使用 `task_read`，检查拓扑、受管验证、状态、归档状态、分支、body 和最近 WAL。
3. 对每个提供的 `created_at`，确认受管值在毫秒精度上匹配，UUIDv7 时间戳表示同一时刻，每个顶层目录使用该时间戳自己的 `YYYY-MM/DD` 日历日期。确认初始 WAL 时间戳和文件名反映的是实际迁移时间。
4. 确认每个迁移的子项具有预期的父级，且每个显式关系解析到新的 UUID。
5. 将目标材料与迁移清单或源盘点进行比较。当精确保留很重要时验证校验和。明确说明重命名的 `task.json`、链接的大型制品和每个有意排除的路径。
6. 搜索迁移后的 body 和材料中过时的 `.trellis/tasks/...` 链接。重写应指向已迁移材料的目标链接；保留有意作为历史信息的来源引用。
7. 确认已归档的 Task 已关闭，且活动的源 Task 不会仅因其为终态而变为已归档。
8. 检查 Git 状态。确保所选 Git 策略与实际跟踪或忽略的内容匹配，且没有无关文件被更改。

发现差异时停止并报告。不要删除或重写源以让验证通过。

## 切换

报告源到目标的映射、已迁移和跳过的 Task、未解决的关系、排除的材料、验证结果以及所选存储/Git 策略。

仅当该工作在范围内时，更新仍需要 Trellis 的项目指令、钩子或入口点。Task 迁移不会自动替换 Trellis 规范、工作流自动化或会话管理。

在审查期间保留 `.trellis/`。移除它是一个独立的破坏性操作，需要在所有已迁移状态和剩余的非 Task 责任被说明后获得显式用户批准。
