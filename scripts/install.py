#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "rich-click>=1.8.9,<2",
#   "rich>=13.9,<15",
# ]
# ///
"""安装、更新或重置 ruokee-skills 的变体与项目 local Skill。"""

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import rich_click as click
from rich.console import Console

from repository import (
    PROJECT_INSTALL_METADATA,
    REPO_ROOT,
    Plugin,
    RepositoryError,
    base_version,
    directory_hash,
    discover_plugins,
    materialized_hash,
    populate_materialized_skill,
    read_json_object,
    read_regular_file,
    repository_state,
    scan_tree,
)


MARKETPLACE_NAME = "ruokee-skills"
HOSTS = ("codex", "claude", "pi")
USER_STATE_SCHEMA = 1
PROJECT_STATE_SCHEMA = 1
USER_STATE_FIELDS = frozenset(("host", "plugin", "variant", "source_commit", "installation_id", "base_version", "baseline_hash", "managed_hash", "updated_at"))
PROJECT_STATE_FIELDS = frozenset(("schema_version", "plugin", "variant", "hosts", "source_commit", "baseline_hash", "managed_hash", "installed_at", "updated_at"))
HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
SUPPORTED_HOST_VERSIONS = {
    "codex": (0, 145, 0),
    "claude": (2, 1, 207),
    "pi": (0, 80, 6),
}
HOST_VERSION_COMMANDS = {
    "codex": ("codex", "--version"),
    "claude": ("claude", "--version"),
    "pi": ("pi", "--version"),
}
COMMAND_TIMEOUT_SECONDS = 120

console = Console()
click.rich_click.USE_RICH_MARKUP = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_OPTION = "cyan"
click.rich_click.STYLE_COMMANDS_TABLE_COLUMN_WIDTH_RATIO = (1, 3)


class InstallError(click.ClickException):
    """可以直接展示给 CLI 用户的安装错误。"""


@dataclass(frozen=True)
class NativeInstall:
    host: str
    plugin: str
    root: Path
    skill_root: Path
    version: str
    enabled: bool = True
    source_arg: str | None = None


@dataclass(frozen=True)
class ProjectTarget:
    path: Path
    hosts: tuple[str, ...]


def now_rfc3339() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def remove_path(path: Path) -> None:
    info = path.lstat()
    if stat.S_ISDIR(info.st_mode):
        shutil.rmtree(path)
    else:
        path.unlink()


def write_json_atomic(path: Path, value: dict[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw_temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(raw_temporary)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        if temporary.exists():
            temporary.unlink()
        raise


def runtime_lock_root() -> Path:
    raw = os.environ.get("XDG_RUNTIME_DIR")
    if raw:
        root = Path(raw).expanduser() / "ruokee-skills"
    else:
        root = user_state_root() / "runtime"
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    return root


@contextmanager
def operation_lock(scope: str, project: Path | None = None) -> Iterator[None]:
    if scope == "user":
        lock_path = user_state_root() / "operation.lock"
    else:
        assert project is not None
        identity = hashlib.sha256(os.fsencode(project)).hexdigest()[:24]
        lock_path = runtime_lock_root() / f"project-{identity}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def run_command(argv: tuple[str, ...], *, cwd: Path = REPO_ROOT) -> str:
    try:
        result = subprocess.run(argv, cwd=cwd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=COMMAND_TIMEOUT_SECONDS, env=os.environ.copy())
    except FileNotFoundError as exc:
        raise InstallError(f"未找到宿主命令：{argv[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise InstallError(f"宿主命令超过 {COMMAND_TIMEOUT_SECONDS} 秒未完成：{' '.join(argv)}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or f"exit {exc.returncode}"
        raise InstallError(f"宿主命令失败：{' '.join(argv)}\n{detail}") from exc
    return result.stdout


def run_json_value(argv: tuple[str, ...]) -> Any:
    output = run_command(argv)
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise InstallError(f"宿主命令没有返回预期 JSON：{' '.join(argv)}") from exc


def run_json_command(argv: tuple[str, ...]) -> dict[str, Any]:
    value = run_json_value(argv)
    if not isinstance(value, dict):
        raise InstallError(f"宿主命令返回的 JSON 根不是 object：{' '.join(argv)}")
    return value


def parse_version(host: str, output: str) -> tuple[int, int, int]:
    if host == "codex":
        match = re.fullmatch(r"codex-cli (\d+)\.(\d+)\.(\d+)\s*", output)
    elif host == "claude":
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+) \(Claude Code\)\s*", output)
    else:
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)\s*", output)
    if match is None:
        raise InstallError(f"无法识别 {host} 版本输出：{output.strip()!r}")
    return tuple(int(part) for part in match.groups())


def check_host_versions(hosts: tuple[str, ...]) -> None:
    for host in hosts:
        output = run_command(HOST_VERSION_COMMANDS[host])
        current = parse_version(host, output)
        expected = SUPPORTED_HOST_VERSIONS[host]
        if current != expected:
            current_text = ".".join(str(part) for part in current)
            expected_text = ".".join(str(part) for part in expected)
            raise InstallError(f"尚未验证 {host} {current_text} 的安装输出；当前适配器只支持 {expected_text}")


def user_state_root() -> Path:
    raw = os.environ.get("XDG_STATE_HOME")
    base = Path(raw).expanduser() if raw else Path.home() / ".local" / "state"
    return base / "ruokee-skills"


def user_state_path() -> Path:
    return user_state_root() / "installs.json"


def user_data_root() -> Path:
    raw = os.environ.get("XDG_DATA_HOME")
    base = Path(raw).expanduser() if raw else Path.home() / ".local" / "share"
    return base / "ruokee-skills"


def validate_user_entry(key: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != USER_STATE_FIELDS:
        raise InstallError(f"用户状态条目 {key!r} 字段不完整或包含未知字段")
    host, separator, plugin = key.partition(":")
    if not separator or value.get("host") != host or value.get("plugin") != plugin or host not in HOSTS:
        raise InstallError(f"用户状态条目 {key!r} 的身份字段无效")
    for field in ("variant", "source_commit", "installation_id", "base_version", "updated_at"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise InstallError(f"用户状态条目 {key!r} 的 {field} 无效")
    for field in ("baseline_hash", "managed_hash"):
        if not isinstance(value.get(field), str) or HASH_PATTERN.fullmatch(value[field]) is None:
            raise InstallError(f"用户状态条目 {key!r} 的 {field} 无效")
    return value


def read_user_state() -> dict[str, Any]:
    path = user_state_path()
    if not path.exists():
        return {"schema_version": USER_STATE_SCHEMA, "installs": {}}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"无法读取用户安装状态 {path}：{exc}") from exc
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "installs"}
        or type(document.get("schema_version")) is not int
        or document.get("schema_version") != USER_STATE_SCHEMA
        or not isinstance(document.get("installs"), dict)
    ):
        raise InstallError(f"用户安装状态 schema 无效：{path}")
    for key, value in document["installs"].items():
        validate_user_entry(key, value)
    return document


