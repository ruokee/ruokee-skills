import importlib.util
import json
import os
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
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="resource-install-test-"
        )
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
            (source / "SKILL.md").write_text(
                f"# {name}\n\n{variant}\n", encoding="utf-8"
            )
            sources[variant] = installer.Variant(variant, source)
        return installer.Resource(name, "skill", "public", workspace, sources)

    def write_v2_metadata(
        self,
        workspace: Path,
        *,
        default: str = "en",
        base: str | None = None,
        extra_top: str = "",
        extra_variants: str = "",
        schema_version: int = 1,
        layout_version: int = 2,
    ) -> None:
        base = base or f"skills/{workspace.name}"
        (workspace / "meta.toml").write_text(
            f'''schema_version = {schema_version}
resource_type = "skill"
{extra_top}
[variants]
layout_version = {layout_version}
default = "{default}"
base = "{base}"
{extra_variants}''',
            encoding="utf-8",
        )

    def make_v2_skill(
        self,
        name: str = "demo",
        overlays: tuple[str, ...] = ("zh",),
        default: str = "en",
    ):
        workspace = self.repo / "public" / name
        base = workspace / "skills" / name
        (base / "references").mkdir(parents=True)
        (base / "scripts").mkdir()
        (base / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: base\n---\n\n# {name}\n\nEnglish\n",
            encoding="utf-8",
        )
        (base / "references" / "guide.md").write_text(
            "English guide\n", encoding="utf-8"
        )
        script = base / "scripts" / "run"
        script.write_text("#!/bin/sh\n", encoding="utf-8")
        script.chmod(0o755)
        for overlay_name in overlays:
            overlay = workspace / "variants" / overlay_name
            overlay.mkdir(parents=True)
            (overlay / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {overlay_name}\n---\n\n# {name}\n\n{overlay_name}\n",
                encoding="utf-8",
            )
        self.write_v2_metadata(workspace, default=default)
        return installer.discover_resources(self.repo)[name]

    def install(self, resource, variant: str = "zh") -> None:
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "repository_state", return_value=("a" * 40, False)
            ),
        ):
            installer.install_resource(
                resource, resource.variants[variant], "codex", self.target
            )

    def test_discovers_direct_and_language_variant_skills(self) -> None:
        direct = self.repo / "fork" / "plain" / "plain"
        direct.mkdir(parents=True)
        (direct / "SKILL.md").write_text("plain", encoding="utf-8")
        self.make_skill()

        resources = installer.discover_resources(self.repo)

        self.assertEqual(set(resources), {"demo", "plain"})
        self.assertEqual(set(resources["demo"].variants), {"en", "zh"})
        self.assertEqual(set(resources["plain"].variants), {"default"})

    def test_v2_discovery_uses_logical_variants_and_explicit_default(self) -> None:
        resource = self.make_v2_skill(default="primary")

        self.assertEqual(resource.layout_version, 2)
        self.assertEqual(resource.default_variant, "primary")
        self.assertEqual(set(resource.variants), {"primary", "zh"})
        self.assertNotIn("skills", resource.variants)
        self.assertEqual(installer.choose_variant(resource, None).name, "primary")
        self.assertEqual(installer.choose_variant(resource, None, "zh").name, "zh")
        self.assertEqual(installer.choose_variant(resource, "zh").name, "zh")

    def test_v2_base_only_workspace_exposes_its_named_default(self) -> None:
        resource = self.make_v2_skill(overlays=(), default="en")

        self.assertEqual(set(resource.variants), {"en"})
        self.assertEqual(installer.choose_variant(resource, None).name, "en")

    def test_meta_entry_types_never_fall_back_to_v1(self) -> None:
        for entry_type in ("directory", "symlink", "broken_symlink"):
            with self.subTest(entry_type=entry_type):
                case_repo = self.root / f"meta-{entry_type}"
                workspace = case_repo / "public" / "demo"
                legacy = workspace / "en" / "demo"
                legacy.mkdir(parents=True)
                (legacy / "SKILL.md").write_text("legacy\n", encoding="utf-8")
                metadata = workspace / "meta.toml"
                if entry_type == "directory":
                    metadata.mkdir()
                elif entry_type == "symlink":
                    target = workspace / "metadata-target"
                    target.write_text("schema_version = 1\n", encoding="utf-8")
                    metadata.symlink_to(target.name)
                else:
                    metadata.symlink_to("missing-meta.toml")

                with self.assertRaisesRegex(installer.ResourceError, "meta.toml"):
                    installer.discover_resources(case_repo)

    def test_meta_parse_and_schema_errors_never_fall_back_to_v1(self) -> None:
        cases = {
            "damaged": "not = [valid",
            "unknown-top": """schema_version = 1
resource_type = "skill"
unexpected = true
[variants]
layout_version = 2
default = "en"
base = "skills/demo"
""",
            "unknown-variants": """schema_version = 1
resource_type = "skill"
[variants]
layout_version = 2
default = "en"
base = "skills/demo"
unexpected = true
""",
            "schema": """schema_version = 3
resource_type = "skill"
[variants]
layout_version = 2
default = "en"
base = "skills/demo"
""",
            "layout": """schema_version = 1
resource_type = "skill"
[variants]
layout_version = 7
default = "en"
base = "skills/demo"
""",
        }
        for name, content in cases.items():
            with self.subTest(name=name):
                case_repo = self.root / f"parse-{name}"
                workspace = case_repo / "public" / "demo"
                legacy = workspace / "en" / "demo"
                legacy.mkdir(parents=True)
                (legacy / "SKILL.md").write_text("legacy\n", encoding="utf-8")
                (workspace / "meta.toml").write_text(content, encoding="utf-8")

                with self.assertRaises(installer.ResourceError):
                    installer.discover_resources(case_repo)

    def test_unreadable_meta_never_falls_back_to_v1(self) -> None:
        workspace = self.repo / "public" / "demo"
        legacy = workspace / "en" / "demo"
        legacy.mkdir(parents=True)
        (legacy / "SKILL.md").write_text("legacy\n", encoding="utf-8")
        self.write_v2_metadata(workspace)
        real_open = installer.os.open

        def deny_metadata(path, flags, *args, **kwargs):
            if Path(path) == workspace / "meta.toml":
                raise PermissionError("simulated unreadable metadata")
            return real_open(path, flags, *args, **kwargs)

        with (
            mock.patch.object(installer.os, "open", side_effect=deny_metadata),
            self.assertRaisesRegex(installer.ResourceError, "无法安全读取"),
        ):
            installer.discover_resources(self.repo)

    def test_v2_workspace_and_base_reject_symlinks(self) -> None:
        real_workspace = self.repo / "public" / "real-demo"
        base = real_workspace / "skills" / "demo"
        base.mkdir(parents=True)
        (base / "SKILL.md").write_text(
            "---\nname: demo\ndescription: test\n---\n", encoding="utf-8"
        )
        self.write_v2_metadata(real_workspace)
        linked_workspace = self.repo / "public" / "demo"
        linked_workspace.symlink_to(real_workspace.name, target_is_directory=True)

        with self.assertRaisesRegex(installer.ResourceError, "Workspace"):
            installer.discover_resources(self.repo)

        linked_workspace.unlink()
        real_workspace.rename(linked_workspace)
        linked_base = linked_workspace / "skills" / "demo"
        real_base = linked_workspace / "real-base"
        linked_base.rename(real_base)
        linked_base.symlink_to(real_base, target_is_directory=True)
        self.write_v2_metadata(linked_workspace)

        with self.assertRaisesRegex(installer.ResourceError, "路径组件"):
            installer.discover_resources(self.repo)

    def test_v2_validates_base_path_and_skill_identity(self) -> None:
        invalid_paths = (
            "/absolute/demo",
            "skills/../demo",
            "skills/./demo",
            "skills//demo",
        )
        for index, base_path in enumerate(invalid_paths):
            with self.subTest(base_path=base_path):
                case_repo = self.root / f"base-path-{index}"
                workspace = case_repo / "public" / "demo"
                source = workspace / "skills" / "demo"
                source.mkdir(parents=True)
                (source / "SKILL.md").write_text(
                    "---\nname: demo\ndescription: test\n---\n", encoding="utf-8"
                )
                self.write_v2_metadata(workspace, base=base_path)
                with self.assertRaises(installer.ResourceError):
                    installer.discover_resources(case_repo)

        workspace = self.repo / "public" / "identity"
        source = workspace / "skills" / "identity"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: different\ndescription: test\n---\n", encoding="utf-8"
        )
        self.write_v2_metadata(workspace)
        with self.assertRaisesRegex(installer.ResourceError, "frontmatter name"):
            installer.discover_resources(self.repo)

    def test_v2_rejects_reserved_and_duplicate_logical_variant_names(self) -> None:
        for default in ("skills", "variants"):
            with self.subTest(default=default):
                case_repo = self.root / f"reserved-{default}"
                workspace = case_repo / "public" / "demo"
                base = workspace / "skills" / "demo"
                base.mkdir(parents=True)
                (base / "SKILL.md").write_text(
                    "---\nname: demo\ndescription: test\n---\n", encoding="utf-8"
                )
                self.write_v2_metadata(workspace, default=default)
                with self.assertRaisesRegex(installer.ResourceError, "保留名称"):
                    installer.discover_resources(case_repo)

        resource = self.make_v2_skill()
        workspace = resource.workspace
        self.write_v2_metadata(workspace, default="zh")
        with self.assertRaisesRegex(installer.ResourceError, "不能与 default 同名"):
            installer.discover_resources(self.repo)

    def test_v2_rejects_mixed_v1_and_v2_layouts(self) -> None:
        for legacy_name in ("en", "zh", "other"):
            with self.subTest(legacy_name=legacy_name):
                case_repo = self.root / f"mixed-{legacy_name}"
                original_repo = self.repo
                self.repo = case_repo
                try:
                    resource = self.make_v2_skill()
                finally:
                    self.repo = original_repo
                legacy = resource.workspace / legacy_name / resource.name
                legacy.mkdir(parents=True)
                (legacy / "SKILL.md").write_text("legacy\n", encoding="utf-8")

                with self.assertRaisesRegex(
                    installer.ResourceError, "mixed-variant-layout"
                ):
                    installer.discover_resources(case_repo)

    def test_legacy_v1_shape_scan_of_v2_workspace_only_sees_skills(self) -> None:
        resource = self.make_v2_skill()
        legacy_variants = []
        for candidate in sorted(
            path for path in resource.workspace.iterdir() if path.is_dir()
        ):
            if (candidate / resource.name / "SKILL.md").is_file():
                legacy_variants.append(candidate.name)

        self.assertEqual(legacy_variants, ["skills"])

    def test_repository_with_agents_uses_v2_sparse_layout(self) -> None:
        resource = installer.discover_resources(installer.REPO_ROOT)["with-agents"]

        self.assertEqual(resource.layout_version, 2)
        self.assertEqual(resource.default_variant, "en")
        self.assertEqual(set(resource.variants), {"en", "zh"})
        self.assertEqual(
            resource.workspace,
            installer.REPO_ROOT / "experimential" / "with-agents",
        )
        self.assertFalse((resource.workspace / "en").exists())
        self.assertFalse((resource.workspace / "zh").exists())
        self.assertFalse((resource.workspace / "variants" / "zh" / "scripts").exists())

        with (
            installer.materialized_variant(
                resource, resource.variants["en"]
            ) as english,
            installer.materialized_variant(
                resource, resource.variants["zh"]
            ) as chinese,
        ):
            for relative in ("scripts/with-agents", "scripts/launch-agent"):
                self.assertEqual(
                    (english / relative).read_bytes(), (chinese / relative).read_bytes()
                )
            self.assertNotEqual(
                (english / "SKILL.md").read_text(encoding="utf-8"),
                (chinese / "SKILL.md").read_text(encoding="utf-8"),
            )

        generated = [
            path
            for path in resource.workspace.rglob("*")
            if path.name in ("__pycache__", ".ruff_cache")
            or path.name.endswith((".pyc", ".pyo", ".pyd"))
        ]
        self.assertEqual(generated, [])

    def test_choose_variant_ignores_locale_and_uses_deterministic_priority(
        self,
    ) -> None:
        language_variants = self.make_skill()
        with mock.patch.dict(installer.os.environ, {"LANG": "zh_CN.UTF-8"}):
            self.assertEqual(
                installer.choose_variant(language_variants, None).name, "en"
            )
        self.assertEqual(
            installer.choose_variant(language_variants, None, "zh").name, "zh"
        )
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
        (directory / installer.METADATA_NAME).write_text(
            '{"anything": true}', encoding="utf-8"
        )
        self.assertEqual(installer.hash_directory(directory), before)

    def test_v2_materializes_base_and_sparse_overlay_with_preserved_modes(self) -> None:
        resource = self.make_v2_skill()
        overlay = resource.workspace / "variants" / "zh"
        (overlay / "references").mkdir()
        (overlay / "references" / "guide.md").write_text("中文指南\n", encoding="utf-8")
        (overlay / "references" / "extra.md").write_text("新增\n", encoding="utf-8")
        resource = installer.discover_resources(self.repo)[resource.name]

        with installer.materialized_variant(
            resource, resource.variants["zh"]
        ) as materialized:
            materialized_root = materialized.parent
            self.assertEqual(
                (materialized / "SKILL.md")
                .read_text(encoding="utf-8")
                .splitlines()[-1],
                "zh",
            )
            self.assertEqual(
                (materialized / "references" / "guide.md").read_text(encoding="utf-8"),
                "中文指南\n",
            )
            self.assertEqual(
                (materialized / "references" / "extra.md").read_text(encoding="utf-8"),
                "新增\n",
            )
            self.assertTrue(os.access(materialized / "scripts" / "run", os.X_OK))
        self.assertFalse(materialized_root.exists())

    def test_v2_hashes_materialized_views_per_variant(self) -> None:
        resource = self.make_v2_skill()
        en_before = installer.hash_variant(resource, resource.variants["en"])
        zh_before = installer.hash_variant(resource, resource.variants["zh"])
        self.assertNotEqual(en_before, zh_before)

        overlay_skill = resource.workspace / "variants" / "zh" / "SKILL.md"
        overlay_skill.write_text(
            "---\nname: demo\ndescription: changed\n---\n\n# demo\n\n中文变更\n",
            encoding="utf-8",
        )
        self.assertEqual(
            installer.hash_variant(resource, resource.variants["en"]), en_before
        )
        self.assertNotEqual(
            installer.hash_variant(resource, resource.variants["zh"]), zh_before
        )

        base_reference = (
            resource.workspace / "skills" / "demo" / "references" / "guide.md"
        )
        base_reference.write_text("base changed\n", encoding="utf-8")
        self.assertNotEqual(
            installer.hash_variant(resource, resource.variants["en"]), en_before
        )
        self.assertNotEqual(
            installer.hash_variant(resource, resource.variants["zh"]), zh_before
        )

    def test_v2_rejects_overlay_type_conflicts_and_empty_overlays(self) -> None:
        resource = self.make_v2_skill()
        overlay = resource.workspace / "variants" / "zh"
        (overlay / "references").write_text(
            "cannot replace directory\n", encoding="utf-8"
        )
        with self.assertRaisesRegex(installer.ResourceError, "类型替换"):
            installer.discover_resources(self.repo)

        reverse_repo = self.root / "reverse-type"
        workspace = reverse_repo / "public" / "demo"
        base = workspace / "skills" / "demo"
        base.mkdir(parents=True)
        (base / "SKILL.md").write_text(
            "---\nname: demo\ndescription: test\n---\n", encoding="utf-8"
        )
        overlay_skill = workspace / "variants" / "zh" / "SKILL.md"
        overlay_skill.mkdir(parents=True)
        (overlay_skill / "nested.md").write_text("invalid\n", encoding="utf-8")
        self.write_v2_metadata(workspace)
        with self.assertRaisesRegex(installer.ResourceError, "类型替换"):
            installer.discover_resources(reverse_repo)

        other_repo = self.root / "empty-overlay"
        workspace = other_repo / "public" / "demo"
        base = workspace / "skills" / "demo"
        base.mkdir(parents=True)
        (base / "SKILL.md").write_text(
            "---\nname: demo\ndescription: test\n---\n", encoding="utf-8"
        )
        (workspace / "variants" / "zh").mkdir(parents=True)
        self.write_v2_metadata(workspace)
        with self.assertRaisesRegex(installer.ResourceError, "至少需要一个普通文件"):
            installer.discover_resources(other_repo)

    def test_v2_rejects_symlink_overlay_directory(self) -> None:
        resource = self.make_v2_skill(overlays=())
        translation = resource.workspace / "translation-source"
        translation.mkdir()
        (translation / "SKILL.md").write_text(
            "---\nname: demo\ndescription: translated\n---\n", encoding="utf-8"
        )
        variants = resource.workspace / "variants"
        variants.mkdir()
        (variants / "zh").symlink_to(translation, target_is_directory=True)

        with self.assertRaisesRegex(installer.ResourceError, "overlay 必须"):
            installer.discover_resources(self.repo)

    def test_v2_rejects_unsafe_overlay_entries(self) -> None:
        entry_types = ("symlink", "fifo", "bytecode", "metadata")
        for entry_type in entry_types:
            with self.subTest(entry_type=entry_type):
                case_repo = self.root / f"unsafe-{entry_type}"
                workspace = case_repo / "public" / "demo"
                base = workspace / "skills" / "demo"
                base.mkdir(parents=True)
                (base / "SKILL.md").write_text(
                    "---\nname: demo\ndescription: test\n---\n", encoding="utf-8"
                )
                overlay = workspace / "variants" / "zh"
                overlay.mkdir(parents=True)
                safe_file = overlay / "translation.md"
                safe_file.write_text("translation\n", encoding="utf-8")
                if entry_type == "symlink":
                    (overlay / "linked.md").symlink_to(safe_file.name)
                elif entry_type == "fifo":
                    os.mkfifo(overlay / "pipe")
                elif entry_type == "bytecode":
                    (overlay / "module.pyc").write_bytes(b"generated")
                else:
                    (overlay / installer.METADATA_NAME).write_text(
                        "{}\n", encoding="utf-8"
                    )
                self.write_v2_metadata(workspace)

                with self.assertRaises(installer.ResourceError):
                    installer.discover_resources(case_repo)

    def test_v2_materialization_tempdirs_are_cleaned_on_success_and_failure(
        self,
    ) -> None:
        resource = self.make_v2_skill()
        temporary_root = self.root / "materialized"
        temporary_root.mkdir()
        real_temporary_directory = tempfile.TemporaryDirectory
        created: list[Path] = []

        def tracked_temporary_directory(*args, **kwargs):
            kwargs["dir"] = temporary_root
            context = real_temporary_directory(*args, **kwargs)
            created.append(Path(context.name))
            return context

        with mock.patch.object(
            installer.tempfile,
            "TemporaryDirectory",
            side_effect=tracked_temporary_directory,
        ):
            installer.hash_variant(resource, resource.variants["zh"])
            with (
                mock.patch.object(installer, "REPO_ROOT", self.repo),
                mock.patch.object(
                    installer, "repository_state", return_value=("a" * 40, False)
                ),
                mock.patch.object(
                    installer, "atomic_install", side_effect=OSError("install failed")
                ),
                self.assertRaisesRegex(OSError, "install failed"),
            ):
                installer.install_resource(
                    resource, resource.variants["zh"], "codex", self.target
                )

        self.assertGreaterEqual(len(created), 2)
        self.assertTrue(all(not path.exists() for path in created))

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
            self.assertEqual(
                installer.destination_root("codex", None, True), global_root
            )

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
        metadata = json.loads(
            (destination / installer.METADATA_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(
            metadata["resource"], {"name": "demo", "type": "skill", "domain": "public"}
        )
        self.assertEqual(metadata["source"]["variant"], "zh")
        self.assertEqual(metadata["source"]["repository_commit"], "a" * 40)
        self.assertEqual(
            metadata["source"]["content_hash"], installer.hash_directory(destination)
        )
        self.assertEqual(
            installer.status_for(resource, "codex", self.target).state, "current"
        )

    def test_v2_install_records_workspace_layers_and_materialized_hash(self) -> None:
        resource = self.make_v2_skill()
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "repository_state", return_value=("b" * 40, True)
            ),
        ):
            installer.install_resource(
                resource, resource.variants["zh"], "codex", self.target
            )

        destination = self.target / "demo"
        metadata = json.loads(
            (destination / installer.METADATA_NAME).read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["source"]["variant"], "zh")
        self.assertEqual(metadata["source"]["path"], "public/demo")
        self.assertEqual(metadata["source"]["layout_version"], 2)
        self.assertEqual(
            metadata["source"]["layers"],
            [
                {"role": "base", "path": "public/demo/skills/demo"},
                {"role": "overlay", "path": "public/demo/variants/zh"},
            ],
        )
        self.assertEqual(
            metadata["source"]["content_hash"], installer.hash_directory(destination)
        )
        self.assertFalse((destination / "variants").exists())
        self.assertEqual(
            installer.status_for(resource, "codex", self.target).state, "current"
        )

    def test_v2_status_maps_legacy_variant_metadata_without_using_old_source_path(
        self,
    ) -> None:
        resource = self.make_v2_skill()
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "repository_state", return_value=("b" * 40, False)
            ),
        ):
            installer.install_resource(
                resource, resource.variants["zh"], "codex", self.target
            )
        metadata_path = self.target / "demo" / installer.METADATA_NAME
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["source"]["path"] = "public/demo/zh/demo"
        metadata["source"].pop("layout_version")
        metadata["source"].pop("layers")
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

        status = installer.status_for(resource, "codex", self.target)

        self.assertEqual(status.state, "current")
        self.assertEqual(status.variant, "zh")

    def test_status_distinguishes_source_update_and_local_modification(self) -> None:
        resource = self.make_skill()
        self.install(resource)
        source_file = resource.variants["zh"].source / "SKILL.md"
        installed_file = self.target / "demo" / "SKILL.md"

        source_file.write_text("repository update", encoding="utf-8")
        self.assertEqual(
            installer.status_for(resource, "codex", self.target).state,
            "update_available",
        )

        installed_file.write_text("local edit", encoding="utf-8")
        self.assertEqual(
            installer.status_for(resource, "codex", self.target).state,
            "update_and_modified",
        )

    def test_reinstall_restores_local_modification(self) -> None:
        resource = self.make_skill()
        self.install(resource)
        installed_file = self.target / "demo" / "SKILL.md"
        installed_file.write_text("local edit", encoding="utf-8")
        self.assertEqual(
            installer.status_for(resource, "codex", self.target).state, "modified"
        )

        self.install(resource)

        self.assertEqual(installed_file.read_text(encoding="utf-8"), "# demo\n\nzh\n")
        self.assertEqual(
            installer.status_for(resource, "codex", self.target).state, "current"
        )

    def test_update_command_restores_modified_installation(self) -> None:
        resource = self.make_skill()
        project = self.root / "project"
        cli_target = project / ".agents" / "skills"
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "repository_state", return_value=("a" * 40, False)
            ),
        ):
            installer.install_resource(
                resource, resource.variants["zh"], "codex", cli_target
            )
        installed_file = cli_target / "demo" / "SKILL.md"
        installed_file.write_text("local edit", encoding="utf-8")

        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "discover_resources", return_value={"demo": resource}
            ),
            mock.patch.object(
                installer, "repository_state", return_value=("b" * 40, True)
            ),
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
            mock.patch.object(
                installer, "repository_state", return_value=("a" * 40, False)
            ),
        ):
            installer.install_resource(
                resource, resource.variants["zh"], "codex", cli_target
            )

        common_patches = (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "discover_resources", return_value={"demo": resource}
            ),
            mock.patch.object(
                installer, "repository_state", return_value=("b" * 40, True)
            ),
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
            mock.patch.object(
                installer, "discover_resources", return_value={"demo": resource}
            ),
            mock.patch.object(
                installer, "repository_state", return_value=("c" * 40, True)
            ),
        ):
            reinstalled = CliRunner().invoke(
                installer.cli,
                ["update", "demo", "--reinstall", "--root", str(project)],
            )
        self.assertIsNone(reinstalled.exception, reinstalled.output)
        self.assertEqual(installed_file.read_text(encoding="utf-8"), "# demo\n\nen\n")

    def test_v2_cli_install_status_switch_and_reinstall_share_materialized_view(
        self,
    ) -> None:
        resource = self.make_v2_skill()
        project = self.root / "v2-project"
        cli_target = project / ".agents" / "skills"
        patches = (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "discover_resources", return_value={"demo": resource}
            ),
            mock.patch.object(
                installer, "repository_state", return_value=("c" * 40, False)
            ),
        )
        with patches[0], patches[1], patches[2]:
            installed = CliRunner().invoke(
                installer.cli,
                ["install", "demo", "--variant", "zh", "--root", str(project)],
            )
        self.assertIsNone(installed.exception, installed.output)
        installed_skill = cli_target / "demo" / "SKILL.md"
        self.assertEqual(
            installed_skill.read_text(encoding="utf-8").splitlines()[-1], "zh"
        )
        self.assertEqual(
            installer.status_for(resource, "codex", cli_target).state, "current"
        )

        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "discover_resources", return_value={"demo": resource}
            ),
            mock.patch.object(
                installer, "repository_state", return_value=("d" * 40, True)
            ),
        ):
            switched = CliRunner().invoke(
                installer.cli,
                ["update", "demo", "--variant", "en", "--root", str(project)],
            )
        self.assertIsNone(switched.exception, switched.output)
        self.assertEqual(
            installed_skill.read_text(encoding="utf-8").splitlines()[-1], "English"
        )

        installed_skill.write_text("local change\n", encoding="utf-8")
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "discover_resources", return_value={"demo": resource}
            ),
            mock.patch.object(
                installer, "repository_state", return_value=("e" * 40, True)
            ),
        ):
            reinstalled = CliRunner().invoke(
                installer.cli,
                ["update", "demo", "--reinstall", "--root", str(project)],
            )
        self.assertIsNone(reinstalled.exception, reinstalled.output)
        self.assertEqual(
            installed_skill.read_text(encoding="utf-8").splitlines()[-1], "English"
        )

    def test_force_install_can_replace_a_file(self) -> None:
        resource = self.make_skill()
        self.target.mkdir()
        destination = self.target / "demo"
        destination.write_text("old file", encoding="utf-8")

        self.install(resource)

        self.assertTrue(destination.is_dir())
        self.assertEqual(
            (destination / "SKILL.md").read_text(encoding="utf-8"), "# demo\n\nzh\n"
        )

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

        with mock.patch.object(
            Path, "rename", autospec=True, side_effect=failing_rename
        ):
            with self.assertRaisesRegex(OSError, "simulated failure"):
                installer.atomic_install(
                    resource.variants["en"].source, destination, {"schema_version": 1}
                )

        self.assertEqual(
            (destination / "SKILL.md").read_text(encoding="utf-8"), original
        )

    def test_v2_materialization_and_destination_failures_preserve_existing_install(
        self,
    ) -> None:
        resource = self.make_v2_skill()
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "repository_state", return_value=("a" * 40, False)
            ),
        ):
            installer.install_resource(
                resource, resource.variants["en"], "codex", self.target
            )
        destination = self.target / "demo"
        original = (destination / "SKILL.md").read_text(encoding="utf-8")

        unsafe = resource.workspace / "variants" / "zh" / installer.METADATA_NAME
        unsafe.write_text("{}\n", encoding="utf-8")
        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "repository_state", return_value=("b" * 40, False)
            ),
            self.assertRaises(installer.ResourceError),
        ):
            installer.install_resource(
                resource, resource.variants["zh"], "codex", self.target
            )
        self.assertEqual(
            (destination / "SKILL.md").read_text(encoding="utf-8"), original
        )

        unsafe.unlink()
        real_rename = Path.rename

        def failing_rename(path: Path, target: Path):
            if path.name.startswith(".demo.install-"):
                raise OSError("simulated v2 replacement failure")
            return real_rename(path, target)

        with (
            mock.patch.object(installer, "REPO_ROOT", self.repo),
            mock.patch.object(
                installer, "repository_state", return_value=("c" * 40, False)
            ),
            mock.patch.object(
                Path, "rename", autospec=True, side_effect=failing_rename
            ),
            self.assertRaisesRegex(OSError, "simulated v2 replacement failure"),
        ):
            installer.install_resource(
                resource, resource.variants["zh"], "codex", self.target
            )
        self.assertEqual(
            (destination / "SKILL.md").read_text(encoding="utf-8"), original
        )

    def test_unmanaged_destination_is_reported(self) -> None:
        resource = self.make_skill()
        destination = self.target / "demo"
        destination.mkdir(parents=True)
        (destination / "personal.txt").write_text("keep", encoding="utf-8")

        status = installer.status_for(resource, "codex", self.target)

        self.assertEqual(status.state, "unmanaged")
        self.assertEqual(
            (destination / "personal.txt").read_text(encoding="utf-8"), "keep"
        )


if __name__ == "__main__":
    unittest.main()
