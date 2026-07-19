import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-skill-updates.py"
SPEC = importlib.util.spec_from_file_location("check_skill_updates", SCRIPT)
assert SPEC and SPEC.loader
updates = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updates)


class UpstreamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="skill-update-test-")
        self.root = Path(self.temporary_directory.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def skill(self, commit: str, local: str, mode: str = "merge") -> updates.Skill:
        local_root = self.workspace / "demo"
        local_root.mkdir(exist_ok=True)
        (local_root / "SKILL.md").write_text(local, encoding="utf-8")
        metadata = self.workspace / "upstream.toml"
        metadata.write_text(
            f'''schema_version = 1

[upstream]
repository = "https://github.com/example/demo"
path = "skills/demo"
ref = "main"
commit = "{commit}"
imported_at = "2026-01-01"
updated_at = "2026-01-01"

[update]
mode = "{mode}"
local_root = "demo"
managed_paths = ["SKILL.md"]
''',
            encoding="utf-8",
        )
        return updates.Skill(
            name="demo",
            workspace=self.workspace,
            metadata=metadata,
            repository="https://github.com/example/demo",
            upstream_path="skills/demo",
            ref="main",
            commit=commit,
            imported_at="2026-01-01",
            updated_at="2026-01-01",
            mode=mode,
            local_root="demo",
            managed_paths=("SKILL.md",),
        )

    @staticmethod
    def snapshot(base: bytes, latest: bytes):
        class Snapshot:
            def __init__(self, skill: updates.Skill, latest_commit: str):
                self.skill = skill
                self.latest_commit = latest_commit

            def __enter__(self):
                return self

            def __exit__(self, *_: object) -> None:
                pass

            def blob(self, revision: str, path: str) -> bytes:
                return base if revision == self.skill.commit else latest

            def diff(self, stat: bool = False) -> str:
                return "" if base == latest else "changed"

        return Snapshot

    def test_check_ignores_unmanaged_changes(self) -> None:
        base = "title\nbody\n"
        old = "a" * 40
        latest = "b" * 40
        skill = self.skill(old, base)

        with (
            mock.patch.object(updates, "resolve_ref", return_value=latest),
            mock.patch.object(updates, "UpstreamSnapshot", self.snapshot(base.encode(), base.encode())),
        ):
            status = updates.check_skills({"demo": skill})[0]

        self.assertEqual(status.state, "ref_advanced")

    def test_merge_update_preserves_local_change(self) -> None:
        base = "title\nupstream: old\ncontext 1\ncontext 2\ncontext 3\nlocal: base\n"
        remote = "title\nupstream: new\ncontext 1\ncontext 2\ncontext 3\nlocal: base\n"
        old = "a" * 40
        new = "b" * 40
        skill = self.skill(
            old,
            "title\nupstream: old\ncontext 1\ncontext 2\ncontext 3\nlocal: custom\n",
        )

        with (
            mock.patch.object(updates, "resolve_ref", return_value=new),
            mock.patch.object(updates, "UpstreamSnapshot", self.snapshot(base.encode(), remote.encode())),
        ):
            result = updates.command_update([skill])

        self.assertEqual(result, 0)
        self.assertEqual(
            (self.workspace / "demo" / "SKILL.md").read_text(encoding="utf-8"),
            "title\nupstream: new\ncontext 1\ncontext 2\ncontext 3\nlocal: custom\n",
        )
        self.assertIn(f'commit = "{new}"', skill.metadata.read_text(encoding="utf-8"))

    def test_conflict_leaves_workspace_unchanged(self) -> None:
        old = "a" * 40
        new = "b" * 40
        local = "value: local\n"
        skill = self.skill(old, local)
        metadata_before = skill.metadata.read_bytes()

        with (
            mock.patch.object(updates, "resolve_ref", return_value=new),
            mock.patch.object(
                updates,
                "UpstreamSnapshot",
                self.snapshot(b"value: base\n", b"value: upstream\n"),
            ),
            self.assertRaisesRegex(updates.UpstreamError, "三方合并冲突"),
        ):
            updates.command_update([skill])

        self.assertEqual((self.workspace / "demo" / "SKILL.md").read_text(), local)
        self.assertEqual(skill.metadata.read_bytes(), metadata_before)


if __name__ == "__main__":
    unittest.main()