def write_user_state(document: dict[str, Any]) -> None:
    path = user_state_path()
    installs = document["installs"]
    if not installs:
        if path.exists():
            path.unlink()
            fsync_directory(path.parent)
        return
    write_json_atomic(path, document, mode=0o600)


def state_key(host: str, plugin: str) -> str:
    return f"{host}:{plugin}"


def codex_home() -> Path:
    raw = os.environ.get("CODEX_HOME")
    return (Path(raw).expanduser() if raw else Path.home() / ".codex").resolve()


def claude_home() -> Path:
    raw = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(raw).expanduser() if raw else Path.home() / ".claude").resolve()


def pi_home() -> Path:
    raw = os.environ.get("PI_CODING_AGENT_DIR")
    return (Path(raw).expanduser() if raw else Path.home() / ".pi" / "agent").resolve()


def path_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def validate_package_root(host: str, plugin: Plugin, root: Path, version: str, expected_parent: Path) -> NativeInstall:
    info = root.lstat() if root.exists() or root.is_symlink() else None
    if info is None or not stat.S_ISDIR(info.st_mode):
        raise InstallError(f"{host} 报告的插件目录不存在或不是普通目录：{root}")
    if not path_within(root, expected_parent):
        raise InstallError(f"{host} 插件目录越过已验证 cache/package 根：{root}")
    manifest = read_json_object(root / ".codex-plugin" / "plugin.json", f"{host} 已安装 Codex manifest")
    manifest_version = manifest.get("version")
    version_matches = manifest_version == version if host != "claude" else isinstance(manifest_version, str) and manifest_version.split("+", 1)[0] == version
    if manifest.get("name") != plugin.name or not version_matches:
        raise InstallError(f"{host} 已安装目录的 manifest 身份或版本不匹配：{root}")
    skill_root = root / "skills" / plugin.name
    skill_info = skill_root.lstat() if skill_root.exists() or skill_root.is_symlink() else None
    if skill_info is None or not stat.S_ISDIR(skill_info.st_mode):
        raise InstallError(f"{host} 已安装插件缺少 Skill 目录：{skill_root}")
    return NativeInstall(host, plugin.name, root, skill_root, version)


def validate_catalog_source(plugin: Plugin, entry: dict[str, Any]) -> None:
    source = entry.get("source")
    if not isinstance(source, dict) or source.get("source") != "local":
        raise InstallError(f"Codex catalog 中 {plugin.name} 不是本地 source")
    raw_path = source.get("path")
    if not isinstance(raw_path, str) or Path(raw_path).resolve() != plugin.package_root.resolve():
        raise InstallError(f"Codex catalog 中 {plugin.name} 指向错误 package root：{raw_path!r}")
    marketplace = entry.get("marketplaceSource")
    if not isinstance(marketplace, dict) or marketplace.get("sourceType") != "local" or Path(str(marketplace.get("source"))).resolve() != REPO_ROOT.resolve():
        raise InstallError(f"Codex catalog 中 {plugin.name} 的 marketplace source 不是当前仓库")


def codex_catalog() -> dict[str, Any]:
    return run_json_command(("codex", "plugin", "list", "--available", "--json"))


def codex_marketplace_registered() -> bool:
    document = run_json_command(("codex", "plugin", "marketplace", "list", "--json"))
    entries = document.get("marketplaces")
    if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
        raise InstallError("Codex marketplace list --json 没有返回有效 marketplaces 数组")
    matches = [item for item in entries if item.get("name") == MARKETPLACE_NAME]
    if len(matches) > 1:
        raise InstallError(f"Codex marketplace 名称重复：{MARKETPLACE_NAME}")
    if not matches:
        return False
    entry = matches[0]
    source = entry.get("marketplaceSource")
    raw_root = entry.get("root")
    raw_source = source.get("source") if isinstance(source, dict) else None
    if (
        not isinstance(source, dict)
        or source.get("sourceType") != "local"
        or not isinstance(raw_source, str)
        or Path(raw_source).resolve() != REPO_ROOT.resolve()
        or not isinstance(raw_root, str)
        or Path(raw_root).resolve() != REPO_ROOT.resolve()
    ):
        raise InstallError(f"Codex marketplace {MARKETPLACE_NAME} 没有指向当前仓库")
    return True


def codex_entry(plugin: Plugin, *, installed: bool | None = None) -> dict[str, Any] | None:
    document = codex_catalog()
    entries: list[dict[str, Any]] = []
    if installed is not False:
        entries.extend(item for item in document.get("installed", []) if isinstance(item, dict))
    if installed is not True:
        entries.extend(item for item in document.get("available", []) if isinstance(item, dict))
    matches = [item for item in entries if item.get("pluginId") == f"{plugin.name}@{MARKETPLACE_NAME}"]
    if len(matches) > 1:
        raise InstallError(f"Codex catalog 中 {plugin.name} 身份重复")
    if not matches:
        return None
    validate_catalog_source(plugin, matches[0])
    return matches[0]


def codex_status(plugin: Plugin) -> NativeInstall | None:
    registered = codex_marketplace_registered()
    entry = codex_entry(plugin, installed=True)
    if entry is None:
        if registered and codex_entry(plugin, installed=False) is None:
            raise InstallError(f"Codex marketplace 中找不到插件 {plugin.name}")
        return None
    if not registered:
        raise InstallError(f"Codex 已安装 {plugin.name}，但 {MARKETPLACE_NAME} marketplace 未登记")
    version = entry.get("version")
    if not isinstance(version, str) or not version:
        raise InstallError(f"Codex 没有报告 {plugin.name} 的已安装版本")
    cache_parent = codex_home() / "plugins" / "cache" / MARKETPLACE_NAME / plugin.name
    root = cache_parent / version
    install = validate_package_root("codex", plugin, root, version, cache_parent)
    return NativeInstall(install.host, install.plugin, install.root, install.skill_root, install.version, bool(entry.get("enabled", False)))


