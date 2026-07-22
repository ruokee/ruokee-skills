#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "rich-click>=1.8.9,<2",
#   "rich>=13.9,<15",
# ]
# ///
"""安装和管理当前仓库中的资源。"""

import hashlib
import json
import os
import re
import stat
import tomllib
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

import rich_click as click
from rich.console import Console
from rich.table import Table


REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCE_DOMAINS = ("public", "experimential", "fork", "third-party")
METADATA_NAME = "meta.json"
MANAGER_NAME = "resource-installer"
SCHEMA_VERSION = 1
TARGETS = ("codex", "claude")
WORKSPACE_METADATA_NAME = "meta.toml"
V2_LAYOUT_VERSION = 2
V2_RESERVED_VARIANTS = frozenset(("skills", "variants"))

console = Console()
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_OPTION = "cyan"
click.rich_click.STYLE_COMMANDS_TABLE_COLUMN_WIDTH_RATIO = (1, 3)


class ResourceError(click.ClickException):
    """可直接展示给 CLI 用户的资源管理错误。"""


@dataclass(frozen=True)
class Variant:
    name: str
    source: Path
    layers: tuple["Layer", ...] = ()


@dataclass(frozen=True)
class Layer:
    role: str
    source: Path


@dataclass(frozen=True)
class Resource:
    name: str
    kind: str
    domain: str
    workspace: Path
    variants: dict[str, Variant]
    layout_version: int = 1
    default_variant: str | None = None


@dataclass(frozen=True)
class InstallationStatus:
    state: str
    variant: str | None = None
    source_hash: str | None = None
    installed_hash: str | None = None
    recorded_hash: str | None = None
    detail: str | None = None


def lstat_optional(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ResourceError(f"无法检查路径：{path}（{exc}）") from exc


def read_regular_file_no_follow(path: Path) -> bytes:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ResourceError(f"无法安全读取普通文件：{path}（{exc}）") from exc
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode):
            raise ResourceError(f"路径不是普通文件：{path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    except OSError as exc:
        raise ResourceError(f"无法读取文件：{path}（{exc}）") from exc
    finally:
        os.close(descriptor)


def validate_workspace_directory(workspace: Path) -> None:
    info = lstat_optional(workspace)
    if info is None or not stat.S_ISDIR(info.st_mode):
        raise ResourceError(f"meta-v2 Workspace 必须是非符号链接目录：{workspace}")


def parse_relative_directory(workspace: Path, value: Any, field: str) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or value.startswith("/")
        or "\\" in value
    ):
        raise ResourceError(f"{field} 必须是非空的 Workspace 相对 POSIX 路径")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ResourceError(f"{field} 包含非法路径段：{value!r}")
    current = workspace
    for part in parts:
        current /= part
        info = lstat_optional(current)
        if info is None:
            raise ResourceError(f"{field} 指向不存在的路径：{current}")
        if not stat.S_ISDIR(info.st_mode):
            raise ResourceError(
                f"{field} 的所有路径组件都必须是非符号链接目录：{current}"
            )
    return current


def validate_variant_name(name: Any, field: str) -> str:
    if not isinstance(name, str) or not name or name in (".", ".."):
        raise ResourceError(f"{field} 必须是非空变体名称")
    if name in V2_RESERVED_VARIANTS:
        raise ResourceError(f"{field} 使用了保留名称：{name}")
    if any(ord(character) < 32 or ord(character) == 127 for character in name):
        raise ResourceError(f"{field} 不能包含控制字符")
    if "/" in name or "\\" in name:
        raise ResourceError(f"{field} 不能包含路径分隔符")
    return name


