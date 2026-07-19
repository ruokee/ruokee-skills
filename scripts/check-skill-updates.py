#!/usr/bin/env python3
"""检查并选择性更新仓库内由上游引入的 Skills。"""

import argparse
import datetime as dt
import difflib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_DOMAINS = ("third-party", "fork")
GIT_TIMEOUT_SECONDS = 30
HTTP_TIMEOUT_SECONDS = 20


class UpstreamError(RuntimeError):
    pass


@dataclass(frozen=True)
class Skill:
    name: str
    workspace: Path
    metadata: Path
    repository: str
    upstream_path: str
    ref: str
    commit: str
    imported_at: str
    updated_at: str
    mode: str
    local_root: str
    managed_paths: tuple[str, ...]


@dataclass(frozen=True)
class Status:
    name: str
    state: str
    current_commit: str
    latest_commit: str | None
    repository: str
    ref: str
    error: str | None = None


def run_git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["GIT_TERMINAL_PROMPT"] = "0"
    try:
        return subprocess.run(
            ("git", *args),
            cwd=cwd,
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env=environment,
        )
    except FileNotFoundError as exc:
        raise UpstreamError("未找到 git 命令") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or f"exit {exc.returncode}"
        raise UpstreamError(f"git {' '.join(args)} 失败：{detail}") from exc
    except subprocess.TimeoutExpired as exc:
        raise UpstreamError(
            f"git {' '.join(args)} 超过 {GIT_TIMEOUT_SECONDS} 秒未完成"
        ) from exc


def normalized_relative_path(value: str, field: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) in ("", "."):
        raise UpstreamError(f"{field} 必须是非空的安全相对路径：{value!r}")
    return path.as_posix().strip("/")


def load_skill(metadata: Path) -> Skill:
    try:
        data = tomllib.loads(metadata.read_text(encoding="utf-8"))
        upstream = data["upstream"]
        update = data["update"]
    except (OSError, tomllib.TOMLDecodeError, KeyError) as exc:
        raise UpstreamError(f"无法读取 {metadata.relative_to(REPO_ROOT)}：{exc}") from exc

    if data.get("schema_version") != 1:
        raise UpstreamError(f"{metadata.relative_to(REPO_ROOT)}: 仅支持 schema_version = 1")

    required_upstream = {"repository", "path", "ref", "commit", "imported_at", "updated_at"}
    required_update = {"mode", "local_root", "managed_paths"}
    missing = sorted(required_upstream - upstream.keys())
    missing.extend(f"update.{key}" for key in sorted(required_update - update.keys()))
    if missing:
        raise UpstreamError(
            f"{metadata.relative_to(REPO_ROOT)}: 缺少字段 {', '.join(missing)}"
        )

    mode = update.get("mode")
    if mode not in ("replace", "merge"):
        raise UpstreamError(f"{metadata.relative_to(REPO_ROOT)}: update.mode 必须是 replace 或 merge")

    raw_managed_paths = update["managed_paths"]
    if not isinstance(raw_managed_paths, list):
        raise UpstreamError(
            f"{metadata.relative_to(REPO_ROOT)}: update.managed_paths 必须是数组"
        )
    managed_paths = tuple(
        normalized_relative_path(str(value), "update.managed_paths")
        for value in raw_managed_paths
    )
    if not managed_paths or len(managed_paths) != len(set(managed_paths)):
        raise UpstreamError(
            f"{metadata.relative_to(REPO_ROOT)}: update.managed_paths 必须非空且不能重复"
        )

    commit = str(upstream.get("commit", ""))
    if not re.fullmatch(r"[0-9a-fA-F]{40}", commit):
        raise UpstreamError(f"{metadata.relative_to(REPO_ROOT)}: upstream.commit 必须是完整 commit SHA")

    repository = str(upstream["repository"]).rstrip("/")
    github_repository_path(repository)
    ref = str(upstream["ref"])
    if not ref:
        raise UpstreamError(f"{metadata.relative_to(REPO_ROOT)}: upstream.ref 不能为空")

    return Skill(
        name=metadata.parent.name,
        workspace=metadata.parent,
        metadata=metadata,
        repository=repository,
        upstream_path=normalized_relative_path(str(upstream["path"]), "upstream.path"),
        ref=ref,
        commit=commit.lower(),
        imported_at=str(upstream["imported_at"]),
        updated_at=str(upstream["updated_at"]),
        mode=mode,
        local_root=normalized_relative_path(str(update["local_root"]), "update.local_root"),
        managed_paths=managed_paths,
    )


def discover_skills() -> dict[str, Skill]:
    skills: dict[str, Skill] = {}
    for domain in UPSTREAM_DOMAINS:
        for metadata in sorted((REPO_ROOT / domain).glob("*/upstream.toml")):
            skill = load_skill(metadata)
            if skill.name in skills:
                raise UpstreamError(f"Skill 名称重复：{skill.name}")
            skills[skill.name] = skill
    return skills


