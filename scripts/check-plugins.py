#!/usr/bin/env python3
"""确定性校验 ruokee-skills 的 plugin workspace、manifest 与 marketplace。"""

import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any

from repository import (
    PROJECT_INSTALL_METADATA,
    REPO_ROOT,
    RepositoryError,
    base_version,
    claude_manifest,
    codex_manifest,
    discover_plugins,
    frontmatter_name,
    materialized_hash,
    read_json_object,
)


EXPECTED_PLUGIN_COUNT = 11
SEMVER_PATTERN = re.compile(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?")
PLACEHOLDER_PATTERN = re.compile(r"\[TODO:|placeholder|your[-_ ](?:name|plugin)", re.IGNORECASE)
REQUIRED_CODEX_INTERFACE = frozenset(("displayName", "shortDescription", "longDescription", "developerName", "category", "capabilities", "defaultPrompt"))
OLD_ROOTS = ("public", "experimential", "fork", "third-party", "tests")


class CheckError(RuntimeError):
    """结构校验失败。"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckError(message)


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_codex_manifest(plugin: Any, manifest: dict[str, Any]) -> None:
    path = plugin.package_root / ".codex-plugin" / "plugin.json"
    require(manifest.get("name") == plugin.name, f"{path} 的 name 必须是 {plugin.name!r}")
    version = manifest.get("version")
    require(isinstance(version, str) and SEMVER_PATTERN.fullmatch(version) is not None, f"{path} 的 version 不是 strict semver")
    require(nonempty_string(manifest.get("description")), f"{path} 缺少真实 description")
    author = manifest.get("author")
    require(isinstance(author, dict) and nonempty_string(author.get("name")), f"{path} 缺少 author.name")
    require(manifest.get("skills") == "./skills/", f"{path} 的 skills 必须是 ./skills/")
    require((plugin.package_root / "skills").is_dir(), f"{path} 声明的 skills 目录不存在")
    for field in ("mcpServers", "apps"):
        value = manifest.get(field)
        if isinstance(value, str):
            require(value.startswith("./"), f"{path} 的 {field} 必须是 ./ 相对路径")
            require((plugin.package_root / value[2:]).is_file(), f"{path} 的 {field} 指向不存在的文件")
    interface = manifest.get("interface")
    require(isinstance(interface, dict), f"{path} 缺少 interface")
    require(REQUIRED_CODEX_INTERFACE <= set(interface), f"{path} 的 interface 缺少 {sorted(REQUIRED_CODEX_INTERFACE - set(interface or {}))}")
    require(all(nonempty_string(interface.get(field)) for field in ("displayName", "shortDescription", "longDescription", "developerName", "category")), f"{path} 的 interface 文本字段不能为空")
    capabilities = interface.get("capabilities")
    require(isinstance(capabilities, list) and capabilities and all(nonempty_string(item) for item in capabilities), f"{path} 的 interface.capabilities 无效")
    prompts = interface.get("defaultPrompt")
    require(isinstance(prompts, list) and 1 <= len(prompts) <= 3, f"{path} 的 interface.defaultPrompt 必须有 1 到 3 条")
    require(all(nonempty_string(item) and len(item) <= 128 for item in prompts), f"{path} 的 interface.defaultPrompt 单条必须非空且不超过 128 字符")
    require(PLACEHOLDER_PATTERN.search(json.dumps(manifest, ensure_ascii=False)) is None, f"{path} 含有脚手架占位内容")


def validate_claude_manifest(plugin: Any, manifest: dict[str, Any]) -> None:
    path = plugin.package_root / ".claude-plugin" / "plugin.json"
    require(manifest.get("name") == plugin.name, f"{path} 的 name 必须是 {plugin.name!r}")
    version = manifest.get("version")
    require(isinstance(version, str) and SEMVER_PATTERN.fullmatch(version) is not None and "+" not in version, f"{path} 的 version 必须是不带 build metadata 的 strict semver")
    require(nonempty_string(manifest.get("description")), f"{path} 缺少真实 description")
    author = manifest.get("author")
    require(isinstance(author, dict) and nonempty_string(author.get("name")), f"{path} 缺少 author.name")
    require(nonempty_string(manifest.get("repository")), f"{path} 缺少 repository")
    require(PLACEHOLDER_PATTERN.search(json.dumps(manifest, ensure_ascii=False)) is None, f"{path} 含有脚手架占位内容")


def validate_task_package(plugin: Any, version: str) -> None:
    if plugin.name != "task":
        return
    package = read_json_object(plugin.package_root / "package.json", "Task package.json")
    require(package.get("version") == version, "Task package.json 版本与宿主 manifest 不一致")
    pi = package.get("pi")
    require(isinstance(pi, dict) and pi.get("skills") == ["./skills"] and pi.get("extensions") == ["./adapters/pi/task-tools.ts"], "Task package.json 的 Pi 资源声明无效")
    peer = package.get("peerDependencies")
    require(peer == {"@earendil-works/pi-coding-agent": "*", "typebox": "*"}, "Task 的 Pi core peerDependencies 必须使用 *")
    dependencies = package.get("dependencies", {})
    require(not isinstance(dependencies, dict) or "typebox" not in dependencies, "Task 不得把 typebox 放在 dependencies")


def expected_source(plugin: Any) -> str:
    return "./" + plugin.package_root.relative_to(REPO_ROOT).as_posix()


def marketplace_entries(document: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    require(document.get("name") == "ruokee-skills", f"{path} 的 marketplace name 必须是 ruokee-skills")
    entries = document.get("plugins")
    require(isinstance(entries, list), f"{path} 的 plugins 必须是数组")
    require(all(isinstance(item, dict) for item in entries), f"{path} 的 plugins 条目必须是 object")
    names = [item.get("name") for item in entries]
    require(all(nonempty_string(item) for item in names), f"{path} 的插件名无效")
    require(len(names) == len(set(names)), f"{path} 的插件名重复")
    return entries


def validate_marketplaces(plugins: dict[str, Any]) -> list[str]:
    codex_path = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
    claude_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
    codex_entries = marketplace_entries(read_json_object(codex_path, "Codex marketplace"), codex_path)
    claude_entries = marketplace_entries(read_json_object(claude_path, "Claude marketplace"), claude_path)
    codex_names = [item["name"] for item in codex_entries]
    claude_names = [item["name"] for item in claude_entries]
    require(codex_names == claude_names, "Codex 与 Claude marketplace 的插件集合或顺序不一致")
    require(set(codex_names) == set(plugins), "marketplace 集合与 plugins/* 发现集合不一致")
    for entry in codex_entries:
        plugin = plugins[entry["name"]]
        require(entry.get("source") == {"source": "local", "path": expected_source(plugin)}, f"Codex marketplace 的 {plugin.name} source 无效")
        policy = entry.get("policy")
        require(policy == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}, f"Codex marketplace 的 {plugin.name} policy 不完整或含额外字段")
        require(nonempty_string(entry.get("category")), f"Codex marketplace 的 {plugin.name} 缺少 category")
    for entry in claude_entries:
        plugin = plugins[entry["name"]]
        require(entry.get("source") == expected_source(plugin), f"Claude marketplace 的 {plugin.name} source 无效")
    return codex_names


def validate_bootstrap_links(plugins: dict[str, Any]) -> None:
    for host_root in (REPO_ROOT / ".agents" / "skills", REPO_ROOT / ".claude" / "skills"):
        require(host_root.is_dir() and not host_root.is_symlink(), f"自举目录不存在或不是普通目录：{host_root}")
        children = sorted(host_root.iterdir())
        require({child.name for child in children} == set(plugins), f"{host_root} 的自举链接集合不完整")
        for child in children:
            info = child.lstat()
            require(stat.S_ISLNK(info.st_mode), f"自举入口必须是符号链接：{child}")
            raw_target = os.readlink(child)
            require(not os.path.isabs(raw_target), f"自举链接必须使用相对目标：{child}")
            expected = plugins[child.name].base.resolve()
            require(child.resolve(strict=True) == expected, f"自举链接没有指向 default base：{child} -> {raw_target}")
            require(child.is_dir(), f"自举链接必须解析为目录：{child}")


def validate_cleanup() -> None:
    for name in OLD_ROOTS:
        path = REPO_ROOT / name
        require(not path.exists() and not path.is_symlink(), f"旧根目录仍然存在：{name}/")
    require(not any(REPO_ROOT.rglob("upstream.toml")), "独立 upstream.toml 仍然存在")
    require(not any(REPO_ROOT.rglob("meta.json")), "旧 meta.json 仍然存在")
    require((REPO_ROOT / "CLAUDE.md").is_symlink() and os.readlink(REPO_ROOT / "CLAUDE.md") == "AGENTS.md", "CLAUDE.md 必须保持指向 AGENTS.md 的相对软链接")
    installer = (REPO_ROOT / "scripts" / "install.py").read_text()
    for old_token in ("RESOURCE_DOMAINS", "layout_version", "meta.json", "--global", "--target"):
        require(old_token not in installer, f"安装器仍包含旧布局或命令 token：{old_token}")
    require("PROJECT_INSTALL_METADATA" in installer, f"安装器没有使用新的项目托管元数据 {PROJECT_INSTALL_METADATA}")


def validate_plugins() -> dict[str, Any]:
    plugins = discover_plugins()
    require(len(plugins) == EXPECTED_PLUGIN_COUNT, f"当前应发现 {EXPECTED_PLUGIN_COUNT} 个插件，实际为 {len(plugins)}")
    hashes: dict[str, dict[str, str]] = {}
    for name, plugin in plugins.items():
        require(plugin.workspace.name == name, f"插件目录名与发现名不一致：{plugin.workspace}")
        require(frontmatter_name(plugin.base / "SKILL.md") == name, f"default Skill frontmatter name 与插件名不一致：{name}")
        codex = codex_manifest(plugin)
        claude = claude_manifest(plugin)
        validate_codex_manifest(plugin, codex)
        validate_claude_manifest(plugin, claude)
        version = base_version(plugin)
        validate_task_package(plugin, version)
        hashes[name] = {variant: materialized_hash(plugin, variant) for variant in plugin.variants}
    order = validate_marketplaces(plugins)
    validate_bootstrap_links(plugins)
    validate_cleanup()
    return {"plugins": order, "variants": hashes}


def main() -> int:
    try:
        result = validate_plugins()
    except (CheckError, RepositoryError, OSError) as exc:
        print(f"结构校验失败：{exc}", file=sys.stderr)
        return 1
    variants = sum(len(item) for item in result["variants"].values())
    print(f"结构校验通过：{len(result['plugins'])} 个插件，{variants} 个可物化变体，两个 marketplace 与 22 个自举链接一致。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