def ensure_codex_marketplace(plugin: Plugin) -> None:
    if not codex_marketplace_registered():
        run_json_command(("codex", "plugin", "marketplace", "add", str(REPO_ROOT), "--json"))
    if not codex_marketplace_registered():
        raise InstallError("Codex 注册本地 marketplace 后没有报告当前仓库")
    if codex_entry(plugin, installed=False) is None and codex_entry(plugin, installed=True) is None:
        raise InstallError("Codex 注册本地 marketplace 后仍找不到目标插件")


def codex_reinstall(plugin: Plugin) -> NativeInstall:
    ensure_codex_marketplace(plugin)
    result = run_json_command(("codex", "plugin", "add", f"{plugin.name}@{MARKETPLACE_NAME}", "--json"))
    version = result.get("version")
    raw_root = result.get("installedPath")
    if not isinstance(version, str) or not isinstance(raw_root, str):
        raise InstallError(f"Codex 安装 {plugin.name} 后未返回 version/installedPath")
    cache_parent = codex_home() / "plugins" / "cache" / MARKETPLACE_NAME / plugin.name
    reported = validate_package_root("codex", plugin, Path(raw_root), version, cache_parent)
    installed = codex_status(plugin)
    if installed is None or installed.root.resolve() != reported.root.resolve() or installed.version != reported.version:
        raise InstallError(f"Codex 安装 {plugin.name} 后的 catalog 与返回路径不一致")
    return installed


def claude_catalog() -> dict[str, Any]:
    return run_json_command(("claude", "plugin", "list", "--available", "--json"))


def claude_marketplace_registered() -> bool:
    entries = run_json_value(("claude", "plugin", "marketplace", "list", "--json"))
    if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
        raise InstallError("Claude Code marketplace list --json 没有返回数组")
    matches = [item for item in entries if item.get("name") == MARKETPLACE_NAME]
    if len(matches) > 1:
        raise InstallError(f"Claude Code marketplace 名称重复：{MARKETPLACE_NAME}")
    if not matches:
        return False
    entry = matches[0]
    raw_path = entry.get("path")
    if entry.get("source") != "directory" or not isinstance(raw_path, str) or Path(raw_path).resolve() != REPO_ROOT.resolve():
        raise InstallError(f"Claude Code marketplace {MARKETPLACE_NAME} 没有指向当前仓库")
    return True


def claude_catalog_has(plugin: Plugin) -> bool:
    document = claude_catalog()
    identifier = f"{plugin.name}@{MARKETPLACE_NAME}"
    return any(isinstance(item, dict) and (item.get("pluginId") == identifier or item.get("id") == identifier) for group in ("installed", "available") for item in document.get(group, []))


def ensure_claude_marketplace(plugin: Plugin) -> None:
    registered = claude_marketplace_registered()
    if not registered:
        run_command(("claude", "plugin", "marketplace", "add", str(REPO_ROOT), "--scope", "user"))
    elif not claude_catalog_has(plugin):
        run_command(("claude", "plugin", "marketplace", "update", MARKETPLACE_NAME))
    if not claude_marketplace_registered():
        raise InstallError("Claude Code 注册本地 marketplace 后没有报告当前仓库")
    if not claude_catalog_has(plugin):
        raise InstallError("Claude Code 注册本地 marketplace 后仍找不到目标插件")


def claude_status(plugin: Plugin) -> NativeInstall | None:
    registered = claude_marketplace_registered()
    document = run_json_value(("claude", "plugin", "list", "--json"))
    if not isinstance(document, list):
        raise InstallError("Claude Code plugin list --json 没有返回数组")
    identifier = f"{plugin.name}@{MARKETPLACE_NAME}"
    matches = [item for item in document if isinstance(item, dict) and item.get("id") == identifier and item.get("scope") == "user"]
    if len(matches) > 1:
        raise InstallError(f"Claude Code 用户级安装中 {plugin.name} 身份重复")
    if not matches:
        if registered and not claude_catalog_has(plugin):
            raise InstallError(f"Claude Code marketplace 中找不到插件 {plugin.name}")
        return None
    if not registered:
        raise InstallError(f"Claude Code 已安装 {plugin.name}，但 {MARKETPLACE_NAME} marketplace 未登记")
    entry = matches[0]
    version = entry.get("version")
    raw_root = entry.get("installPath")
    if not isinstance(version, str) or not isinstance(raw_root, str):
        raise InstallError(f"Claude Code 没有报告 {plugin.name} 的 version/installPath")
    cache_parent = claude_home() / "plugins" / "cache" / MARKETPLACE_NAME / plugin.name
    install = validate_package_root("claude", plugin, Path(raw_root), version, cache_parent)
    return NativeInstall(install.host, install.plugin, install.root, install.skill_root, install.version, bool(entry.get("enabled", False)))


def claude_reinstall(plugin: Plugin, current: NativeInstall | None) -> NativeInstall:
    ensure_claude_marketplace(plugin)
    if current is None:
        run_command(("claude", "plugin", "install", f"{plugin.name}@{MARKETPLACE_NAME}", "--scope", "user"))
    else:
        run_command(("claude", "plugin", "marketplace", "update", MARKETPLACE_NAME))
        run_command(("claude", "plugin", "update", f"{plugin.name}@{MARKETPLACE_NAME}", "--scope", "user"))
    installed = claude_status(plugin)
    if installed is None:
        raise InstallError(f"Claude Code 操作成功后仍找不到用户级插件 {plugin.name}")
    return installed


def pi_settings_path() -> Path:
    return pi_home() / "settings.json"


def pi_package_sources() -> list[tuple[str, Path]]:
    run_command(("pi", "list", "--no-approve"))
    path = pi_settings_path()
    if not path.exists():
        return []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"无法读取 Pi settings {path}：{exc}") from exc
    packages = document.get("packages", [])
    if not isinstance(packages, list):
        raise InstallError(f"Pi settings 的 packages 不是数组：{path}")
    result: list[tuple[str, Path]] = []
    for item in packages:
        raw = item if isinstance(item, str) else item.get("source") if isinstance(item, dict) else None
        if not isinstance(raw, str) or raw.startswith(("npm:", "git:", "http://", "https://", "ssh://")):
            continue
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = path.parent / candidate
        result.append((raw, candidate.resolve(strict=False)))
    return result