def resolve_ref(skill: Skill) -> str:
    candidates = (
        skill.ref,
        f"refs/heads/{skill.ref}",
        f"refs/tags/{skill.ref}",
        f"refs/tags/{skill.ref}^{{}}",
    )
    result = run_git("ls-remote", skill.repository, *candidates)
    refs: dict[str, str] = {}
    for line in result.stdout.splitlines():
        commit, ref = line.split(maxsplit=1)
        refs[ref] = commit.lower()

    preferred_refs = (
        f"refs/tags/{skill.ref}^{{}}",
        f"refs/heads/{skill.ref}",
        f"refs/tags/{skill.ref}",
        skill.ref,
    )
    for ref in preferred_refs:
        if ref in refs:
            return refs[ref]
    raise UpstreamError(f"上游不存在 ref {skill.ref!r}")


def check_skills(skills: dict[str, Skill]) -> list[Status]:
    statuses: list[Status] = []
    for skill in skills.values():
        try:
            latest = resolve_ref(skill)
            if latest == skill.commit:
                state = "current"
            else:
                with UpstreamSnapshot(skill, latest) as snapshot:
                    has_managed_changes = bool(snapshot.diff().strip())
                state = "update_available" if has_managed_changes else "ref_advanced"
            statuses.append(
                Status(skill.name, state, skill.commit, latest, skill.repository, skill.ref)
            )
        except UpstreamError as exc:
            statuses.append(
                Status(skill.name, "error", skill.commit, None, skill.repository, skill.ref, str(exc))
            )
    return statuses


