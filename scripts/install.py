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
import locale
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable

import rich_click as click
from rich.console import Console
from rich.table import Table


REPO_ROOT = Path(__file__).resolve().parent.parent
RESOURCE_DOMAINS = ("public", "experimential", "fork", "third-party")
METADATA_NAME = "meta.json"
MANAGER_NAME = "resource-installer"
SCHEMA_VERSION = 1
TARGETS = ("codex", "claude")

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


@dataclass(frozen=True)
class Resource:
    name: str
    kind: str
    domain: str
    workspace: Path
    variants: dict[str, Variant]


@dataclass(frozen=True)
class InstallationStatus:
    state: str
    variant: str | None = None
    source_hash: str | None = None
    installed_hash: str | None = None
    recorded_hash: str | None = None
    detail: str | None = None


def discover_resources(root: Path = REPO_ROOT) -> dict[str, Resource]:
    """从当前 Workspace 约定发现可安装资源。"""
    resources: dict[str, Resource] = {}
    for domain in RESOURCE_DOMAINS:
        domain_root = root / domain
        if not domain_root.is_dir():
            continue
        for workspace in sorted(path for path in domain_root.iterdir() if path.is_dir()):
            name = workspace.name
            variants: dict[str, Variant] = {}
            direct = workspace / name / "SKILL.md"
            if direct.is_file():
                variants["default"] = Variant("default", direct.parent)
            for candidate in sorted(path for path in workspace.iterdir() if path.is_dir()):
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
        return Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "skills"
    raise ResourceError(f"未知安装目标：{target}")


def destination_root(target: str, root: Path | None, global_install: bool = False) -> Path:
    if global_install:
        return default_root(target).expanduser().resolve()
    project_root = (root if root is not None else Path.cwd()).expanduser().resolve()
    if project_root.name == "skills" and project_root.parent.name == ".agents":
        return project_root
    if project_root.name == ".agents":
        return project_root / "skills"
    return project_root / ".agents" / "skills"


def hash_directory(directory: Path) -> str:
    """计算可复现的目录内容哈希，忽略由本工具写入的元数据。"""
    digest = hashlib.sha256()
    for path in sorted(directory.rglob("*"), key=lambda item: item.relative_to(directory).as_posix()):
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
            ("git", "rev-parse", "HEAD"), cwd=root, check=True, capture_output=True,
            text=True, timeout=5,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ("git", "status", "--porcelain"), cwd=root,
            check=True, capture_output=True, text=True, timeout=5,
        ).stdout.strip())
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
    if data.get("schema_version") != SCHEMA_VERSION or data.get("manager") != MANAGER_NAME:
        raise ResourceError(f"不支持的安装元数据：{metadata_path}")
    return data


def metadata_belongs_to(metadata: dict[str, Any], resource: Resource) -> bool:
    resource_data = metadata.get("resource", {})
    return (
        resource_data.get("name") == resource.name
        and resource_data.get("type") == resource.kind
    )


def choose_variant(resource: Resource, requested: str | None, installed: str | None = None) -> Variant:
    if requested:
        if requested not in resource.variants:
            choices = "、".join(resource.variants)
            raise ResourceError(f"{resource.name} 没有变体 {requested!r}；可选：{choices}")
        return resource.variants[requested]
    if installed in resource.variants:
        return resource.variants[installed]  # type: ignore[index]
    if len(resource.variants) == 1:
        return next(iter(resource.variants.values()))
    language = (locale.getlocale()[0] or os.environ.get("LANG", "")).lower()
    preferred = "zh" if language.startswith("zh") else "en"
    return resource.variants.get(preferred, next(iter(resource.variants.values())))