def managed_pi_package(plugin: Plugin) -> Path:
    return user_data_root() / "packages" / plugin.name


def pi_local_plugin_name(root: Path) -> str | None:
    manifest = root / ".codex-plugin" / "plugin.json"
    info = manifest.lstat() if manifest.exists() or manifest.is_symlink() else None
    if info is None or not stat.S_ISREG(info.st_mode):
        return None
    try:
        value = read_json_object(manifest, "Pi 本地 Package Codex manifest")
    except RepositoryError:
        return None
    name = value.get("name")
    return name if isinstance(name, str) else None


def pi_status(plugin: Plugin) -> NativeInstall | None:
    expected = {
        plugin.package_root.resolve(): "default",
        managed_pi_package(plugin).resolve(): "managed",
    }
    sources = pi_package_sources()
    foreign = [(raw, resolved) for raw, resolved in sources if resolved not in expected and pi_local_plugin_name(resolved) == plugin.name]
    if foreign:
        paths = ", ".join(str(item[1]) for item in foreign)
        raise InstallError(f"Pi 已登记来自其他本地 source 的同名插件 {plugin.name}：{paths}")
    matches = [(raw, resolved, expected[resolved]) for raw, resolved in sources if resolved in expected]
    if len(matches) > 1:
        paths = ", ".join(str(item[1]) for item in matches)
        raise InstallError(f"Pi 同时登记了 {plugin.name} 的多个活动本地 source：{paths}")
    if not matches:
        return None
    raw, root, _ = matches[0]
    if not root.exists():
        raise InstallError(f"Pi 登记的 {plugin.name} 本地 Package 不存在：{root}")
    manifest = read_json_object(root / ".codex-plugin" / "plugin.json", "Pi Package Codex manifest")
    version = manifest.get("version")
    if manifest.get("name") != plugin.name or not isinstance(version, str):
        raise InstallError(f"Pi Package 身份无效：{root}")
    allowed_parent = plugin.workspace if root == plugin.package_root.resolve() else user_data_root() / "packages"
    install = validate_package_root("pi", plugin, root, version, allowed_parent)
    return NativeInstall(install.host, install.plugin, install.root, install.skill_root, install.version, True, raw)


def pi_switch_source(plugin: Plugin, target: Path, current: NativeInstall | None) -> NativeInstall:
    target = target.resolve()
    sources = pi_package_sources()
    target_raw = next((raw for raw, resolved in sources if resolved == target), None)
    if target_raw is None:
        run_command(("pi", "install", str(target), "--no-approve"))
    if current is not None and current.root.resolve() != target and current.source_arg is not None:
        run_command(("pi", "remove", str(current.root.resolve()), "--no-approve"))
    installed = pi_status(plugin)
    if installed is None or installed.root.resolve() != target:
        raise InstallError(f"Pi 切换 {plugin.name} source 后未解析到预期 Package：{target}")
    return installed


def native_status(host: str, plugin: Plugin) -> NativeInstall | None:
    if host == "codex":
        installed = codex_status(plugin)
    elif host == "claude":
        installed = claude_status(plugin)
    else:
        installed = pi_status(plugin)
    if installed is not None and not installed.enabled:
        raise InstallError(f"{host}:{plugin.name} 已安装但未启用")
    return installed


def validate_task_runtime(host: str, plugin: Plugin, installed: NativeInstall | None) -> None:
    if plugin.name != "task":
        return
    if installed is None:
        raise InstallError(f"项目 local Task 需要先安装 {host} 用户级 runtime")
    if not installed.enabled:
        raise InstallError(f"项目 local Task 需要先启用 {host} 用户级 runtime")
    launcher = installed.root / "bin" / "task-core"
    binaries = list(installed.root.glob("runtime/*/task-core.dist/task-core.bin"))
    if not launcher.is_file() or not os.access(launcher, os.X_OK) or len(binaries) != 1 or not binaries[0].is_file() or not os.access(binaries[0], os.X_OK):
        raise InstallError(f"{host} 用户级 Task runtime 不完整：{installed.root}")


def validate_task_source_runtime(plugin: Plugin) -> None:
    if plugin.name != "task":
        return
    launcher = plugin.package_root / "bin" / "task-core"
    binaries = list(plugin.package_root.glob("runtime/*/task-core.dist/task-core.bin"))
    if not launcher.is_file() or not os.access(launcher, os.X_OK) or len(binaries) != 1 or not os.access(binaries[0], os.X_OK):
        raise InstallError(f"Task package runtime 尚未构建：{plugin.package_root}")


def cleanup_staging(destination: Path) -> None:
    parent = destination.parent
    staging = sorted(parent.glob(f".{destination.name}.ruokee-skills-staging-*"))
    backups = sorted(parent.glob(f".{destination.name}.ruokee-skills-backup-*"))
    for child in staging:
        remove_path(child)
    destination_exists = destination.exists() or destination.is_symlink()
    if not destination_exists and len(backups) == 1:
        os.replace(backups[0], destination)
        fsync_directory(parent)
        return
    if not destination_exists and backups:
        raise InstallError(f"发现多个无法判定的中断备份，拒绝清理：{', '.join(str(path) for path in backups)}")
    for child in backups:
        remove_path(child)


def atomic_replace_directory(destination: Path, builder: Callable[[Path], None]) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    cleanup_staging(destination)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.ruokee-skills-staging-", dir=destination.parent))
    backup: Path | None = None
    try:
        builder(stage)
        if destination.exists() or destination.is_symlink():
            backup = Path(tempfile.mkdtemp(prefix=f".{destination.name}.ruokee-skills-backup-", dir=destination.parent))
            backup.rmdir()
            os.replace(destination, backup)
        os.replace(stage, destination)
        fsync_directory(destination.parent)
    except BaseException:
        if stage.exists():
            remove_path(stage)
        if backup is not None and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    if backup is not None and backup.exists():
        remove_path(backup)


