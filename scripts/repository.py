"""ruokee-skills 仓库结构、变体与 manifest 的共享模型。"""

import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT_NAME = "plugins"
PROJECT_INSTALL_METADATA = ".ruokee-skills-install.json"
CLASSIFICATIONS = frozenset(("public", "third-party", "fork"))
UPSTREAM_CLASSIFICATIONS = frozenset(("third-party", "fork"))
UPSTREAM_MODES = frozenset(("merge", "replace"))
TOP_LEVEL_FIELDS = frozenset(("schema_version", "classification", "experimental", "package_root", "variants", "upstream"))
VARIANT_FIELDS = frozenset(("default", "base"))
UPSTREAM_FIELDS = frozenset(("repository", "path", "ref", "commit", "imported_at", "updated_at", "mode", "managed_paths"))
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
SAFE_SEGMENT_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")


class RepositoryError(RuntimeError):
    """仓库结构或内容不满足 schema 2 契约。"""


@dataclass(frozen=True)
class TreeEntry:
    kind: str
    mode: int
    digest: str | None = None


@dataclass(frozen=True)
class Upstream:
    repository: str
    path: str
    ref: str
    commit: str
    imported_at: date
    updated_at: date
    mode: str
    managed_paths: tuple[str, ...]


@dataclass(frozen=True)
class Plugin:
    name: str
    workspace: Path
    classification: str
    experimental: bool
    package_root: Path
    default_variant: str
    base: Path
    overlays: dict[str, Path]
    upstream: Upstream | None

    @property
    def variants(self) -> tuple[str, ...]:
        return (self.default_variant, *sorted(self.overlays))

    @property
    def skill_path(self) -> Path:
        return self.base

    def source_for_variant(self, variant: str) -> Path | None:
        if variant == self.default_variant:
            return None
        try:
            return self.overlays[variant]
        except KeyError as exc:
            choices = ", ".join(self.variants)
            raise RepositoryError(f"插件 {self.name} 没有变体 {variant!r}；可选值：{choices}") from exc

    def relative_package_root(self, repository_root: Path = REPO_ROOT) -> str:
        return self.package_root.relative_to(repository_root).as_posix()