class UpstreamSnapshot:
    def __init__(self, skill: Skill, latest: str):
        self.skill = skill
        self.latest = latest
        self._cache: dict[tuple[str, str], bytes | None] = {}
        self.repository_path = github_repository_path(skill.repository)

    def __enter__(self) -> UpstreamSnapshot:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def blob(self, revision: str, managed_path: str) -> bytes | None:
        key = (revision, managed_path)
        if key in self._cache:
            return self._cache[key]

        remote_path = f"{self.skill.upstream_path}/{managed_path}"
        encoded_path = "/".join(quote(part, safe="") for part in remote_path.split("/"))
        url = f"https://raw.githubusercontent.com/{self.repository_path}/{revision}/{encoded_path}"
        headers = {"User-Agent": "ruokee-skills-update-checker"}
        if token := os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
                content = response.read()
        except HTTPError as exc:
            if exc.code == 404:
                content = None
            else:
                raise UpstreamError(f"读取 {remote_path} 失败：GitHub HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise UpstreamError(f"读取 {remote_path} 失败：{exc}") from exc
        self._cache[key] = content
        return content

    def diff(self, stat: bool = False) -> str:
        output: list[str] = []
        for path in self.skill.managed_paths:
            current = self.blob(self.skill.commit, path)
            latest = self.blob(self.latest, path)
            if current == latest:
                continue
            current_text = decode_upstream_text(current, path)
            latest_text = decode_upstream_text(latest, path)
            lines = list(
                difflib.unified_diff(
                    current_text.splitlines(keepends=True),
                    latest_text.splitlines(keepends=True),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                )
            )
            if stat:
                additions = sum(line.startswith("+") and not line.startswith("+++") for line in lines)
                deletions = sum(line.startswith("-") and not line.startswith("---") for line in lines)
                output.append(f"{path} | +{additions} -{deletions}\n")
            else:
                output.extend(lines)
        return "".join(output)


def decode_upstream_text(content: bytes | None, path: str) -> str:
    if content is None:
        return ""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise UpstreamError(f"托管文件必须是 UTF-8 文本：{path}") from exc


def github_repository_path(repository: str) -> str:
    parsed = urlparse(repository)
    repository_path = parsed.path.removesuffix(".git").strip("/")
    if parsed.scheme != "https" or parsed.netloc not in ("github.com", "www.github.com"):
        raise UpstreamError(f"仅支持 HTTPS GitHub 上游仓库：{repository}")
    if len(repository_path.split("/")) != 2:
        raise UpstreamError(f"GitHub 仓库地址格式无效：{repository}")
    return repository_path


def select_skills(all_skills: dict[str, Skill], names: list[str]) -> list[Skill]:
    missing = sorted(set(names) - all_skills.keys())
    if missing:
        raise UpstreamError(f"未知 Skill：{', '.join(missing)}")
    return [all_skills[name] for name in names]


def command_check(skills: dict[str, Skill], as_json: bool) -> int:
    statuses = check_skills(skills)
    if as_json:
        print(json.dumps([asdict(status) for status in statuses], ensure_ascii=False, indent=2))
    else:
        for status in statuses:
            if status.state == "current":
                print(f"[最新] {status.name}: {status.current_commit[:12]} ({status.ref})")
            elif status.state == "update_available":
                print(
                    f"[可更新] {status.name}: {status.current_commit[:12]} -> "
                    f"{status.latest_commit[:12]} ({status.ref})"
                )
            elif status.state == "ref_advanced":
                print(
                    f"[无内容更新] {status.name}: 上游已推进至 "
                    f"{status.latest_commit[:12]}，托管文件未变化 ({status.ref})"
                )
            else:
                print(f"[错误] {status.name}: {status.error}", file=sys.stderr)

        updates = [status.name for status in statuses if status.state == "update_available"]
        if updates:
            print("\n查看变更：")
            for name in updates:
                print(f"  {Path(sys.argv[0]).as_posix()} diff {name}")

    return 2 if any(status.state == "error" for status in statuses) else 0


def command_diff(skills: list[Skill], stat: bool) -> int:
    for index, skill in enumerate(skills):
        latest = resolve_ref(skill)
        if index:
            print()
        print(f"# {skill.name}: {skill.commit} -> {latest}")
        if latest == skill.commit:
            print("已是最新版本。")
            continue
        with UpstreamSnapshot(skill, latest) as snapshot:
            output = snapshot.diff(stat=stat)
        print(output.rstrip() or "托管文件没有变化。")
    return 0


def merge_file(local: bytes, base: bytes, remote: bytes, path: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="skill-merge-") as temporary_directory:
        root = Path(temporary_directory)
        files = (root / "local", root / "base", root / "remote")
        for file, content in zip(files, (local, base, remote), strict=True):
            file.write_bytes(content)
        result = subprocess.run(
            (
                "git",
                "merge-file",
                "-p",
                "-L",
                f"local/{path}",
                "-L",
                "upstream-base",
                "-L",
                "upstream-latest",
                *(str(file) for file in files),
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode == 0:
            return result.stdout
        if result.returncode == 1:
            raise UpstreamError(f"{path} 存在三方合并冲突；未更新任何文件")
        detail = result.stderr.decode(errors="replace").strip()
        raise UpstreamError(f"合并 {path} 失败：{detail}")


def update_metadata(skill: Skill, latest: str) -> None:
    text = skill.metadata.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(?m)^commit\s*=\s*"[0-9a-fA-F]{40}"\s*$',
        f'commit = "{latest}"',
        text,
        count=1,
    )
    updated, date_count = re.subn(
        r'(?m)^updated_at\s*=\s*"[^"]+"\s*$',
        f'updated_at = "{dt.date.today().isoformat()}"',
        updated,
        count=1,
    )
    if count != 1 or date_count != 1:
        raise UpstreamError(f"无法安全更新 {skill.metadata.relative_to(REPO_ROOT)}")
    temporary = skill.metadata.with_suffix(".toml.tmp")
    temporary.write_text(updated, encoding="utf-8")
    os.replace(temporary, skill.metadata)


def command_update(skills: list[Skill]) -> int:
    for skill in skills:
        latest = resolve_ref(skill)
        if latest == skill.commit:
            print(f"[跳过] {skill.name} 已是最新版本")
            continue

        pending: dict[Path, bytes | None] = {}
        with UpstreamSnapshot(skill, latest) as snapshot:
            for path in skill.managed_paths:
                base = snapshot.blob(skill.commit, path)
                remote = snapshot.blob(latest, path)
                local_path = skill.workspace / skill.local_root / Path(path)
                local = local_path.read_bytes() if local_path.is_file() else None

                if skill.mode == "replace" or local == base:
                    result = remote
                elif remote == base or local == remote:
                    result = local
                elif base is None or remote is None or local is None:
                    raise UpstreamError(
                        f"{skill.name}/{path} 的增删与本地修改冲突；未更新任何文件"
                    )
                else:
                    result = merge_file(local, base, remote, path)
                pending[local_path] = result

        for path, content in pending.items():
            if content is None:
                if path.exists():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name(f".{path.name}.upstream.tmp")
                temporary.write_bytes(content)
                os.replace(temporary, path)
        update_metadata(skill, latest)
        print(f"[已更新] {skill.name}: {skill.commit[:12]} -> {latest[:12]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser("check", help="检查所有上游 Skill（默认动作）")
    check.add_argument("--json", action="store_true", help="输出供 agent 读取的 JSON")

    diff = subparsers.add_parser("diff", help="查看指定 Skill 的上游变更")
    diff.add_argument("skills", nargs="+", help="Skill 名称")
    diff.add_argument("--stat", action="store_true", help="只输出变更统计")

    update = subparsers.add_parser("update", help="更新明确选中的 Skill")
    update.add_argument("skills", nargs="+", help="Skill 名称")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        skills = discover_skills()
        if not skills:
            raise UpstreamError("没有找到 upstream.toml")
        if args.command in (None, "check"):
            return command_check(skills, getattr(args, "json", False))
        selected = select_skills(skills, args.skills)
        if args.command == "diff":
            return command_diff(selected, args.stat)
        if args.command == "update":
            return command_update(selected)
        parser.error(f"未知命令：{args.command}")
    except UpstreamError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