def install_skill(destination: Path, plugin: Plugin, variant: str, metadata: dict[str, Any] | None = None) -> None:
    def build(stage: Path) -> None:
        populate_materialized_skill(plugin, variant, stage)
        if metadata is not None:
            target = stage / PROJECT_INSTALL_METADATA
            target.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            target.chmod(0o644)

    atomic_replace_directory(destination, build)


def copy_package(source: Path, destination: Path) -> None:
    entries = scan_tree(source, exclude_install_metadata=False)
    for relative, entry in entries.items():
        target = destination / relative
        if entry.kind == "directory":
            target.mkdir(parents=True, exist_ok=True)
            target.chmod(entry.mode)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(read_regular_file(source / relative))
            target.chmod(entry.mode)


def build_managed_pi_package(plugin: Plugin, variant: str) -> NativeInstall:
    destination = managed_pi_package(plugin)

    def build(stage: Path) -> None:
        copy_package(plugin.package_root, stage)
        skill = stage / "skills" / plugin.name
        remove_path(skill)
        skill.mkdir(parents=True)
        populate_materialized_skill(plugin, variant, skill)

    atomic_replace_directory(destination, build)
    manifest = read_json_object(destination / ".codex-plugin" / "plugin.json", "受管 Pi Package manifest")
    version = manifest.get("version")
    if not isinstance(version, str):
        raise InstallError(f"受管 Pi Package 缺少版本：{destination}")
    return NativeInstall("pi", plugin.name, destination, destination / "skills" / plugin.name, version)


def baseline_hash(plugin: Plugin, host: str) -> str:
    if host == "pi":
        return directory_hash(plugin.package_root, exclude_install_metadata=False)
    return materialized_hash(plugin, plugin.default_variant)


def current_hash(installed: NativeInstall, host: str) -> str:
    target = installed.root if host == "pi" else installed.skill_root
    return directory_hash(target, exclude_install_metadata=False)


def verify_drift(plugin: Plugin, host: str, installed: NativeInstall | None, state: dict[str, Any] | None, baseline: str, force: bool) -> None:
    if installed is None:
        return
    current = current_hash(installed, host)
    if state is not None:
        if current in (state["managed_hash"], baseline):
            return
        if force:
            return
        raise InstallError(f"{host}:{plugin.name} 的已托管内容发生漂移；使用 --force 仅可覆盖该已验证安装")
    if current == baseline:
        return
    if force:
        return
    raise InstallError(f"{host}:{plugin.name} 已安装 Skill/Package 不是当前 default 基线；请检查修改或使用 --force 原生恢复")


def installation_id(host: str, plugin: Plugin) -> str:
    return f"{plugin.name}@{MARKETPLACE_NAME}" if host in ("codex", "claude") else f"{plugin.name}@local"


def user_state_entry(host: str, plugin: Plugin, variant: str, baseline: str, managed: str, commit: str) -> dict[str, Any]:
    return {
        "host": host,
        "plugin": plugin.name,
        "variant": variant,
        "source_commit": commit,
        "installation_id": installation_id(host, plugin),
        "base_version": base_version(plugin),
        "baseline_hash": baseline,
        "managed_hash": managed,
        "updated_at": now_rfc3339(),
    }


def refresh_native(host: str, plugin: Plugin, current: NativeInstall | None) -> NativeInstall:
    validate_task_source_runtime(plugin)
    if host == "codex":
        return codex_reinstall(plugin)
    if host == "claude":
        return claude_reinstall(plugin, current)
    raise AssertionError(host)


def apply_user_variant(host: str, plugin: Plugin, variant: str, current: NativeInstall | None, *, refresh: bool) -> NativeInstall:
    if host in ("codex", "claude"):
        installed = refresh_native(host, plugin, current) if refresh or current is None else current
        if not installed.enabled:
            raise InstallError(f"{host}:{plugin.name} 已安装但未启用")
        install_skill(installed.skill_root, plugin, variant)
        expected = materialized_hash(plugin, variant)
        if directory_hash(installed.skill_root) != expected:
            raise InstallError(f"{host}:{plugin.name} 物化结果校验失败")
        return installed

    validate_task_source_runtime(plugin)
    if variant == plugin.default_variant:
        installed = pi_switch_source(plugin, plugin.package_root, current)
    else:
        managed = build_managed_pi_package(plugin, variant)
        installed = pi_switch_source(plugin, managed.root, current)
    return installed


def normalized_hosts(raw_hosts: tuple[str, ...]) -> tuple[str, ...]:
    selected = set(raw_hosts or HOSTS)
    return tuple(host for host in HOSTS if host in selected)


def require_plugins(names: tuple[str, ...], all_plugins: dict[str, Plugin]) -> list[Plugin]:
    missing = sorted(set(names) - set(all_plugins))
    if missing:
        raise InstallError(f"未知插件：{', '.join(missing)}")
    return [all_plugins[name] for name in names]


def variant_for(plugin: Plugin, requested: str | None) -> str:
    variant = requested or plugin.default_variant
    plugin.source_for_variant(variant)
    return variant