def frontmatter_name(skill_file: Path) -> str:
    try:
        content = read_regular_file_no_follow(skill_file).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ResourceError(f"SKILL.md 不是有效 UTF-8：{skill_file}") from exc
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ResourceError(f"SKILL.md 缺少 YAML frontmatter：{skill_file}")
    try:
        end = next(
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration as exc:
        raise ResourceError(f"SKILL.md frontmatter 未闭合：{skill_file}") from exc
    names: list[str] = []
    descriptions: list[str] = []
    for line in lines[1:end]:
        match = re.fullmatch(r"name\s*:\s*(.*?)\s*", line)
        if match:
            value = match.group(1)
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            names.append(value)
        description = re.fullmatch(r"description\s*:\s*(.*?)\s*", line)
        if description:
            descriptions.append(description.group(1))
    if len(names) != 1 or not names[0]:
        raise ResourceError(f"SKILL.md frontmatter 必须包含唯一的 name：{skill_file}")
    if len(descriptions) != 1 or not descriptions[0]:
        raise ResourceError(
            f"SKILL.md frontmatter 必须包含唯一且非空的 description：{skill_file}"
        )
    return names[0]


def forbidden_layer_path(relative: Path) -> bool:
    return (
        relative.name == METADATA_NAME
        or "__pycache__" in relative.parts
        or relative.match("*.py[cod]")
    )


def scan_layer(source: Path, role: str) -> dict[Path, str]:
    root_info = lstat_optional(source)
    if root_info is None or not stat.S_ISDIR(root_info.st_mode):
        raise ResourceError(f"{role} layer 必须是非符号链接目录：{source}")
    entries: dict[Path, str] = {}

    def visit(directory: Path, relative_directory: Path) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            raise ResourceError(f"无法遍历 {role} layer：{directory}（{exc}）") from exc
        for child in children:
            relative = relative_directory / child.name
            if forbidden_layer_path(relative):
                raise ResourceError(
                    f"{role} layer 包含保留或生成文件：{relative.as_posix()}"
                )
            try:
                info = child.stat(follow_symlinks=False)
            except OSError as exc:
                raise ResourceError(
                    f"无法检查 {role} layer 路径：{child.path}（{exc}）"
                ) from exc
            if stat.S_ISDIR(info.st_mode):
                entries[relative] = "directory"
                visit(Path(child.path), relative)
            elif stat.S_ISREG(info.st_mode):
                entries[relative] = "file"
            else:
                raise ResourceError(
                    f"{role} layer 只允许非符号链接目录和普通文件：{relative.as_posix()}"
                )

    visit(source, Path())
    return entries


def validate_overlay(base_entries: dict[Path, str], overlay: Path) -> dict[Path, str]:
    overlay_entries = scan_layer(overlay, "overlay")
    if not any(kind == "file" for kind in overlay_entries.values()):
        raise ResourceError(f"overlay 至少需要一个普通文件：{overlay}")
    for relative, overlay_kind in overlay_entries.items():
        base_kind = base_entries.get(relative)
        if base_kind is not None and base_kind != overlay_kind:
            raise ResourceError(
                f"overlay 不允许 file/directory 类型替换：{relative.as_posix()}"
            )
    return overlay_entries


def parse_workspace_metadata(workspace: Path) -> dict[str, Any]:
    metadata_path = workspace / WORKSPACE_METADATA_NAME
    info = lstat_optional(metadata_path)
    if info is None:
        raise ResourceError(f"meta-v2 元数据不存在：{metadata_path}")
    if not stat.S_ISREG(info.st_mode):
        raise ResourceError(f"meta.toml 必须是非符号链接普通文件：{metadata_path}")
    try:
        metadata = tomllib.loads(
            read_regular_file_no_follow(metadata_path).decode("utf-8")
        )
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ResourceError(f"meta.toml 损坏：{metadata_path}（{exc}）") from exc
    expected_top = {"schema_version", "resource_type", "variants"}
    unknown_top = set(metadata) - expected_top
    missing_top = expected_top - set(metadata)
    if unknown_top or missing_top:
        detail = ", ".join(sorted(unknown_top or missing_top))
        label = "未知字段" if unknown_top else "缺少字段"
        raise ResourceError(f"meta.toml {label}：{detail}")
    if metadata["schema_version"] != SCHEMA_VERSION or isinstance(
        metadata["schema_version"], bool
    ):
        raise ResourceError(
            f"不支持的 meta.toml schema_version：{metadata['schema_version']!r}"
        )
    if metadata["resource_type"] != "skill":
        raise ResourceError(
            f"不支持的 meta.toml resource_type：{metadata['resource_type']!r}"
        )
    variants = metadata["variants"]
    if not isinstance(variants, dict):
        raise ResourceError("meta.toml variants 必须是 table")
    expected_variants = {"layout_version", "default", "base"}
    unknown_variants = set(variants) - expected_variants
    missing_variants = expected_variants - set(variants)
    if unknown_variants or missing_variants:
        detail = ", ".join(sorted(unknown_variants or missing_variants))
        label = "未知字段" if unknown_variants else "缺少字段"
        raise ResourceError(f"meta.toml variants {label}：{detail}")
    if variants["layout_version"] != V2_LAYOUT_VERSION or isinstance(
        variants["layout_version"], bool
    ):
        raise ResourceError(
            f"不支持的 variants.layout_version：{variants['layout_version']!r}"
        )
    return variants


def discover_v2_resource(domain: str, workspace: Path) -> Resource:
    validate_workspace_directory(workspace)
    metadata = parse_workspace_metadata(workspace)
    name = workspace.name
    default_variant = validate_variant_name(metadata["default"], "variants.default")
    base = parse_relative_directory(workspace, metadata["base"], "variants.base")
    if base.name != name:
        raise ResourceError(
            f"base Skill 目录名必须与 Workspace 名一致：{base.name!r} != {name!r}"
        )
    skill_file = base / "SKILL.md"
    skill_info = lstat_optional(skill_file)
    if skill_info is None or not stat.S_ISREG(skill_info.st_mode):
        raise ResourceError(f"base 必须包含非符号链接普通文件 SKILL.md：{skill_file}")
    if frontmatter_name(skill_file) != name:
        raise ResourceError(f"SKILL.md frontmatter name 必须为 {name!r}：{skill_file}")
    base_entries = scan_layer(base, "base")
    base_layer = Layer("base", base)
    variants = {
        default_variant: Variant(default_variant, base, (base_layer,)),
    }
    overlays_root = workspace / "variants"
    overlays_info = lstat_optional(overlays_root)
    if overlays_info is not None:
        if not stat.S_ISDIR(overlays_info.st_mode):
            raise ResourceError(f"variants 必须是非符号链接目录：{overlays_root}")
        try:
            overlay_entries = sorted(
                os.scandir(overlays_root), key=lambda item: item.name
            )
        except OSError as exc:
            raise ResourceError(f"无法遍历 variants：{overlays_root}（{exc}）") from exc
        for entry in overlay_entries:
            overlay_name = validate_variant_name(entry.name, "overlay 名称")
            try:
                overlay_info = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ResourceError(f"无法检查 overlay：{entry.path}（{exc}）") from exc
            if not stat.S_ISDIR(overlay_info.st_mode):
                raise ResourceError(f"overlay 必须是非符号链接目录：{entry.path}")
            if overlay_name == default_variant:
                raise ResourceError(f"overlay 不能与 default 同名：{overlay_name}")
            overlay = Path(entry.path)
            overlay_layer_entries = validate_overlay(base_entries, overlay)
            if overlay_layer_entries.get(Path("SKILL.md")) == "file":
                if frontmatter_name(overlay / "SKILL.md") != name:
                    raise ResourceError(
                        f"overlay SKILL.md frontmatter name 必须为 {name!r}：{overlay / 'SKILL.md'}"
                    )
            variants[overlay_name] = Variant(
                overlay_name,
                base,
                (base_layer, Layer("overlay", overlay)),
            )
    expected_base = base
    for candidate in sorted(path for path in workspace.iterdir() if path.is_dir()):
        artifact_root = candidate / name
        artifact = artifact_root / "SKILL.md"
        if artifact.is_file() and artifact_root != expected_base:
            relative = artifact_root.relative_to(workspace)
            raise ResourceError(
                f"mixed-variant-layout：发现旧 v1 Skill 树 {relative.as_posix()}"
            )
    return Resource(
        name,
        "skill",
        domain,
        workspace,
        variants,
        layout_version=V2_LAYOUT_VERSION,
        default_variant=default_variant,
    )


def discover_resources(root: Path = REPO_ROOT) -> dict[str, Resource]:
    """从当前 Workspace 约定发现可安装资源。"""
    resources: dict[str, Resource] = {}
    for domain in RESOURCE_DOMAINS:
        domain_root = root / domain
        if not domain_root.is_dir():
            continue
        for workspace in sorted(
            path for path in domain_root.iterdir() if path.is_dir()
        ):
            name = workspace.name
            meta_info = lstat_optional(workspace / WORKSPACE_METADATA_NAME)
            if meta_info is not None:
                resource = discover_v2_resource(domain, workspace)
                if name in resources:
                    previous = resources[name].workspace.relative_to(root)
                    current = workspace.relative_to(root)
                    raise ResourceError(
                        f"资源名称重复：{name}（{previous}、{current}）"
                    )
                resources[name] = resource
                continue
            variants: dict[str, Variant] = {}
            direct = workspace / name / "SKILL.md"
            if direct.is_file():
                variants["default"] = Variant("default", direct.parent)
            for candidate in sorted(
                path for path in workspace.iterdir() if path.is_dir()
            ):
                artifact = candidate / name / "SKILL.md"
                if artifact.is_file():
                    variants[candidate.name] = Variant(candidate.name, artifact.parent)
            if not variants:
                continue
            if name in resources:
                previous = resources[name].workspace.relative_to(root)
                current = workspace.relative_to(root)
                raise ResourceError(f"资源名称重复：{name}（{previous}、{current}）")
            resources[name] = Resource(name, "skill", domain, workspace, variants)
    return resources


def default_root(target: str) -> Path:
    if target == "codex":
        base = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        return base / "skills"
    if target == "claude":
        return (
            Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
            / "skills"
        )
    raise ResourceError(f"未知安装目标：{target}")


def destination_root(
    target: str, root: Path | None, global_install: bool = False
) -> Path:
    if global_install:
        return default_root(target).expanduser().resolve()
    project_root = (root if root is not None else Path.cwd()).expanduser().resolve()
    if project_root.name == "skills" and project_root.parent.name == ".agents":
        return project_root
    if project_root.name == ".agents":
        return project_root / "skills"
    return project_root / ".agents" / "skills"


def copy_regular_file_no_follow(source: Path, destination: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        source_descriptor = os.open(source, flags)
    except OSError as exc:
        raise ResourceError(f"无法安全复制普通文件：{source}（{exc}）") from exc
    try:
        source_info = os.fstat(source_descriptor)
        if not stat.S_ISREG(source_info.st_mode):
            raise ResourceError(f"复制期间源路径不再是普通文件：{source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination_descriptor = os.open(
            destination,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
            stat.S_IMODE(source_info.st_mode),
        )
        try:
            with (
                os.fdopen(source_descriptor, "rb", closefd=False) as source_stream,
                os.fdopen(
                    destination_descriptor, "wb", closefd=False
                ) as destination_stream,
            ):
                shutil.copyfileobj(
                    source_stream, destination_stream, length=1024 * 1024
                )
                destination_stream.flush()
            os.fchmod(destination_descriptor, stat.S_IMODE(source_info.st_mode))
        finally:
            os.close(destination_descriptor)
        os.utime(
            destination,
            ns=(source_info.st_atime_ns, source_info.st_mtime_ns),
            follow_symlinks=False,
        )
    except OSError as exc:
        raise ResourceError(f"无法复制普通文件：{source}（{exc}）") from exc
    finally:
        os.close(source_descriptor)


def copy_layer(source: Path, destination: Path, entries: dict[Path, str]) -> None:
    for relative, kind in sorted(entries.items(), key=lambda item: item[0].as_posix()):
        source_path = source / relative
        destination_path = destination / relative
        if kind == "directory":
            source_info = lstat_optional(source_path)
            if source_info is None or not stat.S_ISDIR(source_info.st_mode):
                raise ResourceError(f"复制期间源路径不再是目录：{source_path}")
            destination_path.mkdir(parents=True, exist_ok=True)
            destination_path.chmod(stat.S_IMODE(source_info.st_mode))
            continue
        copy_regular_file_no_follow(source_path, destination_path)


@contextmanager
def materialized_variant(
    resource: Resource, variant: Variant
) -> Generator[Path, None, None]:
    if resource.layout_version == 1:
        yield variant.source
        return
    if resource.layout_version != V2_LAYOUT_VERSION or not variant.layers:
        raise ResourceError(
            f"不支持的资源布局：{resource.name} layout_version={resource.layout_version}"
        )
    base_layer = variant.layers[0]
    if base_layer.role != "base":
        raise ResourceError(
            f"meta-v2 变体缺少首个 base layer：{resource.name}/{variant.name}"
        )
    base_entries = scan_layer(base_layer.source, "base")
    overlay_entries: dict[Path, str] | None = None
    overlay_layer: Layer | None = None
    if len(variant.layers) > 2:
        raise ResourceError(
            f"meta-v2 第一版只允许单个 overlay：{resource.name}/{variant.name}"
        )
    if len(variant.layers) == 2:
        overlay_layer = variant.layers[1]
        if overlay_layer.role != "overlay":
            raise ResourceError(
                f"meta-v2 第二个 layer 必须是 overlay：{resource.name}/{variant.name}"
            )
        overlay_entries = validate_overlay(base_entries, overlay_layer.source)
    with tempfile.TemporaryDirectory(
        prefix=f".{resource.name}.{variant.name}.materialized-"
    ) as temporary:
        materialized = Path(temporary) / resource.name
        materialized.mkdir()
        copy_layer(base_layer.source, materialized, base_entries)
        if overlay_entries is not None and overlay_layer is not None:
            copy_layer(overlay_layer.source, materialized, overlay_entries)
        materialized_skill = materialized / "SKILL.md"
        if frontmatter_name(materialized_skill) != resource.name:
            raise ResourceError(
                f"物化后的 SKILL.md frontmatter name 必须为 {resource.name!r}：{materialized_skill}"
            )
        yield materialized


def hash_variant(resource: Resource, variant: Variant) -> str:
    with materialized_variant(resource, variant) as source:
        return hash_directory(source)


def hash_directory(directory: Path) -> str:
    """计算可复现的目录内容哈希，忽略由本工具写入的元数据。"""
    digest = hashlib.sha256()
    for path in sorted(
        directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix()
    ):
        relative = path.relative_to(directory).as_posix()
        if relative == METADATA_NAME:
            continue
        if path.is_symlink():
            digest.update(b"L\0")
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(os.readlink(path).encode())
        elif path.is_file():
            digest.update(b"F\0")
            digest.update(relative.encode())
            digest.update(b"\0")
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
        elif path.is_dir():
            digest.update(b"D\0")
            digest.update(relative.encode())
            digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def repository_state(root: Path = REPO_ROOT) -> tuple[str, bool]:
    try:
        commit = subprocess.run(
            ("git", "rev-parse", "HEAD"),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ("git", "status", "--porcelain"),
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        )
    except (FileNotFoundError, subprocess.SubprocessError) as exc:
        raise ResourceError(f"无法读取仓库版本：{exc}") from exc
    return commit, dirty


def read_metadata(destination: Path) -> dict[str, Any] | None:
    metadata_path = destination / METADATA_NAME
    if not metadata_path.is_file():
        return None
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResourceError(f"安装元数据损坏：{metadata_path}（{exc}）") from exc
    if (
        data.get("schema_version") != SCHEMA_VERSION
        or data.get("manager") != MANAGER_NAME
    ):
        raise ResourceError(f"不支持的安装元数据：{metadata_path}")
    return data


def metadata_belongs_to(metadata: dict[str, Any], resource: Resource) -> bool:
    resource_data = metadata.get("resource", {})
    return (
        resource_data.get("name") == resource.name
        and resource_data.get("type") == resource.kind
    )


def choose_variant(
    resource: Resource, requested: str | None, installed: str | None = None
) -> Variant:
    if requested:
        if requested not in resource.variants:
            choices = "、".join(resource.variants)
            raise ResourceError(
                f"{resource.name} 没有变体 {requested!r}；可选：{choices}"
            )
        return resource.variants[requested]
    if installed in resource.variants:
        return resource.variants[installed]  # type: ignore[index]
    if resource.layout_version == V2_LAYOUT_VERSION:
        if resource.default_variant not in resource.variants:
            raise ResourceError(f"{resource.name} 的 meta default 变体不存在")
        return resource.variants[resource.default_variant]  # type: ignore[index]
    if len(resource.variants) == 1:
        return next(iter(resource.variants.values()))
    for preferred in ("default", "en"):
        if preferred in resource.variants:
            return resource.variants[preferred]
    return next(iter(resource.variants.values()))


def metadata_for(
    resource: Resource, variant: Variant, target: str, content_hash: str
) -> dict[str, Any]:
    commit, dirty = repository_state()
    source: dict[str, Any] = {
        "variant": variant.name,
        "path": variant.source.relative_to(REPO_ROOT).as_posix(),
        "repository_commit": commit,
        "repository_dirty": dirty,
        "content_hash": content_hash,
    }
    if resource.layout_version == V2_LAYOUT_VERSION:
        source["path"] = resource.workspace.relative_to(REPO_ROOT).as_posix()
        source["layout_version"] = V2_LAYOUT_VERSION
        source["layers"] = [
            {
                "role": layer.role,
                "path": layer.source.relative_to(REPO_ROOT).as_posix(),
            }
            for layer in variant.layers
        ]
    return {
        "schema_version": SCHEMA_VERSION,
        "manager": MANAGER_NAME,
        "resource": {
            "name": resource.name,
            "type": resource.kind,
            "domain": resource.domain,
        },
        "source": source,
        "installation": {
            "target": target,
            "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def atomic_install(source: Path, destination: Path, metadata: dict[str, Any]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ResourceError(f"拒绝覆盖符号链接：{destination}")
    staging = Path(
        tempfile.mkdtemp(prefix=f".{destination.name}.install-", dir=destination.parent)
    )
    backup = destination.parent / f".{destination.name}.backup-{os.getpid()}"
    try:
        shutil.copytree(source, staging, dirs_exist_ok=True, symlinks=True)
        (staging / METADATA_NAME).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if destination.exists():
            if backup.exists():
                raise ResourceError(f"临时备份路径已存在：{backup}")
            destination.rename(backup)
        staging.rename(destination)
        if backup.exists():
            if backup.is_dir() and not backup.is_symlink():
                shutil.rmtree(backup)
            else:
                backup.unlink()
    except Exception:
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def install_resource(
    resource: Resource, variant: Variant, target: str, root: Path
) -> None:
    with materialized_variant(resource, variant) as source:
        source_hash = hash_directory(source)
        metadata = metadata_for(resource, variant, target, source_hash)
        atomic_install(source, root / resource.name, metadata)


def status_for(resource: Resource, target: str, root: Path) -> InstallationStatus:
    destination = root / resource.name
    if not destination.exists():
        return InstallationStatus("not_installed")
    metadata = read_metadata(destination)
    if metadata is None:
        return InstallationStatus("unmanaged", detail="目标目录没有管理元数据")
    if not metadata_belongs_to(metadata, resource):
        return InstallationStatus("unmanaged", detail="元数据属于其他资源")
    variant_name = metadata.get("source", {}).get("variant")
    if variant_name not in resource.variants:
        return InstallationStatus("source_missing", variant=str(variant_name))
    variant = resource.variants[variant_name]
    source_hash = hash_variant(resource, variant)
    installed_hash = hash_directory(destination)
    recorded_hash = metadata.get("source", {}).get("content_hash")
    source_changed = source_hash != recorded_hash
    local_changed = installed_hash != recorded_hash
    if source_hash == installed_hash:
        state = "current"
    elif source_changed and local_changed:
        state = "update_and_modified"
    elif source_changed:
        state = "update_available"
    else:
        state = "modified"
    return InstallationStatus(
        state, variant_name, source_hash, installed_hash, recorded_hash
    )


def require_resources(
    catalog: dict[str, Resource], names: Iterable[str]
) -> list[Resource]:
    selected = []
    for name in names:
        if name not in catalog:
            raise ResourceError(f"仓库中不存在资源：{name}")
        selected.append(catalog[name])
    return selected


def target_options(function):
    function = click.option(
        "--root",
        type=click.Path(path_type=Path, file_okay=False),
        help="项目根目录；默认使用当前工作目录。",
    )(function)
    function = click.option(
        "--target", type=click.Choice(TARGETS), help="全局安装目标。"
    )(function)
    function = click.option(
        "--global",
        "global_install",
        is_flag=True,
        help="安装到 --target 对应的全局目录。",
    )(function)
    return function


def global_target_options(function):
    function = click.option(
        "--root",
        type=click.Path(path_type=Path, file_okay=False),
        help="项目根目录；默认使用当前工作目录。",
    )(function)
    function = click.option(
        "--target",
        type=click.Choice(TARGETS),
        default="codex",
        show_default=True,
        help="全局安装目标。",
    )(function)
    function = click.option(
        "--global",
        "global_install",
        is_flag=True,
        help="安装到 --target 对应的全局目录。",
    )(function)
    return function


def effective_target_options(
    target: str | None,
    root: Path | None,
    global_install: bool,
) -> tuple[str, Path | None, bool]:
    context = click.get_current_context()
    if context is None:
        raise ResourceError("无法读取 CLI 上下文")
    root_params = context.find_root().params
    effective_target = target or root_params.get("target") or "codex"
    effective_root = root if root is not None else root_params.get("root")
    effective_global = global_install or bool(root_params.get("global_install"))
    if effective_global and effective_root is not None:
        raise ResourceError("--global 与 --root 不能同时使用")
    return effective_target, effective_root, effective_global


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option("1", prog_name="resource-installer")
@global_target_options
def cli(target: str, root: Path | None, global_install: bool) -> None:
    """[bold]管理当前仓库中的可安装资源。[/bold]

    当前支持 Skill，并为后续 Package、Plugin 等资源保留统一模型。
    """


@cli.command("list")
@target_options
def list_resources(target: str | None, root: Path | None, global_install: bool) -> None:
    """列出仓库资源及其安装状态。"""
    target, root, global_install = effective_target_options(
        target, root, global_install
    )
    catalog = discover_resources()
    resolved_root = destination_root(target, root, global_install)
    table = Table(
        title=f"仓库资源 · {target} → {resolved_root}", header_style="bold cyan"
    )
    table.add_column("资源")
    table.add_column("类型")
    table.add_column("来源")
    table.add_column("变体")
    table.add_column("状态")
    labels = {
        "not_installed": "[dim]未安装[/dim]",
        "current": "[green]已是最新[/green]",
        "update_available": "[yellow]可更新[/yellow]",
        "modified": "[magenta]本地已修改[/magenta]",
        "update_and_modified": "[red]可更新 / 本地已修改[/red]",
        "unmanaged": "[red]未受管理[/red]",
        "source_missing": "[red]源变体不存在[/red]",
    }
    for resource in catalog.values():
        status = status_for(resource, target, resolved_root)
        variants = ", ".join(resource.variants)
        table.add_row(
            resource.name,
            resource.kind,
            resource.domain,
            variants,
            labels[status.state],
        )
    console.print(table)


@cli.command()
@click.argument("resources", nargs=-1, required=True, metavar="RESOURCE...")
@click.option("-v", "--variant", help="选择变体；一次安装多个资源时共同使用。")
@click.option(
    "-f", "--force", is_flag=True, help="覆盖现有目录，包括未受本工具管理的目录。"
)
@target_options
def install(
    resources: tuple[str, ...],
    variant: str | None,
    force: bool,
    target: str | None,
    root: Path | None,
    global_install: bool,
) -> None:
    """安装一个或多个资源。"""
    target, root, global_install = effective_target_options(
        target, root, global_install
    )
    catalog = discover_resources()
    selected = require_resources(catalog, resources)
    resolved_root = destination_root(target, root, global_install)
    for resource in selected:
        destination = resolved_root / resource.name
        metadata = (
            read_metadata(destination) if destination.is_dir() and not force else None
        )
        if metadata is not None and not metadata_belongs_to(metadata, resource):
            metadata = None
        if destination.exists() and metadata is None and not force:
            raise ResourceError(
                f"{destination} 已存在且未受本工具管理；使用 --force 明确覆盖"
            )
        installed_variant = (
            metadata.get("source", {}).get("variant") if metadata else None
        )
        chosen = choose_variant(resource, variant, installed_variant)
        if destination.exists() and not force:
            state = status_for(resource, target, resolved_root)
            if state.state == "current" and state.variant == chosen.name:
                console.print(f"[dim]跳过[/dim] {resource.name}：内容哈希一致")
                continue
            raise ResourceError(f"{resource.name} 已安装；请使用 update 或 change")
        install_resource(resource, chosen, target, resolved_root)
        console.print(
            f"[green]✓[/green] 已安装 {resource.name} [dim]({chosen.name})[/dim]"
        )


@cli.command()
@click.argument("resources", nargs=-1, metavar="RESOURCE...")
@click.option("-y", "--yes", is_flag=True, help="不询问，更新所有发现的变化。")
@click.option("-v", "--variant", help="切换到指定变体。")
@click.option("--reinstall", is_flag=True, help="重新安装当前变体，恢复仓库版本。")
@target_options
def update(
    resources: tuple[str, ...],
    yes: bool,
    variant: str | None,
    reinstall: bool,
    target: str | None,
    root: Path | None,
    global_install: bool,
) -> None:
    """检查更新、切换变体，或重新安装资源。"""
    target, root, global_install = effective_target_options(
        target, root, global_install
    )
    catalog = discover_resources()
    resolved_root = destination_root(target, root, global_install)
    if variant and reinstall:
        raise ResourceError("--variant 与 --reinstall 不能同时使用")
    if (variant or reinstall) and not resources:
        raise ResourceError("使用 --variant 或 --reinstall 时必须指定资源")
    selected = (
        require_resources(catalog, resources) if resources else list(catalog.values())
    )

    if variant or reinstall:
        for resource in selected:
            status = status_for(resource, target, resolved_root)
            if status.state == "not_installed":
                raise ResourceError(f"{resource.name} 尚未安装")
            if status.state in ("unmanaged", "source_missing"):
                raise ResourceError(
                    f"无法更改 {resource.name}：{status.detail or '无法定位原变体'}"
                )
            chosen = choose_variant(resource, variant, status.variant)
            install_resource(resource, chosen, target, resolved_root)
            action = "已重新安装" if reinstall else "已切换"
            console.print(
                f"[green]✓[/green] {action} {resource.name} [dim]({chosen.name})[/dim]"
            )
        return

    pending: list[tuple[Resource, InstallationStatus]] = []
    for resource in selected:
        status = status_for(resource, target, resolved_root)
        if status.state == "not_installed":
            if resources:
                console.print(f"[dim]跳过[/dim] {resource.name}：尚未安装")
            continue
        if status.state == "current":
            console.print(f"[dim]跳过[/dim] {resource.name}：内容哈希一致")
            continue
        if status.state in ("unmanaged", "source_missing"):
            console.print(
                f"[red]跳过[/red] {resource.name}：{status.detail or '无法定位原变体'}"
            )
            continue
        pending.append((resource, status))
    if not pending:
        console.print("[green]没有需要更新的资源。[/green]")
        return
    table = Table(title="待更新资源", header_style="bold yellow")
    table.add_column("资源")
    table.add_column("变体")
    table.add_column("变化")
    for resource, status in pending:
        change = "仓库内容已变化"
        if status.state == "modified":
            change = "安装目录被修改；将恢复仓库版本"
        elif status.state == "update_and_modified":
            change = "仓库与安装目录均有变化；本地修改将被覆盖"
        table.add_row(resource.name, status.variant or "-", change)
    console.print(table)
    if not yes and not click.confirm("更新以上资源？", default=False):
        raise click.Abort()
    for resource, status in pending:
        chosen = choose_variant(resource, status.variant)
        install_resource(resource, chosen, target, resolved_root)
        console.print(
            f"[green]✓[/green] 已更新 {resource.name} [dim]({chosen.name})[/dim]"
        )


@cli.command()
@click.argument("resources", nargs=-1, required=True, metavar="RESOURCE...")
@click.option("-y", "--yes", is_flag=True, help="不询问，直接移除。")
@target_options
def remove(
    resources: tuple[str, ...],
    yes: bool,
    target: str | None,
    root: Path | None,
    global_install: bool,
) -> None:
    """移除一个或多个由本工具安装的资源。"""
    target, root, global_install = effective_target_options(
        target, root, global_install
    )
    catalog = discover_resources()
    selected = require_resources(catalog, resources)
    resolved_root = destination_root(target, root, global_install)
    removable: list[Resource] = []
    for resource in selected:
        destination = resolved_root / resource.name
        if not destination.exists():
            console.print(f"[dim]跳过[/dim] {resource.name}：尚未安装")
            continue
        metadata = (
            None
            if destination.is_symlink() or not destination.is_dir()
            else read_metadata(destination)
        )
        if metadata is None or not metadata_belongs_to(metadata, resource):
            raise ResourceError(f"拒绝移除未受本工具管理的目录：{destination}")
        removable.append(resource)
    if not removable:
        return
    names = "、".join(resource.name for resource in removable)
    if not yes and not click.confirm(f"移除 {names}？", default=False):
        raise click.Abort()
    for resource in removable:
        shutil.rmtree(resolved_root / resource.name)
        console.print(f"[green]✓[/green] 已移除 {resource.name}")


if __name__ == "__main__":
    cli()
