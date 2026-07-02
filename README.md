# ruokee-skills

Ruokee 的个人 Skills 工作仓库。

这个仓库用于管理 Skill Workspace、可安装的 Skill 产物、第三方 Skill 说明，以及后续的安装和版本切换工具。

## 当前状态

- 仓库已初始化。
- `public/` 下的自研 Skill 正在迁入，当前内容仍处于审阅阶段。
- 安装脚本、registry 或自动发现机制尚未实现。

## 顶层目录

```text
public/
experimental/
third-party/
```

- `public/`：自研且已经稳定到可以对外发布的 Skills。
- `experimental/`：自研或改造中、尚未正式可用的 Skills。
- `third-party/`：外部引入的 Skills。通常只保留极简 Workspace，并在 `README.md` 中说明来源和选用原因。

## Workspace 结构

自研 Skill 的 Workspace 以 Skill 名称命名：

```text
public/<skill-name>/
├── README.md
├── CHANGELOG.md
├── architecture.md
├── en/
│   └── <skill-name>/
└── zh/
    └── <skill-name>/
```

约束：

- `README.md` 和可安装的 Skill 产物目录是必须项。
- 可安装的 Skill 产物目录名称必须与 Skill 名称完全一致，例如 `zh/code-quality/`。
- `CHANGELOG.md`、`architecture.md`、`research/` 等维护材料按需添加。
- 语言变体由后续安装脚本选择或切换；同一个安装目标下同一时间只安装一个同名 Skill 变体。