def repository_status() -> str:
    try:
        return subprocess.run(("git", "-C", str(REPO_ROOT), "status", "--porcelain"), check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise InstallError(f"无法读取目标仓库状态：{exc}") from exc


def setup_user(plugins: list[Plugin], hosts: tuple[str, ...], requested_variant: str | None, force: bool) -> None:
    check_host_versions(hosts)
    before_status = repository_status()
    with operation_lock("user"):
        state = read_user_state()
        for plugin in plugins:
            validate_task_source_runtime(plugin)
        preflight: dict[tuple[str, str], tuple[str, str, NativeInstall | None, dict[str, Any] | None]] = {}
        for host in hosts:
            for plugin in plugins:
                variant = variant_for(plugin, requested_variant)
                baseline = baseline_hash(plugin, host)
                installed = native_status(host, plugin)
                entry = state["installs"].get(state_key(host, plugin.name))
                verify_drift(plugin, host, installed, entry, baseline, force)
                preflight[(host, plugin.name)] = (variant, baseline, installed, entry)

        commit, _ = repository_state()
        for host in hosts:
            for plugin in plugins:
                variant, baseline, installed, entry = preflight[(host, plugin.name)]
                needs_refresh = installed is None or installed.version.split("+", 1)[0] != base_version(plugin) or (force and installed is not None and current_hash(installed, host) not in (baseline, entry["managed_hash"] if entry else baseline))
                active = apply_user_variant(host, plugin, variant, installed, refresh=needs_refresh)
                managed = current_hash(active, host)
                state["installs"][state_key(host, plugin.name)] = user_state_entry(host, plugin, variant, baseline, managed, commit)
                write_user_state(state)
                console.print(f"[green]已设置[/green] {host}:{plugin.name} -> {variant}")
    if repository_status() != before_status:
        raise InstallError("安装过程改变了 ruokee-skills 工作树；状态已保留，请先检查差异")


def selected_user_entries(document: dict[str, Any], names: tuple[str, ...], hosts: tuple[str, ...]) -> list[tuple[str, str, dict[str, Any]]]:
    selected_names = set(names)
    result = []
    for key, entry in document["installs"].items():
        if entry["host"] in hosts and (not selected_names or entry["plugin"] in selected_names):
            result.append((entry["host"], entry["plugin"], entry))
    result.sort(key=lambda item: (HOSTS.index(item[0]), item[1]))
    if names:
        missing = sorted(name for name in selected_names if not any(item[1] == name for item in result))
        if missing:
            raise InstallError(f"没有找到所选宿主中的托管用户安装：{', '.join(missing)}")
    if not result:
        raise InstallError("没有可处理的托管用户安装")
    return result


def update_user(names: tuple[str, ...], all_plugins: dict[str, Plugin], hosts: tuple[str, ...], force: bool) -> None:
    check_host_versions(hosts)
    before_status = repository_status()
    with operation_lock("user"):
        state = read_user_state()
        entries = selected_user_entries(state, names, hosts)
        preflight = []
        for host, name, entry in entries:
            plugin = all_plugins.get(name)
            if plugin is None:
                raise InstallError(f"状态中的插件已不在仓库：{name}")
            validate_task_source_runtime(plugin)
            variant = variant_for(plugin, entry["variant"])
            baseline = baseline_hash(plugin, host)
            installed = native_status(host, plugin)
            verify_drift(plugin, host, installed, entry, baseline, force)
            preflight.append((host, plugin, variant, baseline, installed))

        commit, _ = repository_state()
        for host, plugin, variant, baseline, installed in preflight:
            active = apply_user_variant(host, plugin, variant, installed, refresh=host in ("codex", "claude"))
            managed = current_hash(active, host)
            state["installs"][state_key(host, plugin.name)] = user_state_entry(host, plugin, variant, baseline, managed, commit)
            write_user_state(state)
            console.print(f"[green]已更新[/green] {host}:{plugin.name} -> {variant}")
    if repository_status() != before_status:
        raise InstallError("更新过程改变了 ruokee-skills 工作树；状态已保留，请先检查差异")


def remove_managed_pi_package(plugin: Plugin) -> None:
    path = managed_pi_package(plugin)
    if not path.exists():
        return
    parent = user_data_root() / "packages"
    if not path_within(path, parent) or path.is_symlink():
        raise InstallError(f"拒绝删除未验证的 Pi 受管 Package：{path}")
    tombstone = Path(tempfile.mkdtemp(prefix=f".{plugin.name}.ruokee-skills-remove-", dir=parent))
    tombstone.rmdir()
    os.replace(path, tombstone)
    remove_path(tombstone)


def reset_user(names: tuple[str, ...], all_plugins: dict[str, Plugin], hosts: tuple[str, ...], force: bool) -> None:
    check_host_versions(hosts)
    before_status = repository_status()
    with operation_lock("user"):
        state = read_user_state()
        entries = selected_user_entries(state, names, hosts)
        preflight = []
        for host, name, entry in entries:
            plugin = all_plugins.get(name)
            if plugin is None:
                raise InstallError(f"状态中的插件已不在仓库：{name}")
            validate_task_source_runtime(plugin)
            baseline = baseline_hash(plugin, host)
            installed = native_status(host, plugin)
            verify_drift(plugin, host, installed, entry, baseline, force)
            preflight.append((host, plugin, installed))

        for host, plugin, installed in preflight:
            if host in ("codex", "claude"):
                active = apply_user_variant(host, plugin, plugin.default_variant, installed, refresh=True)
                if current_hash(active, host) != baseline_hash(plugin, host):
                    raise InstallError(f"{host}:{plugin.name} reset 后不是当前 default")
            else:
                active = apply_user_variant(host, plugin, plugin.default_variant, installed, refresh=False)
                if current_hash(active, host) != baseline_hash(plugin, host):
                    raise InstallError(f"Pi:{plugin.name} reset 后不是当前 default Package")
                remove_managed_pi_package(plugin)
            del state["installs"][state_key(host, plugin.name)]
            write_user_state(state)
            console.print(f"[green]已重置[/green] {host}:{plugin.name} -> {plugin.default_variant}")
    if repository_status() != before_status:
        raise InstallError("reset 过程改变了 ruokee-skills 工作树；状态已保留，请先检查差异")


def normalize_project(raw: Path | None) -> Path:
    if raw is None:
        raise InstallError("project scope 必须显式提供 --project")
    absolute = raw.expanduser().absolute()
    if absolute == Path("/") or absolute.resolve() == REPO_ROOT.resolve():
        raise InstallError("拒绝把根目录或 ruokee-skills 自身作为消费项目")
    if absolute.resolve() != absolute:
        raise InstallError(f"消费项目路径不能经过符号链接：{absolute}")
    info = absolute.lstat() if absolute.exists() else None
    if info is None or not stat.S_ISDIR(info.st_mode) or not os.access(absolute, os.W_OK | os.X_OK):
        raise InstallError(f"消费项目必须是存在且可写的普通目录：{absolute}")
    return absolute


def ensure_safe_target_parent(project: Path, parent: Path) -> None:
    current = project
    for part in parent.relative_to(project).parts:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        info = current.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise InstallError(f"项目安装父路径不能是符号链接或普通文件：{current}")


def project_targets(project: Path, plugin: Plugin, hosts: tuple[str, ...]) -> list[ProjectTarget]:
    targets = []
    shared = tuple(host for host in ("codex", "pi") if host in hosts)
    if shared:
        targets.append(ProjectTarget(project / ".agents" / "skills" / plugin.name, shared))
    if "claude" in hosts:
        targets.append(ProjectTarget(project / ".claude" / "skills" / plugin.name, ("claude",)))
    return targets


def validate_project_metadata(path: Path, value: Any, plugin: Plugin | None = None) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or set(value) != PROJECT_STATE_FIELDS
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != PROJECT_STATE_SCHEMA
    ):
        raise InstallError(f"项目托管元数据 schema 无效：{path}")
    if value.get("plugin") != path.parent.name:
        raise InstallError(f"项目托管元数据与目标目录名不匹配：{path}")
    if plugin is not None and value.get("plugin") != plugin.name:
        raise InstallError(f"项目托管元数据不属于目标插件：{path}")
    hosts = value.get("hosts")
    if not isinstance(hosts, list) or not hosts or any(host not in HOSTS for host in hosts) or len(hosts) != len(set(hosts)):
        raise InstallError(f"项目托管元数据 hosts 无效：{path}")
    host_root = path.parent.parent.parent.name
    allowed_hosts = {"codex", "pi"} if host_root == ".agents" else {"claude"} if host_root == ".claude" else set()
    if not set(hosts) <= allowed_hosts:
        raise InstallError(f"项目托管元数据 hosts 与目标根不匹配：{path}")
    for field in ("plugin", "variant", "source_commit", "installed_at", "updated_at"):
        if not isinstance(value.get(field), str) or not value[field]:
            raise InstallError(f"项目托管元数据 {field} 无效：{path}")
    for field in ("baseline_hash", "managed_hash"):
        if not isinstance(value.get(field), str) or HASH_PATTERN.fullmatch(value[field]) is None:
            raise InstallError(f"项目托管元数据 {field} 无效：{path}")
    return value