def lstat_optional(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise RepositoryError(f"无法检查路径 {path}：{exc}") from exc


def require_directory(path: Path, field: str) -> Path:
    info = lstat_optional(path)
    if info is None or not stat.S_ISDIR(info.st_mode):
        raise RepositoryError(f"{field} 必须是存在的非符号链接目录：{path}")
    return path


def require_regular_file(path: Path, field: str) -> Path:
    info = lstat_optional(path)
    if info is None or not stat.S_ISREG(info.st_mode):
        raise RepositoryError(f"{field} 必须是存在的普通文件：{path}")
    return path


def validate_segment(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SAFE_SEGMENT_PATTERN.fullmatch(value):
        raise RepositoryError(f"{field} 必须是安全的小写连字符单段名称")
    return value


def normalized_relative_path(value: Any, field: str, *, allow_dot: bool = False) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise RepositoryError(f"{field} 必须是非空的相对 POSIX 路径")
    if value == ".":
        if allow_dot:
            return value
        raise RepositoryError(f"{field} 不能是当前目录")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise RepositoryError(f"{field} 包含非法路径段：{value!r}")
    return value


def resolve_directory(root: Path, value: Any, field: str, *, allow_dot: bool = False) -> Path:
    relative = normalized_relative_path(value, field, allow_dot=allow_dot)
    if relative == ".":
        return require_directory(root, field)
    current = root
    for part in relative.split("/"):
        current /= part
        require_directory(current, field)
    return current


def resolve_managed_path(root: Path, value: Any, field: str) -> Path:
    relative = normalized_relative_path(value, field)
    current = root
    parts = relative.split("/")
    for part in parts[:-1]:
        current /= part
        require_directory(current, field)
    target = current / parts[-1]
    return require_regular_file(target, field)


def read_regular_file(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise RepositoryError(f"无法安全读取普通文件 {path}：{exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise RepositoryError(f"路径不是普通文件：{path}")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    except OSError as exc:
        raise RepositoryError(f"无法读取普通文件 {path}：{exc}") from exc
    finally:
        os.close(descriptor)


def scan_tree(root: Path, *, exclude_install_metadata: bool = False) -> dict[Path, TreeEntry]:
    require_directory(root, "Skill layer")
    entries: dict[Path, TreeEntry] = {}

    def visit(directory: Path, relative_directory: Path) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise RepositoryError(f"无法遍历目录 {directory}：{exc}") from exc
        for child in children:
            relative = relative_directory / child.name
            if exclude_install_metadata and relative == Path(PROJECT_INSTALL_METADATA):
                continue
            if child.name == "__pycache__" or child.name.endswith((".pyc", ".pyo")):
                raise RepositoryError(f"Skill layer 包含生成文件：{relative.as_posix()}")
            try:
                info = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise RepositoryError(f"无法检查 Skill layer 路径 {child.path}：{exc}") from exc
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISDIR(info.st_mode):
                entries[relative] = TreeEntry("directory", mode)
                visit(Path(child.path), relative)
            elif stat.S_ISREG(info.st_mode):
                digest = hashlib.sha256(read_regular_file(Path(child.path))).hexdigest()
                entries[relative] = TreeEntry("file", mode, digest)
            else:
                raise RepositoryError(f"Skill layer 只允许非符号链接目录和普通文件：{relative.as_posix()}")

    visit(root, Path())
    return entries


def validate_overlay(base: Path, overlay: Path) -> None:
    base_entries = scan_tree(base)
    overlay_entries = scan_tree(overlay)
    for relative, current in overlay_entries.items():
        original = base_entries.get(relative)
        if original is None:
            continue
        if original.kind != current.kind:
            raise RepositoryError(f"overlay 不能改变路径类型：{overlay / relative}")
        if current.kind == "file" and original.mode == current.mode and original.digest == current.digest:
            raise RepositoryError(f"overlay 不应重复与 base 完全相同的文件：{overlay / relative}")


def frontmatter_name(skill_file: Path) -> str:
    require_regular_file(skill_file, "SKILL.md")
    try:
        lines = read_regular_file(skill_file).decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise RepositoryError(f"SKILL.md 不是有效 UTF-8：{skill_file}") from exc
    if not lines or lines[0].strip() != "---":
        raise RepositoryError(f"SKILL.md 缺少 YAML frontmatter：{skill_file}")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise RepositoryError(f"SKILL.md frontmatter 未闭合：{skill_file}") from exc
    names = []
    for line in lines[1:end]:
        match = re.fullmatch(r"name\s*:\s*(.*?)\s*", line)
        if match:
            value = match.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            names.append(value)
    if len(names) != 1 or not names[0]:
        raise RepositoryError(f"SKILL.md frontmatter 必须包含唯一的 name：{skill_file}")
    return names[0]


def parse_upstream(value: Any, classification: str, base: Path, metadata: Path) -> Upstream | None:
    if value is None:
        if classification in UPSTREAM_CLASSIFICATIONS:
            raise RepositoryError(f"{metadata} 的 {classification} 插件必须提供 [upstream]")
        return None
    if classification not in UPSTREAM_CLASSIFICATIONS:
        raise RepositoryError(f"{metadata} 只有 third-party 或 fork 插件可以提供 [upstream]")
    if not isinstance(value, dict) or set(value) != UPSTREAM_FIELDS:
        unknown = sorted(set(value) - UPSTREAM_FIELDS) if isinstance(value, dict) else []
        missing = sorted(UPSTREAM_FIELDS - set(value)) if isinstance(value, dict) else sorted(UPSTREAM_FIELDS)
        raise RepositoryError(f"{metadata} 的 [upstream] 字段不完整或包含未知项；缺少 {missing}，未知 {unknown}")
    strings: dict[str, str] = {}
    for field in ("repository", "path", "ref", "commit", "mode"):
        current = value[field]
        if not isinstance(current, str) or not current:
            raise RepositoryError(f"{metadata} 的 upstream.{field} 必须是非空字符串")
        strings[field] = current
    normalized_relative_path(strings["path"], f"{metadata}: upstream.path", allow_dot=True)
    if not COMMIT_PATTERN.fullmatch(strings["commit"]):
        raise RepositoryError(f"{metadata} 的 upstream.commit 必须是 40 位小写十六进制 commit")
    if strings["mode"] not in UPSTREAM_MODES:
        raise RepositoryError(f"{metadata} 的 upstream.mode 只允许 merge 或 replace")
    dates: dict[str, date] = {}
    for field in ("imported_at", "updated_at"):
        current = value[field]
        if not isinstance(current, date) or isinstance(current, datetime):
            raise RepositoryError(f"{metadata} 的 upstream.{field} 必须是 TOML local-date")
        dates[field] = current
    managed = value["managed_paths"]
    if not isinstance(managed, list) or not managed or not all(isinstance(item, str) for item in managed):
        raise RepositoryError(f"{metadata} 的 upstream.managed_paths 必须是非空字符串数组")
    if len(set(managed)) != len(managed):
        raise RepositoryError(f"{metadata} 的 upstream.managed_paths 不能重复")
    for index, current in enumerate(managed):
        resolve_managed_path(base, current, f"{metadata}: upstream.managed_paths[{index}]")
    return Upstream(
        repository=strings["repository"],
        path=strings["path"],
        ref=strings["ref"],
        commit=strings["commit"],
        imported_at=dates["imported_at"],
        updated_at=dates["updated_at"],
        mode=strings["mode"],
        managed_paths=tuple(managed),
    )


def parse_plugin(workspace: Path) -> Plugin:
    require_directory(workspace, "插件工作区")
    name = validate_segment(workspace.name, "插件目录名")
    metadata = require_regular_file(workspace / "meta.toml", "meta.toml")
    try:
        document = tomllib.loads(read_regular_file(metadata).decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise RepositoryError(f"无法解析 {metadata}：{exc}") from exc
    if set(document) - TOP_LEVEL_FIELDS:
        raise RepositoryError(f"{metadata} 包含未知顶层字段：{sorted(set(document) - TOP_LEVEL_FIELDS)}")
    missing = TOP_LEVEL_FIELDS - {"upstream"} - set(document)
    if missing:
        raise RepositoryError(f"{metadata} 缺少顶层字段：{sorted(missing)}")
    schema_version = document["schema_version"]
    if type(schema_version) is not int or schema_version != 2:
        raise RepositoryError(f"{metadata} 的 schema_version 必须是整数 2")
    classification = document["classification"]
    if not isinstance(classification, str) or classification not in CLASSIFICATIONS:
        raise RepositoryError(f"{metadata} 的 classification 无效：{classification!r}")
    experimental = document["experimental"]
    if not isinstance(experimental, bool):
        raise RepositoryError(f"{metadata} 的 experimental 必须是布尔值")
    package_root = resolve_directory(workspace, document["package_root"], f"{metadata}: package_root", allow_dot=True)
    variants = document["variants"]
    if not isinstance(variants, dict) or set(variants) != VARIANT_FIELDS:
        raise RepositoryError(f"{metadata} 的 [variants] 必须只包含 default 和 base")
    default_variant = validate_segment(variants["default"], f"{metadata}: variants.default")
    if default_variant != "en":
        raise RepositoryError(f"{metadata} 的 variants.default 当前必须是 en")
    base = resolve_directory(package_root, variants["base"], f"{metadata}: variants.base")
    require_regular_file(base / "SKILL.md", f"{metadata}: default SKILL.md")

    overlays: dict[str, Path] = {}
    variants_root = workspace / "variants"
    variants_info = lstat_optional(variants_root)
    if variants_info is not None:
        if not stat.S_ISDIR(variants_info.st_mode):
            raise RepositoryError(f"variants 必须是非符号链接目录：{variants_root}")
        for child in sorted(variants_root.iterdir()):
            variant = validate_segment(child.name, f"{metadata}: overlay 名称")
            if variant == default_variant:
                raise RepositoryError(f"{metadata} 不得为 default 变体创建 overlay：{variant}")
            require_directory(child, f"{metadata}: overlay {variant}")
            validate_overlay(base, child)
            overlays[variant] = child

    upstream = parse_upstream(document.get("upstream"), classification, base, metadata)
    return Plugin(name, workspace, classification, experimental, package_root, default_variant, base, overlays, upstream)


def discover_plugins(repository_root: Path = REPO_ROOT) -> dict[str, Plugin]:
    plugins_root = require_directory(repository_root / PLUGINS_ROOT_NAME, "plugins 根目录")
    plugins: dict[str, Plugin] = {}
    for workspace in sorted(plugins_root.iterdir()):
        info = workspace.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise RepositoryError(f"plugins/ 只允许插件目录：{workspace}")
        plugin = parse_plugin(workspace)
        if plugin.name in plugins:
            raise RepositoryError(f"插件名重复：{plugin.name}")
        plugins[plugin.name] = plugin
    if not plugins:
        raise RepositoryError("plugins/ 中没有发现插件")
    return plugins


def _copy_file(source: Path, destination: Path) -> None:
    data = read_regular_file(source)
    mode = stat.S_IMODE(source.lstat().st_mode)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("wb") as stream:
            stream.write(data)
    except OSError as exc:
        raise RepositoryError(f"无法写入物化文件 {destination}：{exc}") from exc
    destination.chmod(mode)


def _copy_layer(source: Path, destination: Path) -> None:
    entries = scan_tree(source)
    for relative, current in entries.items():
        target = destination / relative
        if current.kind == "directory":
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(current.mode)
        else:
            _copy_file(source / relative, target)


def populate_materialized_skill(plugin: Plugin, variant: str, destination: Path) -> None:
    if destination.exists():
        if not destination.is_dir() or any(destination.iterdir()):
            raise RepositoryError(f"物化目标必须是不存在或为空的目录：{destination}")
    else:
        destination.mkdir(parents=True)
    _copy_layer(plugin.base, destination)
    overlay = plugin.source_for_variant(variant)
    if overlay is not None:
        _copy_layer(overlay, destination)
    skill_file = destination / "SKILL.md"
    if frontmatter_name(skill_file) != plugin.name:
        raise RepositoryError(f"物化后的 SKILL.md name 与插件名不一致：{skill_file}")


def directory_hash(directory: Path, *, exclude_install_metadata: bool = True) -> str:
    entries = scan_tree(directory, exclude_install_metadata=exclude_install_metadata)
    digest = hashlib.sha256()
    for relative, current in sorted(entries.items(), key=lambda item: item[0].as_posix()):
        fields = [
            relative.as_posix().encode(),
            current.kind.encode(),
            b"1" if current.mode & stat.S_IXUSR else b"0",
            (current.digest or "").encode(),
        ]
        for field in fields:
            digest.update(len(field).to_bytes(8, "big"))
            digest.update(field)
    return digest.hexdigest()


def materialized_hash(plugin: Plugin, variant: str) -> str:
    with tempfile.TemporaryDirectory(prefix=f"ruokee-skills-{plugin.name}-") as raw:
        destination = Path(raw) / plugin.name
        populate_materialized_skill(plugin, variant, destination)
        return directory_hash(destination)


def read_json_object(path: Path, field: str) -> dict[str, Any]:
    require_regular_file(path, field)
    try:
        value = json.loads(read_regular_file(path).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RepositoryError(f"无法解析 {field} {path}：{exc}") from exc
    if not isinstance(value, dict):
        raise RepositoryError(f"{field} 必须是 JSON object：{path}")
    return value


def codex_manifest(plugin: Plugin) -> dict[str, Any]:
    return read_json_object(plugin.package_root / ".codex-plugin" / "plugin.json", "Codex plugin manifest")


def claude_manifest(plugin: Plugin) -> dict[str, Any]:
    return read_json_object(plugin.package_root / ".claude-plugin" / "plugin.json", "Claude plugin manifest")


def base_version(plugin: Plugin) -> str:
    codex_version = codex_manifest(plugin).get("version")
    claude_version = claude_manifest(plugin).get("version")
    if not isinstance(codex_version, str) or not isinstance(claude_version, str):
        raise RepositoryError(f"插件 {plugin.name} 的宿主 manifest 缺少字符串 version")
    codex_base = codex_version.split("+", 1)[0]
    if codex_base != claude_version:
        raise RepositoryError(f"插件 {plugin.name} 的 Codex/Claude 基础版本不一致：{codex_version!r} != {claude_version!r}")
    return claude_version


def repository_state(repository_root: Path = REPO_ROOT) -> tuple[str, bool]:
    try:
        commit = subprocess.run(["git", "-C", str(repository_root), "rev-parse", "HEAD"], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(repository_root), "status", "--porcelain"], check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RepositoryError(f"无法读取仓库 Git 状态：{exc}") from exc
    return commit, dirty
