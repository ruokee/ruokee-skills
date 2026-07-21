import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from click.testing import CliRunner


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install.py"
SPEC = importlib.util.spec_from_file_location("resource_installer", SCRIPT)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


class InstallerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="resource-install-test-")
        self.root = Path(self.temporary_directory.name)
        self.repo = self.root / "repo"
        self.target = self.root / "target"
        self.repo.mkdir()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def make_skill(self, name: str = "demo", variants: tuple[str, ...] = ("zh", "en")):
        workspace = self.repo / "public" / name
        sources = {}
        for variant in variants:
            source = workspace / variant / name
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text(f"# {name}\n\n{variant}\n", encoding="utf-8")
            sources[variant] = installer.Variant(variant, source)
        return installer.Resource(name, "skill", "public", workspace, sources)

    def install(self, resource, variant: str = "zh") -> None:
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(installer, "repository_state", return_value=("a" * 40, False)),
        ):
            installer.install_resource(resource, resource.variants[variant], "codex", self.target)

    def test_discovers_direct_and_language_variant_skills(self) -> None:
        direct = self.repo / "fork" / "plain" / "plain"
        direct.mkdir(parents=True)
        (direct / "SKILL.md").write_text("plain", encoding="utf-8")
        self.make_skill()

        resources = installer.discover_resources(self.repo)

        self.assertEqual(set(resources), {"demo", "plain"})
        self.assertEqual(set(resources["demo"].variants), {"en", "zh"})
        self.assertEqual(set(resources["plain"].variants), {"default"})

    def test_choose_variant_ignores_locale_and_uses_deterministic_priority(self) -> None:
        language_variants = self.make_skill()
        with mock.patch.dict(installer.os.environ, {"LANG": "zh_CN.UTF-8"}):
            self.assertEqual(installer.choose_variant(language_variants, None).name, "en")
        self.assertEqual(installer.choose_variant(language_variants, None, "zh").name, "zh")
        self.assertEqual(installer.choose_variant(language_variants, "zh").name, "zh")

        direct = self.make_skill("direct", variants=("en", "default"))
        self.assertEqual(installer.choose_variant(direct, None).name, "default")

        custom = self.make_skill("custom", variants=("compact", "full"))
        self.assertEqual(installer.choose_variant(custom, None).name, "compact")

    def test_hash_ignores_manager_metadata(self) -> None:
        directory = self.root / "content"
        directory.mkdir()
        (directory / "SKILL.md").write_text("body", encoding="utf-8")
        before = installer.hash_directory(directory)
        (directory / installer.METADATA_NAME).write_text('{"anything": true}', encoding="utf-8")
        self.assertEqual(installer.hash_directory(directory), before)

    def test_destination_root_discovers_project_agents_directory(self) -> None:
        project = self.root / "project"
        expected = project / ".agents" / "skills"
        expected.mkdir(parents=True)

        self.assertEqual(installer.destination_root("codex", project), expected)
        self.assertEqual(installer.destination_root("codex", expected), expected)
        with mock.patch.object(Path, "cwd", return_value=project):
            self.assertEqual(installer.destination_root("codex", None), expected)

    def test_destination_root_requires_explicit_global_flag(self) -> None:
        global_root = self.root / "global" / "skills"
        with mock.patch.object(installer, "default_root", return_value=global_root):
            self.assertEqual(installer.destination_root("codex", None, True), global_root)

    def test_global_root_option_before_subcommand(self) -> None:
        project = self.root / "project"
        (project / ".agents" / "skills").mkdir(parents=True)

        with mock.patch.object(installer, "discover_resources", return_value={}):
            result = CliRunner().invoke(installer.cli, ["--root", str(project), "list"])

        self.assertIsNone(result.exception, result.output)
        self.assertEqual(result.exit_code, 0, result.output)

    def test_global_and_root_are_mutually_exclusive(self) -> None:
        result = CliRunner().invoke(
            installer.cli,
            ["--global", "--root", str(self.root), "list"],
        )

        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("不能同时使用", result.output)

    def test_install_records_commit_variant_and_hash(self) -> None:
        resource = self.make_skill()
        self.install(resource)

        destination = self.target / "demo"
        metadata = json.loads((destination / installer.METADATA_NAME).read_text(encoding="utf-8"))
        self.assertEqual(metadata["resource"], {"name": "demo", "type": "skill", "domain": "public"})
        self.assertEqual(metadata["source"]["variant"], "zh")
        self.assertEqual(metadata["source"]["repository_commit"], "a" * 40)
        self.assertEqual(metadata["source"]["content_hash"], installer.hash_directory(destination))
        self.assertEqual(installer.status_for(resource, "codex", self.target).state, "current")

    def test_status_distinguishes_source_update_and_local_modification(self) -> None:
        resource = self.make_skill()
        self.install(resource)
        source_file = resource.variants["zh"].source / "SKILL.md"
        installed_file = self.target / "demo" / "SKILL.md"

        source_file.write_text("repository update", encoding="utf-8")
        self.assertEqual(installer.status_for(resource, "codex", self.target).state, "update_available")

        installed_file.write_text("local edit", encoding="utf-8")
        self.assertEqual(installer.status_for(resource, "codex", self.target).state, "update_and_modified")

    def test_reinstall_restores_local_modification(self) -> None:
        resource = self.make_skill()
        self.install(resource)
        installed_file = self.target / "demo" / "SKILL.md"
        installed_file.write_text("local edit", encoding="utf-8")
        self.assertEqual(installer.status_for(resource, "codex", self.target).state, "modified")

        self.install(resource)

        self.assertEqual(installed_file.read_text(encoding="utf-8"), "# demo\n\nzh\n")
        self.assertEqual(installer.status_for(resource, "codex", self.target).state, "current")

    def test_update_command_restores_modified_installation(self) -> None:
        resource = self.make_skill()
        project = self.root / "project"
        cli_target = project / ".agents" / "skills"
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(installer, "repository_state", return_value=("a" * 40, False)),
        ):
            installer.install_resource(resource, resource.variants["zh"], "codex", cli_target)
        installed_file = cli_target / "demo" / "SKILL.md"
        installed_file.write_text("local edit", encoding="utf-8")

        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(installer, "discover_resources", return_value={"demo": resource}),
            mock.patch.object(installer, "repository_state", return_value=("b" * 40, True)),
        ):
            result = CliRunner().invoke(
                installer.cli,
                ["update", "demo", "--yes", "--root", str(project)],
            )

        self.assertIsNone(result.exception, result.output)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(installed_file.read_text(encoding="utf-8"), "# demo\n\nzh\n")

    def test_update_command_switches_variant_and_reinstalls(self) -> None:
        resource = self.make_skill()
        project = self.root / "project"
        cli_target = project / ".agents" / "skills"
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(installer, "repository_state", return_value=("a" * 40, False)),
        ):
            installer.install_resource(resource, resource.variants["zh"], "codex", cli_target)

        common_patches = (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(installer, "discover_resources", return_value={"demo": resource}),
            mock.patch.object(installer, "repository_state", return_value=("b" * 40, True)),
        )
        with common_patches[0], common_patches[1], common_patches[2]:
            switched = CliRunner().invoke(
                installer.cli,
                ["--root", str(project), "update", "demo", "--variant", "en"],
            )
        installed_file = cli_target / "demo" / "SKILL.md"
        self.assertIsNone(switched.exception, switched.output)
        self.assertEqual(installed_file.read_text(encoding="utf-8"), "# demo\n\nen\n")

        installed_file.write_text("local edit", encoding="utf-8")
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(installer, "discover_resources", return_value={"demo": resource}),
            mock.patch.object(installer, "repository_state", return_value=("c" * 40, True)),
        ):
            reinstalled = CliRunner().invoke(
                installer.cli,
                ["update", "demo", "--reinstall", "--root", str(project)],
            )
        self.assertIsNone(reinstalled.exception, reinstalled.output)
        self.assertEqual(installed_file.read_text(encoding="utf-8"), "# demo\n\nen\n")

    def test_force_install_can_replace_a_file(self) -> None:
        resource = self.make_skill()
        self.target.mkdir()
        destination = self.target / "demo"
        destination.write_text("old file", encoding="utf-8")

        self.install(resource)

        self.assertTrue(destination.is_dir())
        self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), "# demo\n\nzh\n")

    def test_atomic_install_rolls_back_when_replacement_fails(self) -> None:
        resource = self.make_skill()
        self.install(resource)
        destination = self.target / "demo"
        original = (destination / "SKILL.md").read_text(encoding="utf-8")
        real_rename = Path.rename

        def failing_rename(path: Path, target: Path):
            if path.name.startswith(".demo.install-"):
                raise OSError("simulated failure")
            return real_rename(path, target)

        with mock.patch.object(Path, "rename", autospec=True, side_effect=failing_rename):
            with self.assertRaisesRegex(OSError, "simulated failure"):
                installer.atomic_install(resource.variants["en"].source, destination, {"schema_version": 1})

        self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), original)

    def test_unmanaged_destination_is_reported(self) -> None:
        resource = self.make_skill()
        destination = self.target / "demo"
        destination.mkdir(parents=True)
        (destination / "personal.txt").write_text("keep", encoding="utf-8")

        status = installer.status_for(resource, "codex", self.target)

        self.assertEqual(status.state, "unmanaged")
        self.assertEqual((destination / "personal.txt").read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