def read_project_metadata(target: Path, plugin: Plugin | None = None) -> dict[str, Any] | None:
    info = target.lstat() if target.exists() or target.is_symlink() else None
    if info is None or not stat.S_ISDIR(info.st_mode):
        return None
    metadata = target / PROJECT_INSTALL_METADATA
    metadata_info = metadata.lstat() if metadata.exists() or metadata.is_symlink() else None
    if metadata_info is None:
        return None
    if not stat.S_ISREG(metadata_info.st_mode):
        raise InstallError(f"项目托管元数据必须是普通文件：{metadata}")
    try:
        value = json.loads(metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"无法读取项目托管元数据 {metadata}：{exc}") from exc
    return validate_project_metadata(metadata, value, plugin)


def verify_project_drift(target: Path, metadata: dict[str, Any], force: bool) -> None:
    current = directory_hash(target)
    if current == metadata["managed_hash"] or force:
        return
    raise InstallError(f"项目 Skill 已发生漂移：{target}；使用 --force 仅可覆盖该有效托管目录")


def project_metadata(plugin: Plugin, variant: str, hosts: tuple[str, ...], commit: str, baseline: str, managed: str, installed_at: str | None = None) -> dict[str, Any]:
    timestamp = now_rfc3339()
    return {
        "schema_version": PROJECT_STATE_SCHEMA,
        "plugin": plugin.name,
        "variant": variant,
        "hosts": [host for host in HOSTS if host in hosts],
        "source_commit": commit,
        "baseline_hash": baseline,
        "managed_hash": managed,
        "installed_at": installed_at or timestamp,
        "updated_at": timestamp,
    }


def preflight_task_runtime(plugin: Plugin, hosts: tuple[str, ...]) -> None:
    if plugin.name != "task":
        return
    for host in hosts:
        validate_task_runtime(host, plugin, native_status(host, plugin))


def setup_project(project: Path, plugins: list[Plugin], hosts: tuple[str, ...], requested_variant: str | None, force: bool) -> None:
    check_host_versions(hosts)
    with operation_lock("project", project):
        preflight = []
        for plugin in plugins:
            variant = variant_for(plugin, requested_variant)
            preflight_task_runtime(plugin, hosts)
            baseline = materialized_hash(plugin, plugin.default_variant)
            managed = materialized_hash(plugin, variant)
            for target in project_targets(project, plugin, hosts):
                ensure_safe_target_parent(project, target.path.parent)
                existing = target.path.exists() or target.path.is_symlink()
                metadata = read_project_metadata(target.path, plugin)
                if existing and metadata is None:
                    if not force:
                        raise InstallError(f"目标已有非托管同名 Skill：{target.path}")
                    console.print(f"[yellow]将替换非托管目标[/yellow] {target.path}")
                if metadata is not None:
                    verify_project_drift(target.path, metadata, force)
                    old_hosts = tuple(metadata["hosts"])
                    if metadata["variant"] != variant and not set(old_hosts) <= set(target.hosts):
                        raise InstallError(f"{target.path} 同时服务未选宿主；切换变体时必须选择现有 hosts：{', '.join(old_hosts)}")
                    combined_hosts = tuple(host for host in HOSTS if host in set(old_hosts) | set(target.hosts))
                else:
                    combined_hosts = target.hosts
                preflight.append((plugin, variant, baseline, managed, target.path, combined_hosts, metadata))

        commit, _ = repository_state()
        for plugin, variant, baseline, managed, target, target_hosts, old_metadata in preflight:
            target.parent.mkdir(parents=True, exist_ok=True)
            metadata = project_metadata(plugin, variant, target_hosts, commit, baseline, managed, old_metadata["installed_at"] if old_metadata else None)
            install_skill(target, plugin, variant, metadata)
            if directory_hash(target) != managed:
                raise InstallError(f"项目 Skill 物化校验失败：{target}")
            console.print(f"[green]已设置项目 Skill[/green] {target} -> {variant} ({', '.join(target_hosts)})")


def discover_project_installs(project: Path, hosts: tuple[str, ...]) -> list[tuple[Path, dict[str, Any]]]:
    roots = []
    if "codex" in hosts or "pi" in hosts:
        roots.append(project / ".agents" / "skills")
    if "claude" in hosts:
        roots.append(project / ".claude" / "skills")
    result = []
    for root in roots:
        if not root.is_dir() or root.is_symlink():
            continue
        for child in sorted(root.iterdir()):
            metadata = read_project_metadata(child)
            if metadata is not None and set(metadata["hosts"]) & set(hosts):
                result.append((child, metadata))
    return result