def metadata_for(resource: Resource, variant: Variant, target: str, content_hash: str) -> dict[str, Any]:
    commit, dirty = repository_state()
    return {
        "schema_version": SCHEMA_VERSION,
        "manager": MANAGER_NAME,
        "resource": {"name": resource.name, "type": resource.kind, "domain": resource.domain},
        "source": {
            "variant": variant.name,
            "path": variant.source.relative_to(REPO_ROOT).as_posix(),
            "repository_commit": commit,
            "repository_dirty": dirty,
            "content_hash": content_hash,
        },
        "installation": {
            "target": target,
            "installed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    }


def atomic_install(source: Path, destination: Path, metadata: dict[str, Any]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise ResourceError(f"拒绝覆盖符号链接：{destination}")
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.install-", dir=destination.parent))
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


def install_resource(resource: Resource, variant: Variant, target: str, root: Path) -> None:
    source_hash = hash_directory(variant.source)
    metadata = metadata_for(resource, variant, target, source_hash)
    atomic_install(variant.source, root / resource.name, metadata)


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
    source_hash = hash_directory(variant.source)
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
    return InstallationStatus(state, variant_name, source_hash, installed_hash, recorded_hash)


def require_resources(catalog: dict[str, Resource], names: Iterable[str]) -> list[Resource]:
    selected = []
    for name in names:
        if name not in catalog:
            raise ResourceError(f"仓库中不存在资源：{name}")
        selected.append(catalog[name])
    return selected


def target_options(function):
    function = click.option("--root", type=click.Path(path_type=Path, file_okay=False),
                            help="项目根目录；默认使用当前工作目录。") (function)
    function = click.option("--target", type=click.Choice(TARGETS),
                            help="全局安装目标。") (function)
    function = click.option("--global", "global_install", is_flag=True,
                            help="安装到 --target 对应的全局目录。") (function)
    return function


def global_target_options(function):
    function = click.option("--root", type=click.Path(path_type=Path, file_okay=False),
                            help="项目根目录；默认使用当前工作目录。") (function)
    function = click.option("--target", type=click.Choice(TARGETS), default="codex", show_default=True,
                            help="全局安装目标。") (function)
    function = click.option("--global", "global_install", is_flag=True,
                            help="安装到 --target 对应的全局目录。") (function)
    return function


def effective_target_options(
    target: str | None,
    root: Path | None,
    global_install: bool,
) -> tuple[str, Path | None, bool]:
    root_params = click.get_current_context().find_root().params
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
    target, root, global_install = effective_target_options(target, root, global_install)
    catalog = discover_resources()
    resolved_root = destination_root(target, root, global_install)
    table = Table(title=f"仓库资源 · {target} → {resolved_root}", header_style="bold cyan")
    table.add_column("资源")
    table.add_column("类型")
    table.add_column("来源")
    table.add_column("变体")
    table.add_column("状态")
    labels = {
        "not_installed": "[dim]未安装[/dim]", "current": "[green]已是最新[/green]",
        "update_available": "[yellow]可更新[/yellow]", "modified": "[magenta]本地已修改[/magenta]",
        "update_and_modified": "[red]可更新 / 本地已修改[/red]",
        "unmanaged": "[red]未受管理[/red]", "source_missing": "[red]源变体不存在[/red]",
    }
    for resource in catalog.values():
        status = status_for(resource, target, resolved_root)
        variants = ", ".join(resource.variants)
        table.add_row(resource.name, resource.kind, resource.domain, variants, labels[status.state])
    console.print(table)


@cli.command()
@click.argument("resources", nargs=-1, required=True, metavar="RESOURCE...")
@click.option("-v", "--variant", help="选择变体；一次安装多个资源时共同使用。")
@click.option("-f", "--force", is_flag=True, help="覆盖现有目录，包括未受本工具管理的目录。")
@target_options
def install(resources: tuple[str, ...], variant: str | None, force: bool,
            target: str | None, root: Path | None, global_install: bool) -> None:
    """安装一个或多个资源。"""
    target, root, global_install = effective_target_options(target, root, global_install)
    catalog = discover_resources()
    selected = require_resources(catalog, resources)
    resolved_root = destination_root(target, root, global_install)
    for resource in selected:
        destination = resolved_root / resource.name
        metadata = read_metadata(destination) if destination.is_dir() and not force else None
        if metadata is not None and not metadata_belongs_to(metadata, resource):
            metadata = None
        if destination.exists() and metadata is None and not force:
            raise ResourceError(f"{destination} 已存在且未受本工具管理；使用 --force 明确覆盖")
        installed_variant = metadata.get("source", {}).get("variant") if metadata else None
        chosen = choose_variant(resource, variant, installed_variant)
        if destination.exists() and not force:
            state = status_for(resource, target, resolved_root)
            if state.state == "current" and state.variant == chosen.name:
                console.print(f"[dim]跳过[/dim] {resource.name}：内容哈希一致")
                continue
            raise ResourceError(f"{resource.name} 已安装；请使用 update 或 change")
        install_resource(resource, chosen, target, resolved_root)
        console.print(f"[green]✓[/green] 已安装 {resource.name} [dim]({chosen.name})[/dim]")


@cli.command()
@click.argument("resources", nargs=-1, metavar="RESOURCE...")
@click.option("-y", "--yes", is_flag=True, help="不询问，更新所有发现的变化。")
@click.option("-v", "--variant", help="切换到指定变体。")
@click.option("--reinstall", is_flag=True, help="重新安装当前变体，恢复仓库版本。")
@target_options
def update(resources: tuple[str, ...], yes: bool, variant: str | None, reinstall: bool,
           target: str | None, root: Path | None, global_install: bool) -> None:
    """检查更新、切换变体，或重新安装资源。"""
    target, root, global_install = effective_target_options(target, root, global_install)
    catalog = discover_resources()
    resolved_root = destination_root(target, root, global_install)
    if variant and reinstall:
        raise ResourceError("--variant 与 --reinstall 不能同时使用")
    if (variant or reinstall) and not resources:
        raise ResourceError("使用 --variant 或 --reinstall 时必须指定资源")
    selected = require_resources(catalog, resources) if resources else list(catalog.values())

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
            console.print(f"[green]✓[/green] {action} {resource.name} [dim]({chosen.name})[/dim]")
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
            console.print(f"[red]跳过[/red] {resource.name}：{status.detail or '无法定位原变体'}")
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
        console.print(f"[green]✓[/green] 已更新 {resource.name} [dim]({chosen.name})[/dim]")


@cli.command()
@click.argument("resources", nargs=-1, required=True, metavar="RESOURCE...")
@click.option("-y", "--yes", is_flag=True, help="不询问，直接移除。")
@target_options
def remove(resources: tuple[str, ...], yes: bool, target: str | None, root: Path | None,
           global_install: bool) -> None:
    """移除一个或多个由本工具安装的资源。"""
    target, root, global_install = effective_target_options(target, root, global_install)
    catalog = discover_resources()
    selected = require_resources(catalog, resources)
    resolved_root = destination_root(target, root, global_install)
    removable: list[Resource] = []
    for resource in selected:
        destination = resolved_root / resource.name
        if not destination.exists():
            console.print(f"[dim]跳过[/dim] {resource.name}：尚未安装")
            continue
        metadata = None if destination.is_symlink() or not destination.is_dir() else read_metadata(destination)
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