def selected_project_entries(project: Path, names: tuple[str, ...], hosts: tuple[str, ...]) -> list[tuple[Path, dict[str, Any]]]:
    entries = discover_project_installs(project, hosts)
    if names:
        selected = set(names)
        entries = [item for item in entries if item[1]["plugin"] in selected]
        missing = sorted(name for name in selected if not any(item[1]["plugin"] == name for item in entries))
        if missing:
            raise InstallError(f"项目中没有所选宿主的托管 Skill：{', '.join(missing)}")
    if not entries:
        raise InstallError("项目中没有可处理的托管 Skill")
    return entries


def update_project(project: Path, names: tuple[str, ...], all_plugins: dict[str, Plugin], hosts: tuple[str, ...], force: bool) -> None:
    check_host_versions(hosts)
    with operation_lock("project", project):
        entries = selected_project_entries(project, names, hosts)
        preflight = []
        for target, metadata in entries:
            plugin = all_plugins.get(metadata["plugin"])
            if plugin is None:
                raise InstallError(f"项目状态中的插件已不在仓库：{metadata['plugin']}")
            variant = variant_for(plugin, metadata["variant"])
            verify_project_drift(target, metadata, force)
            preflight_task_runtime(plugin, tuple(metadata["hosts"]))
            preflight.append((target, metadata, plugin, variant, materialized_hash(plugin, plugin.default_variant), materialized_hash(plugin, variant)))

        commit, _ = repository_state()
        for target, old, plugin, variant, baseline, managed in preflight:
            metadata = project_metadata(plugin, variant, tuple(old["hosts"]), commit, baseline, managed, old["installed_at"])
            install_skill(target, plugin, variant, metadata)
            if directory_hash(target) != managed:
                raise InstallError(f"项目 Skill update 物化校验失败：{target}")
            console.print(f"[green]已更新项目 Skill[/green] {target} -> {variant}")


def remove_owned_directory(target: Path) -> None:
    tombstone = Path(tempfile.mkdtemp(prefix=f".{target.name}.ruokee-skills-remove-", dir=target.parent))
    tombstone.rmdir()
    os.replace(target, tombstone)
    remove_path(tombstone)
    fsync_directory(target.parent)


def reset_project(project: Path, names: tuple[str, ...], hosts: tuple[str, ...], force: bool) -> None:
    check_host_versions(hosts)
    with operation_lock("project", project):
        entries = selected_project_entries(project, names, hosts)
        preflight = []
        for target, metadata in entries:
            verify_project_drift(target, metadata, force)
            selected = set(hosts) & set(metadata["hosts"])
            remaining = tuple(host for host in HOSTS if host in set(metadata["hosts"]) - selected)
            preflight.append((target, metadata, remaining))

        for target, metadata, remaining in preflight:
            if remaining:
                updated = {**metadata, "hosts": list(remaining), "updated_at": now_rfc3339()}
                write_json_atomic(target / PROJECT_INSTALL_METADATA, updated, mode=0o644)
                console.print(f"[green]已解除宿主关联[/green] {target}；仍服务 {', '.join(remaining)}")
            else:
                remove_owned_directory(target)
                console.print(f"[green]已删除项目 Skill[/green] {target}")


def validate_scope(scope: str, project: Path | None) -> Path | None:
    if scope == "project":
        return normalize_project(project)
    if project is not None:
        raise InstallError("user scope 不接受 --project")
    return None


def common_options(function: Callable[..., Any]) -> Callable[..., Any]:
    function = click.option("--force", is_flag=True, help="覆盖已验证的漂移，或在 setup 时替换明确的项目同名目标。")(function)
    function = click.option("--host", "hosts", multiple=True, type=click.Choice(HOSTS), help="限定宿主，可重复；默认处理三个宿主。")(function)
    function = click.option("--project", type=click.Path(path_type=Path), help="project scope 的显式消费项目路径。")(function)
    function = click.option("--scope", required=True, type=click.Choice(("user", "project")), help="安装 scope，必须显式指定。")(function)
    return function


@click.group()
def cli() -> None:
    """管理 marketplace/Package 变体与项目 local Skill。"""


@cli.command()
@click.argument("plugins", nargs=-1, required=True)
@click.option("--variant", help="目标变体；省略时使用插件 default。")
@common_options
def setup(plugins: tuple[str, ...], variant: str | None, scope: str, project: Path | None, hosts: tuple[str, ...], force: bool) -> None:
    """安装原生用户入口并应用变体，或物化项目 local Skill。"""
    try:
        all_plugins = discover_plugins()
        selected = require_plugins(plugins, all_plugins)
        selected_hosts = normalized_hosts(hosts)
        normalized_project = validate_scope(scope, project)
        if scope == "user":
            setup_user(selected, selected_hosts, variant, force)
        else:
            assert normalized_project is not None
            setup_project(normalized_project, selected, selected_hosts, variant, force)
    except RepositoryError as exc:
        raise InstallError(str(exc)) from exc


@cli.command()
@click.argument("plugins", nargs=-1)
@common_options
def update(plugins: tuple[str, ...], scope: str, project: Path | None, hosts: tuple[str, ...], force: bool) -> None:
    """从当前 checkout 重建并重放已记录的变体。"""
    try:
        all_plugins = discover_plugins()
        if plugins:
            require_plugins(plugins, all_plugins)
        selected_hosts = normalized_hosts(hosts)
        normalized_project = validate_scope(scope, project)
        if scope == "user":
            update_user(plugins, all_plugins, selected_hosts, force)
        else:
            assert normalized_project is not None
            update_project(normalized_project, plugins, all_plugins, selected_hosts, force)
    except RepositoryError as exc:
        raise InstallError(str(exc)) from exc


@cli.command()
@click.argument("plugins", nargs=-1, required=True)
@common_options
def reset(plugins: tuple[str, ...], scope: str, project: Path | None, hosts: tuple[str, ...], force: bool) -> None:
    """恢复用户 default 或删除已验证的项目 local Skill。"""
    try:
        all_plugins = discover_plugins()
        require_plugins(plugins, all_plugins)
        selected_hosts = normalized_hosts(hosts)
        normalized_project = validate_scope(scope, project)
        if scope == "user":
            reset_user(plugins, all_plugins, selected_hosts, force)
        else:
            assert normalized_project is not None
            reset_project(normalized_project, plugins, selected_hosts, force)
    except RepositoryError as exc:
        raise InstallError(str(exc)) from exc


if __name__ == "__main__":
    cli()
