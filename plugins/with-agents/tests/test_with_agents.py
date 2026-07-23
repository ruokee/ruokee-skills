import hashlib
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid


sys.dont_write_bytecode = True

TEST_ROOT = Path(__file__).resolve().parent
SKILL_ROOT = TEST_ROOT.parent / "skills" / "with-agents"
ZH_OVERLAY_ROOT = TEST_ROOT.parent / "variants" / "zh"
CLI = SKILL_ROOT / "scripts" / "with-agents"
FIXTURE = TEST_ROOT / "fixtures" / "mock_agent.py"
TOP_FIELDS = [
    "ok",
    "event",
    "stage",
    "target",
    "request",
    "notification",
    "screen",
    "error",
    "recovery",
]
REFERENCE_FILES = {
    "references/adapters.md",
    "references/cli.md",
    "references/messaging.md",
    "references/operation-states.md",
    "references/panes-and-lifecycle.md",
    "references/presets.md",
    "references/tmux-recovery.md",
}
TRANSLATABLE_FILES = {
    "SKILL.md",
    "agents/openai.yaml",
    *REFERENCE_FILES,
}


def markdown_translation_contract(
    text: str,
) -> tuple[list[int], list[tuple[str, ...]], list[str], list[str]]:
    heading_levels = []
    fenced_blocks = []
    inline_code = []
    link_paths = []
    current_block = None
    for line in text.splitlines():
        if line.startswith("```"):
            if current_block is None:
                current_block = [line]
            else:
                current_block.append(line)
                fenced_blocks.append(tuple(current_block))
                current_block = None
            continue
        if current_block is not None:
            current_block.append(line)
            continue
        if heading := re.match(r"^(#{1,6}) ", line):
            heading_levels.append(len(heading.group(1)))
        inline_code.extend(re.findall(r"`([^`]+)`", line))
        link_paths.extend(
            target.split("#", 1)[0]
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", line)
            if ".md" in target
        )
    if current_block is not None:
        raise AssertionError("unclosed fenced code block")
    return heading_levels, fenced_blocks, inline_code, link_paths


def load_controller():
    name = f"with_agents_test_{uuid.uuid4().hex}"
    loader = importlib.machinery.SourceFileLoader(name, str(CLI))
    spec = importlib.util.spec_from_loader(name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    loader.exec_module(module)
    return module


CONTROLLER = load_controller()


def tearDownModule() -> None:
    for cache in (
        TEST_ROOT / "__pycache__",
        TEST_ROOT / "fixtures" / "__pycache__",
        SKILL_ROOT / "scripts" / "__pycache__",
    ):
        if cache.is_dir() and not cache.is_symlink():
            shutil.rmtree(cache)


class Harness:
    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="with-agents-test-")
        self.root = Path(self.temporary.name)
        self.socket = self.root / "tmux.sock"
        self.runtime = self.root / "runtime"
        self.config = self.root / "config"
        self.environment = os.environ.copy()
        self.environment.pop("TMUX", None)
        self.environment.pop("TMUX_PANE", None)
        self.environment["WITH_AGENTS_CALLER_ID"] = "unittest"

    def command(
        self, *arguments: str, environment: dict[str, str] | None = None
    ) -> list[str]:
        return [
            sys.executable,
            str(CLI),
            "--json",
            "--socket",
            str(self.socket),
            "--runtime-dir",
            str(self.runtime),
            "--config-dir",
            str(self.config),
            *arguments,
        ]

    def run(
        self,
        *arguments: str,
        ok: bool = True,
        caller_id: str | None = None,
    ) -> tuple[dict, subprocess.CompletedProcess[str]]:
        environment = self.environment.copy()
        if caller_id is not None:
            environment["WITH_AGENTS_CALLER_ID"] = caller_id
        completed = subprocess.run(
            self.command(*arguments),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            timeout=30,
            check=False,
        )
        payload_text = (
            completed.stdout if completed.stdout.strip() else completed.stderr
        )
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"non-JSON output for {arguments}:\nstdout={completed.stdout}\nstderr={completed.stderr}"
            ) from exc
        self.assert_envelope(payload)
        if ok and completed.returncode != 0:
            raise AssertionError(f"command failed: {arguments}\n{payload_text}")
        if not ok and completed.returncode == 0:
            raise AssertionError(
                f"command unexpectedly succeeded: {arguments}\n{payload_text}"
            )
        return payload, completed

    @staticmethod
    def assert_envelope(payload: dict) -> None:
        if list(payload) != TOP_FIELDS:
            raise AssertionError(f"unstable top-level envelope: {list(payload)}")

    def tmux(
        self, *arguments: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["tmux", "-S", str(self.socket), *arguments],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=check,
        )

    def make_agent_executable(self, name: str) -> Path:
        binary_dir = self.root / "bin"
        binary_dir.mkdir(exist_ok=True)
        target = binary_dir / name
        shutil.copyfile(FIXTURE, target)
        target.chmod(0o755)
        return target

    def launch_mock(
        self,
        name: str,
        *,
        executable: Path | None = None,
        mode: str = "idle",
        extra: list[str] | None = None,
    ) -> tuple[dict, Path]:
        log = self.root / f"{name}.jsonl"
        argv = [
            str(executable or Path(sys.executable)),
        ]
        if executable is None:
            argv.extend(["-u", str(FIXTURE)])
        argv.extend(["--log", str(log), "--mode", mode])
        if extra:
            argv.extend(extra)
        payload, _ = self.run(
            "launch", "--name", name, "--cwd", str(TEST_ROOT), "--", *argv
        )
        return payload, log

    def read_log(self, path: Path) -> list[str]:
        if not path.is_file():
            return []
        return [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def close(self) -> None:
        self.tmux("kill-server", check=False)
        self.temporary.cleanup()


class PureContractTests(unittest.TestCase):
    def test_sparse_overlay_inherits_the_only_executable_copy(self) -> None:
        self.assertFalse((ZH_OVERLAY_ROOT / "scripts").exists())
        for relative in ("scripts/with-agents", "scripts/launch-agent"):
            self.assertTrue((SKILL_ROOT / relative).is_file())

    def test_sparse_overlay_contains_only_translatable_files(self) -> None:
        files = {
            path.relative_to(ZH_OVERLAY_ROOT).as_posix()
            for path in ZH_OVERLAY_ROOT.rglob("*")
            if path.is_file()
        }
        self.assertTrue(files)
        self.assertTrue(
            all(
                relative == "SKILL.md"
                or relative.startswith("agents/")
                or relative.startswith("references/")
                for relative in files
            )
        )
        self.assertFalse(any("__pycache__" in relative for relative in files))
        self.assertFalse(
            any(relative.endswith((".pyc", ".pyo", ".pyd")) for relative in files)
        )

    def test_skill_reference_contract_and_sparse_overlay_parity(self) -> None:
        base_files = {
            path.relative_to(SKILL_ROOT).as_posix()
            for path in SKILL_ROOT.rglob("*")
            if path.is_file()
            and (
                path.name == "SKILL.md"
                or path.relative_to(SKILL_ROOT).as_posix().startswith("agents/")
                or path.relative_to(SKILL_ROOT).as_posix().startswith("references/")
            )
        }
        overlay_files = {
            path.relative_to(ZH_OVERLAY_ROOT).as_posix()
            for path in ZH_OVERLAY_ROOT.rglob("*")
            if path.is_file()
        }

        self.assertEqual(base_files, TRANSLATABLE_FILES)
        self.assertEqual(overlay_files, TRANSLATABLE_FILES)

        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for relative in sorted(REFERENCE_FILES):
            self.assertIn(f"]({relative})", skill_text)
            reference_text = (SKILL_ROOT / relative).read_text(encoding="utf-8")
            if len(reference_text.splitlines()) > 100:
                self.assertIn("## Contents", reference_text)

        for relative in sorted(TRANSLATABLE_FILES - {"agents/openai.yaml"}):
            base_contract = markdown_translation_contract(
                (SKILL_ROOT / relative).read_text(encoding="utf-8")
            )
            overlay_contract = markdown_translation_contract(
                (ZH_OVERLAY_ROOT / relative).read_text(encoding="utf-8")
            )
            self.assertEqual(base_contract[:2], overlay_contract[:2], relative)
            self.assertCountEqual(base_contract[2], overlay_contract[2], relative)
            self.assertEqual(base_contract[3], overlay_contract[3], relative)

    def test_envelope_fields_are_frozen(self) -> None:
        envelope = CONTROLLER.new_envelope("test", "ok")
        self.assertEqual(list(envelope), TOP_FIELDS)

    def test_human_render_surfaces_decision_fields(self) -> None:
        envelope = CONTROLLER.new_envelope(
            "launch",
            "launched",
            target={
                "kind": "pane",
                "pane_id": "%1",
                "session_window_pane": "s:1.0",
                "owned": True,
                "readiness": {
                    "adapter": "codex",
                    "state": "idle",
                    "ready_for_send": True,
                },
                "submission": {
                    "tmux_accepted": True,
                    "tui_acceptance": "unverified",
                },
            },
            request={
                "request_id": "wa-20200101T000000-000000000001",
                "stop_polling": True,
                "items": [
                    {
                        "request_id": "wa-20200101T000000-000000000002",
                        "state": "replied",
                        "notification": {"reason": "caller_identity_mismatch"},
                    }
                ],
            },
        )
        rendered = CONTROLLER.render_text(envelope)
        self.assertIn("state:idle ready_for_send:true", rendered)
        self.assertIn("tmux_accepted:true tui_acceptance:unverified", rendered)
        self.assertIn("stop_polling=true", rendered)
        self.assertIn("notify:caller_identity_mismatch", rendered)

    def test_pane_identity_change_invalidates_every_bound_dimension(self) -> None:
        pane = {
            "socket_path": "/tmp/tmux.sock",
            "server_pid": 10,
            "pane_id": "%1",
            "pane_pid": 20,
            "owned": True,
            "run_id": "run-original",
        }
        identity = CONTROLLER.identity_of(pane)
        self.assertTrue(CONTROLLER.identity_matches(identity, pane))

        replacements = {
            "socket_path": "/tmp/other.sock",
            "server_pid": 11,
            "pane_id": "%2",
            "pane_pid": 21,
            "run_id": "run-replaced",
        }
        for field, value in replacements.items():
            with self.subTest(field=field):
                self.assertFalse(
                    CONTROLLER.identity_matches(identity, {**pane, field: value})
                )

    def test_notification_route_ignores_process_identity_but_binds_server_and_pane(
        self,
    ) -> None:
        route = {
            "socket_path": "/tmp/with-agents/../with-agents.sock",
            "server_pid": 10,
            "pane_id": "%1",
            "pane_pid": 20,
            "run_id": "run-original",
        }
        respawned = {
            **route,
            "socket_path": "/tmp/with-agents.sock",
            "pane_pid": 21,
            "run_id": "run-respawned",
        }
        self.assertTrue(CONTROLLER.notification_route_matches(route, respawned))
        for field, value in (
            ("socket_path", "/tmp/other.sock"),
            ("server_pid", 11),
            ("pane_id", "%2"),
        ):
            with self.subTest(field=field):
                self.assertFalse(
                    CONTROLLER.notification_route_matches(
                        route, {**respawned, field: value}
                    )
                )

    def test_notification_diagnostic_distinguishes_failures_from_timeouts(self) -> None:
        pane = {
            "kind": "pane",
            "socket_path": "/tmp/fake-notification.sock",
            "server_pid": 10,
            "pane_id": "%1",
            "pane_pid": 20,
            "run_id": None,
        }
        request = {
            "version": 2,
            "request_id": "wa-20260722T000000-000000000301",
            "notify_mode": "pane",
            "notify_armed": True,
            "caller": {**pane, "kind": "tmux"},
        }
        event = {
            "seq": 1,
            "status": "progress",
            "message": "diagnostic",
            "result": None,
        }

        class FakeClient:
            def __init__(self, scenario: str) -> None:
                self.scenario = scenario

            def pane(self, _target: str) -> dict[str, str | int | None]:
                return pane

            def run(self, arguments, *, stage: str, **_kwargs):
                failure_stage = self.scenario.removesuffix("_timeout")
                if stage == failure_stage:
                    code = (
                        "tmux_timeout"
                        if self.scenario.endswith("_timeout")
                        else "tmux_command_failed"
                    )
                    raise CONTROLLER.WAError(code, "fixture failure")
                return subprocess.CompletedProcess(arguments, 0, "", "")

        strategy = {
            "mode": "generic",
            "id": "generic",
            "adapter": CONTROLLER.ADAPTERS["generic"],
            "agent": {"agent_type": "fixture"},
        }
        scenarios = {
            "notification_text": (
                "notification_text_not_written",
                True,
                False,
                False,
                None,
            ),
            "notification_text_timeout": (
                "notification_text_state_unknown",
                True,
                None,
                False,
                None,
            ),
            "notification_submit": (
                "notification_text_written_not_submitted",
                True,
                True,
                True,
                False,
            ),
            "notification_submit_timeout": (
                "notification_submit_state_unknown",
                True,
                True,
                True,
                None,
            ),
            "success": ("tmux_accepted", True, True, True, True),
        }
        with tempfile.TemporaryDirectory(prefix="with-agents-notification-") as root:
            runtime = CONTROLLER.RuntimeState(str(Path(root) / "runtime"))
            config = CONTROLLER.ConfigState(str(Path(root) / "config"))
            for scenario, expected in scenarios.items():
                with (
                    self.subTest(scenario=scenario),
                    mock.patch.object(
                        CONTROLLER, "TmuxClient", return_value=FakeClient(scenario)
                    ),
                    mock.patch.object(
                        CONTROLLER, "notification_strategy", return_value=strategy
                    ),
                    mock.patch.object(CONTROLLER.time, "sleep"),
                ):
                    notification = CONTROLLER.notify_event_caller(
                        runtime, config, request, event
                    )
                self.assertEqual(notification["reason"], expected[0])
                self.assertEqual(notification["text_attempted"], expected[1])
                self.assertIs(notification["text_tmux_accepted"], expected[2])
                self.assertEqual(notification["submit_attempted"], expected[3])
                self.assertIs(notification["submit_tmux_accepted"], expected[4])
                self.assertIs(notification["tmux_accepted"], scenario == "success")

    def test_async_protocol_context_has_exact_target_without_fixed_transport(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-protocol-") as root:
            runtime = CONTROLLER.RuntimeState(str(Path(root) / "runtime"))
            identifier = "wa-20260722T000000-000000000302"
            caller = {
                "kind": "tmux",
                "socket_path": "/tmp/caller.sock",
                "server_pid": 10,
                "pane_id": "%7",
            }
            suffix = CONTROLLER.protocol_suffix(identifier, runtime, caller)
        self.assertIn("with-agents async", suffix)
        self.assertIn(f"request={identifier}", suffix)
        self.assertIn("controller=", suffix)
        self.assertIn("runtime=", suffix)
        self.assertIn('reply-target=tmux(socket="/tmp/caller.sock",pane="%7")', suffix)
        self.assertIn("choose any available reply transport", suffix)
        self.assertNotIn("if useful", suffix.lower())
        self.assertNotIn("at most once", suffix.lower())
        self.assertNotIn(f" reply {identifier} ", suffix)

    def test_pane_identity_comes_from_one_tmux_format_record(self) -> None:
        client = CONTROLLER.TmuxClient("/tmp/hint.sock")
        fields = [
            "/tmp/actual.sock",
            "10",
            "%1",
            "20",
            "0",
            "",
            "1",
            "run-1",
            "reviewer",
            "preset-1",
            "session",
            "2",
            "3",
            "codex",
            "/worktree",
            "title",
        ]
        with mock.patch.object(
            client, "server", side_effect=AssertionError("separate identity query")
        ):
            pane = client.parse_pane("\t".join(fields))
        self.assertEqual(pane["socket_path"], "/tmp/actual.sock")
        self.assertEqual(pane["server_pid"], 10)
        self.assertEqual(pane["pane_id"], "%1")
        self.assertEqual(pane["pane_pid"], 20)
        self.assertEqual(pane["run_id"], "run-1")

    def test_unresolvable_tmux_caller_cannot_create_an_unverified_credential(
        self,
    ) -> None:
        environment = {"TMUX": "/tmp/missing.sock,1,0", "TMUX_PANE": "%9"}
        with (
            mock.patch.dict(os.environ, environment, clear=False),
            mock.patch.object(
                CONTROLLER.TmuxClient,
                "pane",
                side_effect=CONTROLLER.WAError("target_not_found", "missing"),
            ),
            self.assertRaises(CONTROLLER.WAError) as raised,
        ):
            CONTROLLER.caller_key()
        self.assertEqual(raised.exception.code, "caller_identity_unavailable")

    def test_explicit_socket_does_not_reuse_a_foreign_caller_pane_id(self) -> None:
        class CrossServerClient:
            inherits_caller = False

            def list_sessions(self):
                return ["first", "second"]

            def list_panes(self):
                return []

            def pane(self, _target):
                raise AssertionError("caller pane must not resolve on another server")

        with mock.patch.dict(os.environ, {"TMUX_PANE": "%1"}, clear=False):
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.choose_new_pane(
                    CrossServerClient(),
                    name="target",
                    cwd="/tmp",
                    session=None,
                    split=None,
                )
        self.assertEqual(raised.exception.code, "session_required")

        with self.assertRaises(CONTROLLER.WAError) as raised:
            CONTROLLER.choose_new_pane(
                CrossServerClient(),
                name="target",
                cwd="/tmp",
                session="first",
                split="%2",
            )
        self.assertEqual(raised.exception.code, "layout_source_conflict")

    def test_failed_restart_rotates_identity_before_process_replacement(self) -> None:
        class RestartClient:
            def __init__(self, pane: dict) -> None:
                self.current = dict(pane)
                self.events: list[str] = []

            def pane(self, _target: str) -> dict:
                return dict(self.current)

            def capture(self, _pane_id: str, _lines: int) -> str:
                return "final screen"

            def run(self, arguments: list[str], **_kwargs):
                self.events.append(" ".join(arguments))
                if (
                    arguments[0] == "set-option"
                    and arguments[4] == "@with_agents_run_id"
                ):
                    self.current["run_id"] = arguments[5]
                elif (
                    arguments[0] == "set-option"
                    and arguments[4] == "@with_agents_owner"
                ):
                    self.current["owned"] = arguments[5] == "1"
                elif arguments[0] == "respawn-pane":
                    raise CONTROLLER.WAError("tmux_command_failed", "injected failure")
                return SimpleNamespace(stdout="", returncode=0)

        with tempfile.TemporaryDirectory(prefix="with-agents-restart-") as root:
            runtime = CONTROLLER.RuntimeState(str(Path(root) / "runtime"))
            original = {
                "kind": "pane",
                "socket_path": "/tmp/test.sock",
                "server_pid": 101,
                "pane_id": "%501",
                "pane_pid": 202,
                "session": "test",
                "window_index": "0",
                "pane_index": "0",
                "session_window_pane": "test:0.0",
                "process": "codex",
                "cwd": root,
                "dead": False,
                "dead_status": None,
                "owned": True,
                "run_id": "run-old",
                "name": "reviewer",
                "preset": None,
                "title": "reviewer",
            }
            CONTROLLER.save_owned_record(
                runtime,
                original,
                argv=["codex"],
                cwd=root,
                name="reviewer",
                preset=None,
            )
            CONTROLLER.mark_observed(runtime, original)
            client = RestartClient(original)
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.restart_pane(
                    runtime,
                    client,
                    original,
                    argv=["codex", "--new"],
                    preset=None,
                    force_foreign=False,
                )
            self.assertEqual(raised.exception.stage, "restart_state_unknown")
            run_id_event = next(
                index
                for index, event in enumerate(client.events)
                if "@with_agents_run_id" in event
            )
            respawn_event = next(
                index
                for index, event in enumerate(client.events)
                if event.startswith("respawn-pane")
            )
            self.assertLess(run_id_event, respawn_event)
            self.assertNotEqual(client.current["run_id"], original["run_id"])
            self.assertFalse(
                CONTROLLER.identity_matches(
                    CONTROLLER.identity_of(original), client.current
                )
            )
            self.assertFalse(
                CONTROLLER.owned_record_path(runtime, original["run_id"]).exists()
            )

    def test_adapter_state_requires_positive_empty_composer(self) -> None:
        self.assertEqual(
            CONTROLLER.classify_adapter_state("codex", "result only"), "unknown"
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state("codex", "result\n› "), "idle"
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state("codex", "esc to interrupt\n› "),
            "busy_queueable",
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state(
                "codex", "Allow destructive action? [y/N]\n› "
            ),
            "unsafe",
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state("codex", "› partially typed"), "unsafe"
        )
        self.assertEqual(CONTROLLER.classify_adapter_state("claude", "› "), "unknown")

        placeholder = "\x1b[1m›\x1b[0m \x1b[2mFind and fix a bug\x1b[0m"
        self.assertEqual(
            CONTROLLER.classify_adapter_state("codex", placeholder), "idle"
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state(
                "codex", "\x1b[0;1m›\x1b[0m \x1b[2mFind and fix a bug"
            ),
            "idle",
        )
        background_placeholder = (
            "\x1b[1;38;5;250m›\x1b[0m "
            "\x1b[48;2;32;35;42m\x1b[2mFind and fix a bug\x1b[22;49m"
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state("codex", background_placeholder),
            "idle",
        )
        background_real_input = (
            "\x1b[1m›\x1b[0m \x1b[48;2;32;35;42mFind and fix a bug\x1b[49m"
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state("codex", background_real_input),
            "unsafe",
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state(
                "codex", f"› prior submitted prompt\noutput\n{placeholder}"
            ),
            "idle",
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state(
                "codex", f"esc to interrupt\n{placeholder}"
            ),
            "busy_queueable",
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state("codex", "\x1b[1m›\x1b[0m partial-input"),
            "unsafe",
        )
        self.assertEqual(CONTROLLER.classify_adapter_state("pi", placeholder), "unsafe")

        border = "─" * 80
        pi_idle = "\n".join(
            [
                "pi v0.80.6",
                "escape interrupt · ctrl+c/ctrl+d clear/exit",
                border,
                "",
                border,
                "~/worktree",
                "0.2%/1.0M deepseek-v4-flash • max",
            ]
        )
        self.assertEqual(CONTROLLER.classify_adapter_state("pi", pi_idle), "idle")
        self.assertEqual(
            CONTROLLER.classify_adapter_state(
                "pi", pi_idle.replace(border, f"⠋ Working...\n{border}", 1)
            ),
            "busy_queueable",
        )
        self.assertEqual(
            CONTROLLER.classify_adapter_state(
                "pi",
                pi_idle.replace(
                    f"{border}\n\n{border}", f"{border}\npartial input\n{border}"
                ),
            ),
            "unsafe",
        )
        self.assertEqual(CONTROLLER.ADAPTERS["codex"]["busy_key"], "Enter")
        self.assertEqual(CONTROLLER.ADAPTERS["pi"]["busy_key"], "Enter")
        self.assertNotIn("extended_keys", CONTROLLER.ADAPTERS["pi"])

    def test_agent_detection_ignores_names_inside_task_arguments(self) -> None:
        pane = {
            "kind": "pane",
            "socket_path": "/tmp/fake.sock",
            "server_pid": 1,
            "pane_id": "%1",
            "pane_pid": 100,
            "owned": False,
            "run_id": None,
            "process": "zsh",
        }
        agent_row = (101, 100, "MainThread", "node /usr/local/bin/codex")
        controller_row = (
            102,
            101,
            "python3",
            "python3 /opt/with-agents request -- 'ask Codex and Pi to review'",
        )
        with tempfile.TemporaryDirectory(prefix="with-agents-detect-") as directory:
            runtime = CONTROLLER.RuntimeState(directory)
            with mock.patch.object(
                CONTROLLER, "process_rows", return_value=[agent_row, controller_row]
            ):
                kind, _, fingerprint = CONTROLLER.detect_agent(runtime, pane)
        expected = (
            "process:"
            + hashlib.sha256(
                f"{agent_row[0]}\x00{agent_row[1]}\x00{agent_row[2]}\x00{agent_row[3]}".encode()
            ).hexdigest()
        )
        self.assertEqual(kind, "codex")
        self.assertEqual(fingerprint, expected)
        self.assertIsNone(CONTROLLER.process_agent_candidate(controller_row))
        pi_candidate = CONTROLLER.process_agent_candidate(
            (103, 100, "env", "env PROVIDER=test pi --model example")
        )
        self.assertIsNotNone(pi_candidate)
        self.assertEqual(pi_candidate[0], "pi")

    def test_notification_only_recognizes_the_tmux_foreground_process(self) -> None:
        pane = {
            "kind": "pane",
            "socket_path": "/tmp/fake.sock",
            "server_pid": 1,
            "pane_id": "%1",
            "pane_pid": 100,
            "owned": False,
            "run_id": None,
            "process": "zsh",
        }
        shell = (100, 1, "zsh", "zsh")
        background_agent = (101, 100, "node", "node /usr/local/bin/codex")
        with tempfile.TemporaryDirectory(prefix="with-agents-foreground-") as directory:
            config = CONTROLLER.ConfigState(directory)
            with mock.patch.object(
                CONTROLLER,
                "process_rows",
                return_value=[shell, background_agent],
            ):
                shell_strategy = CONTROLLER.notification_strategy(config, pane)
                agent_strategy = CONTROLLER.notification_strategy(
                    config, {**pane, "process": "node"}
                )
        self.assertEqual(shell_strategy["mode"], "skip")
        self.assertEqual(shell_strategy["reason"], "caller_not_agent")
        self.assertEqual(agent_strategy["mode"], "capability")
        self.assertEqual(agent_strategy["id"], "codex")

    def test_owned_relative_agent_executable_resolves_from_launch_cwd(self) -> None:
        pane = {
            "kind": "pane",
            "socket_path": "/tmp/fake.sock",
            "server_pid": 1,
            "pane_id": "%1",
            "pane_pid": 100,
            "owned": True,
            "run_id": "run-relative",
        }
        with tempfile.TemporaryDirectory(prefix="with-agents-detect-") as directory:
            runtime = CONTROLLER.RuntimeState(directory)
            launch_cwd = Path(directory) / "worktree"
            launch_cwd.mkdir()
            CONTROLLER.save_owned_record(
                runtime,
                pane,
                argv=["./bin/codex"],
                cwd=str(launch_cwd),
                name="relative",
                preset=None,
            )
            kind, executable, fingerprint = CONTROLLER.detect_agent(runtime, pane)
            self.assertEqual(kind, "codex")
            self.assertEqual(executable, str((launch_cwd / "bin/codex").resolve()))
            self.assertTrue(fingerprint.startswith("owned:"))

            CONTROLLER.save_owned_record(
                runtime,
                pane,
                argv=["node", "./bin/codex", "task"],
                cwd=str(launch_cwd),
                name="relative",
                preset=None,
            )
            kind, executable, _ = CONTROLLER.detect_agent(runtime, pane)
            self.assertEqual(kind, "codex")
            self.assertEqual(executable, str((launch_cwd / "bin/codex").resolve()))

    def test_reply_message_limits_and_controls(self) -> None:
        self.assertEqual(CONTROLLER.validate_reply_message("ok"), "ok")
        with self.assertRaises(CONTROLLER.WAError):
            CONTROLLER.validate_reply_message("x" * 1025)
        with self.assertRaises(CONTROLLER.WAError):
            CONTROLLER.validate_reply_message("two\nlines")
        with self.assertRaises(CONTROLLER.WAError):
            CONTROLLER.validate_reply_message("bad\x1b[31m")
        with self.assertRaises(CONTROLLER.WAError):
            CONTROLLER.validate_reply_message("bad\u009b31m")
        with self.assertRaises(CONTROLLER.WAError):
            CONTROLLER.validate_reply_message("two\u2028lines")
        with self.assertRaises(CONTROLLER.WAError):
            CONTROLLER.validate_reply_message("two\u2029lines")
        with self.assertRaises(CONTROLLER.WAError):
            CONTROLLER.validate_message("bad\u009dtitle")
        self.assertEqual(CONTROLLER.validate_message("two\nlines"), "two\nlines")
        request = {
            "request_id": "wa-20260722T000000-000000000303",
        }
        event = {
            "seq": 4,
            "status": "done",
            "message": "complete",
            "result": {"path": "/tmp/managed/result.txt"},
        }
        self.assertEqual(
            CONTROLLER.notification_doorbell(request, event),
            "[with-agents reply request=wa-20260722T000000-000000000303 seq=4 status=done] complete file=/tmp/managed/result.txt",
        )
        self.assertIsNone(
            CONTROLLER.notification_doorbell(
                request,
                {**event, "result": {"path": "/tmp/bad\npath"}},
            )
        )

    def test_request_records_the_child_identity_that_received_the_task(self) -> None:
        initial = {
            "kind": "pane",
            "socket_path": "/tmp/fake.sock",
            "server_pid": 10,
            "pane_id": "%2",
            "pane_pid": 20,
            "owned": True,
            "run_id": "run-old",
        }
        dispatched = {**initial, "pane_pid": 21, "run_id": "run-new"}

        class FakeClient:
            def resolve(self, _target: str) -> dict:
                return initial

        args = SimpleNamespace(
            socket=None,
            target="child",
            message="review",
            reply_to=None,
            reply_socket=None,
            notify="spool",
            reply_ttl=None,
            allow_foreign=False,
        )
        with tempfile.TemporaryDirectory(prefix="with-agents-request-") as directory:
            runtime = CONTROLLER.RuntimeState(directory)
            with (
                mock.patch.object(CONTROLLER, "TmuxClient", return_value=FakeClient()),
                mock.patch.object(
                    CONTROLLER,
                    "current_caller_route",
                    return_value=({"kind": "external"}, None, None),
                ),
                mock.patch.object(
                    CONTROLLER,
                    "send_core",
                    return_value=(dispatched, CONTROLLER.screen_object("", 80)),
                ),
            ):
                result = CONTROLLER.command_request(args, runtime, None)
            record, _ = CONTROLLER.load_request(
                runtime, result["request"]["request_id"]
            )
        self.assertEqual(record["child"], CONTROLLER.identity_of(dispatched))

    def test_request_releases_request_lock_before_dispatching_to_pane(self) -> None:
        identifier = "wa-20260722T000000-000000000304"
        child = {
            "kind": "pane",
            "socket_path": "/tmp/fake.sock",
            "server_pid": 10,
            "pane_id": "%2",
            "pane_pid": 20,
            "owned": True,
            "run_id": "run-child",
        }

        class FakeClient:
            def resolve(self, _target: str) -> dict:
                return child

        args = SimpleNamespace(
            socket=None,
            target="child",
            message="review",
            reply_to=None,
            reply_socket=None,
            notify="spool",
            reply_ttl=None,
            allow_foreign=False,
        )
        with tempfile.TemporaryDirectory(prefix="with-agents-request-lock-") as root:
            runtime = CONTROLLER.RuntimeState(root)
            dispatch_observations = []

            def send_without_nested_request_lock(*_args, **_kwargs):
                record, directory = CONTROLLER.load_request(runtime, identifier)
                self.assertEqual(record["phase"], "dispatching")
                with CONTROLLER.request_lock(runtime, directory, timeout=0.0):
                    dispatch_observations.append(True)
                return child, CONTROLLER.screen_object("", 80)

            with (
                mock.patch.object(CONTROLLER, "TmuxClient", return_value=FakeClient()),
                mock.patch.object(
                    CONTROLLER,
                    "current_caller_route",
                    return_value=({"kind": "external"}, None, None),
                ),
                mock.patch.object(CONTROLLER, "request_id", return_value=identifier),
                mock.patch.object(
                    CONTROLLER,
                    "send_core",
                    side_effect=send_without_nested_request_lock,
                ),
            ):
                result = CONTROLLER.command_request(args, runtime, None)

            record, _ = CONTROLLER.load_request(runtime, identifier)
        self.assertEqual(dispatch_observations, [True])
        self.assertEqual(result["request"]["phase"], "active")
        self.assertEqual(record["phase"], "active")

    def test_runtime_and_config_roots_reject_final_symlinks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-root-") as directory:
            root = Path(directory)
            real_runtime = root / "real-runtime"
            real_runtime.mkdir()
            runtime_link = root / "runtime-link"
            runtime_link.symlink_to(real_runtime, target_is_directory=True)
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.RuntimeState(str(runtime_link))
            self.assertEqual(raised.exception.code, "unsafe_state_path")

            real_config = root / "real-config"
            real_config.mkdir()
            config_link = root / "config-link"
            config_link.symlink_to(real_config, target_is_directory=True)
            config = CONTROLLER.ConfigState(str(config_link))
            with self.assertRaises(CONTROLLER.WAError) as raised:
                _ = config.presets
            self.assertEqual(raised.exception.code, "unsafe_state_path")

    def test_agent_registry_merges_defaults_and_recognizes_launcher_argv(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-config-") as directory:
            root = Path(directory) / "config"
            config = CONTROLLER.ConfigState(str(root))
            self.assertEqual(
                CONTROLLER.load_agent_registry(config),
                {
                    "codex": {"pane_prefix": "cx", "executables": ["codex"]},
                    "claude": {"pane_prefix": "cc", "executables": ["claude"]},
                    "pi": {"pane_prefix": "pi", "executables": ["pi"]},
                },
            )
            self.assertFalse(root.exists())

            CONTROLLER.atomic_write_json(
                config.agent_config,
                {
                    "version": 1,
                    "agents": {
                        "codex": {"pane_prefix": "cdx"},
                        "pi": {"executables": ["Pi-CLI.EXE"]},
                        "opencode": {
                            "pane_prefix": "oc",
                            "executables": ["OpenCode.EXE"],
                        },
                    },
                },
            )
            registry = CONTROLLER.load_agent_registry(config)
            self.assertEqual(registry["codex"]["pane_prefix"], "cdx")
            self.assertEqual(registry["pi"]["executables"], ["pi-cli"])
            self.assertEqual(registry["opencode"]["executables"], ["opencode"])
            self.assertEqual(
                CONTROLLER.registry_agent_type_from_argv(
                    ["/opt/OpenCode.EXE", "codex in task text"], registry
                ),
                "opencode",
            )
            for argv in (
                ["env", "-i", "PROVIDER=test", "opencode", "task"],
                ["node", "--trace-warnings", "/opt/opencode", "task"],
                ["python3", "-u", "/opt/opencode", "task"],
            ):
                self.assertEqual(
                    CONTROLLER.registry_agent_type_from_argv(argv, registry),
                    "opencode",
                )
            self.assertIsNone(
                CONTROLLER.registry_agent_type_from_argv(
                    ["runner", "--task", "ask opencode"], registry
                )
            )
            self.assertEqual(
                CONTROLLER.kind_from_argv(["node", "/opt/codex", "task"]),
                "codex",
            )

    def test_agent_registry_rejects_any_invalid_full_table(self) -> None:
        invalid_values = (
            {"version": 2, "agents": {}},
            {"version": 1, "agents": {}, "extra": True},
            {"version": 1, "agents": []},
            {"version": 1, "agents": {"codex": {"unknown": "value"}}},
            {"version": 1, "agents": {"opencode": {"pane_prefix": "oc"}}},
            {
                "version": 1,
                "agents": {
                    "codex": {"executables": ["shared"]},
                    "pi": {"executables": ["shared"]},
                },
            },
            {"version": 1, "agents": {"codex": {"pane_prefix": "bad--prefix"}}},
            {"version": 1, "agents": {"codex": {"executables": ["bin/codex"]}}},
            {
                "version": 1,
                "agents": {
                    "generic": {
                        "pane_prefix": "generic",
                        "executables": ["generic-agent"],
                    }
                },
            },
        )
        for index, value in enumerate(invalid_values):
            with self.subTest(index=index):
                with tempfile.TemporaryDirectory(
                    prefix="with-agents-invalid-config-"
                ) as directory:
                    config = CONTROLLER.ConfigState(str(Path(directory) / "config"))
                    CONTROLLER.atomic_write_json(config.agent_config, value)
                    with self.assertRaises(CONTROLLER.WAError) as raised:
                        CONTROLLER.load_agent_registry(config)
                    self.assertEqual(raised.exception.code, "invalid_agent_config")

        with tempfile.TemporaryDirectory(
            prefix="with-agents-invalid-config-"
        ) as directory:
            config = CONTROLLER.ConfigState(str(Path(directory) / "config"))
            config.root.mkdir()
            config.agent_config.write_text("{not json", encoding="utf-8")
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.load_agent_registry(config)
            self.assertEqual(raised.exception.code, "invalid_agent_config")

        with tempfile.TemporaryDirectory(
            prefix="with-agents-invalid-config-"
        ) as directory:
            root = Path(directory)
            config = CONTROLLER.ConfigState(str(root / "config"))
            config.root.mkdir()
            target = root / "actual.json"
            target.write_text('{"version": 1, "agents": {}}', encoding="utf-8")
            config.agent_config.symlink_to(target)
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.load_agent_registry(config)
            self.assertEqual(raised.exception.code, "invalid_agent_config")

    def test_launch_name_sources_and_config_consumption_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory(
            prefix="with-agents-launch-spec-"
        ) as directory:
            config = CONTROLLER.ConfigState(str(Path(directory) / "config"))
            CONTROLLER.atomic_write_json(
                config.ensure_presets() / "review.json",
                {
                    "version": 1,
                    "agent_type": "codex",
                    "pane_name": "saved-name",
                    "argv": ["codex", "--model", "example"],
                },
            )

            def arguments(**overrides):
                values = {
                    "preset": "review",
                    "name": None,
                    "name_suffix": None,
                    "argv": [],
                }
                values.update(overrides)
                return SimpleNamespace(**values)

            with mock.patch.object(
                CONTROLLER,
                "load_agent_registry",
                side_effect=AssertionError("default/full name must not read config"),
            ):
                self.assertEqual(
                    CONTROLLER.resolve_launch_spec(arguments(), config)[1],
                    "saved-name",
                )
                self.assertEqual(
                    CONTROLLER.resolve_launch_spec(
                        arguments(name="one-off-review"), config
                    )[1],
                    "one-off-review",
                )
            self.assertEqual(
                CONTROLLER.resolve_launch_spec(arguments(name_suffix="worker"), config)[
                    1
                ],
                "cx-worker",
            )

            error_cases = (
                (
                    arguments(name="full", name_suffix="suffix"),
                    "pane_name_source_conflict",
                ),
                (
                    arguments(preset=None, name_suffix="suffix"),
                    "name_suffix_requires_preset",
                ),
                (arguments(argv=["--", "codex"]), "launch_source_conflict"),
                (arguments(name_suffix=""), "invalid_pane_name"),
                (arguments(name_suffix="bad--suffix"), "invalid_pane_name"),
            )
            for args, code in error_cases:
                with self.subTest(code=code):
                    with self.assertRaises(CONTROLLER.WAError) as raised:
                        CONTROLLER.resolve_launch_spec(args, config)
                    self.assertEqual(raised.exception.code, code)

            CONTROLLER.atomic_write_json(
                config.ensure_presets() / "external.json",
                {
                    "version": 1,
                    "agent_type": "external",
                    "pane_name": "external-default",
                    "argv": ["unknown-agent"],
                },
            )
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.resolve_launch_spec(
                    arguments(preset="external", name_suffix="worker"), config
                )
            self.assertEqual(raised.exception.code, "agent_prefix_not_configured")

    def test_empty_or_relative_xdg_roots_use_the_standard_fallback(self) -> None:
        fallback = Path("/absolute/fallback")
        for value in ("", "relative/path"):
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": value}, clear=False):
                self.assertEqual(
                    CONTROLLER.xdg_directory("XDG_CONFIG_HOME", fallback), fallback
                )
        with mock.patch.dict(
            os.environ, {"XDG_CONFIG_HOME": "/absolute/config"}, clear=False
        ):
            self.assertEqual(
                CONTROLLER.xdg_directory("XDG_CONFIG_HOME", fallback),
                Path("/absolute/config"),
            )

    def test_exclusive_json_is_complete_before_write_once_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-atomic-") as directory:
            path = Path(directory) / "state.json"
            first = {"version": 1, "payload": "x" * 4096}
            real_link = os.link
            observed: list[dict] = []

            def checking_link(source, destination, *, follow_symlinks=True):
                self.assertFalse(Path(destination).exists())
                observed.append(json.loads(Path(source).read_text(encoding="utf-8")))
                return real_link(source, destination, follow_symlinks=follow_symlinks)

            with mock.patch.object(os, "link", side_effect=checking_link):
                CONTROLLER.atomic_write_json(path, first, exclusive=True)
            self.assertEqual(observed, [first])
            self.assertEqual(CONTROLLER.safe_read_json(path), first)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.atomic_write_json(path, {"version": 2}, exclusive=True)
            self.assertEqual(raised.exception.code, "state_exists")
            self.assertEqual(CONTROLLER.safe_read_json(path), first)

    def test_gc_waits_for_the_complete_reply_event(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-reply-gc-") as root:
            runtime = CONTROLLER.RuntimeState(str(Path(root) / "runtime"))
            identifier = "wa-20260721T000000-000000000001"
            directory = CONTROLLER.request_dir(runtime, identifier)
            directory.mkdir(mode=0o700)
            CONTROLLER.atomic_write_json(
                directory / "request.json",
                {
                    "version": 1,
                    "request_id": identifier,
                    "created_at": CONTROLLER.iso_now(),
                    "created_epoch": time.time(),
                    "phase": "active",
                    "caller": {"kind": "external"},
                    "notify_mode": "spool",
                    "notify_armed": False,
                    "reply_ttl_seconds": None,
                },
                exclusive=True,
            )
            notify_entered = threading.Event()
            release_notify = threading.Event()
            gc_finished = threading.Event()
            outcomes: dict[str, dict | BaseException] = {}

            def blocked_notification(*_args):
                notify_entered.set()
                if not release_notify.wait(5):
                    raise AssertionError("notification test gate timed out")
                return CONTROLLER.notification_result("spool_only")

            def reply_worker() -> None:
                try:
                    outcomes["reply"] = CONTROLLER.command_reply(
                        SimpleNamespace(
                            request_id=identifier,
                            status="done",
                            message="complete",
                            file=None,
                        ),
                        runtime,
                        None,
                    )
                except BaseException as exc:
                    outcomes["reply_error"] = exc

            def gc_worker() -> None:
                try:
                    outcomes["gc"] = CONTROLLER.command_gc(
                        SimpleNamespace(stale=None, delete_stale=False),
                        runtime,
                        None,
                    )
                except BaseException as exc:
                    outcomes["gc_error"] = exc
                finally:
                    gc_finished.set()

            with mock.patch.object(
                CONTROLLER, "notify_caller", side_effect=blocked_notification
            ):
                reply_thread = threading.Thread(target=reply_worker)
                reply_thread.start()
                self.assertTrue(notify_entered.wait(5))
                gc_thread = threading.Thread(target=gc_worker)
                gc_thread.start()
                self.assertFalse(gc_finished.wait(0.2))
                release_notify.set()
                reply_thread.join(5)
                gc_thread.join(5)

            self.assertFalse(reply_thread.is_alive())
            self.assertFalse(gc_thread.is_alive())
            self.assertNotIn("reply_error", outcomes)
            self.assertNotIn("gc_error", outcomes)
            reply = outcomes["reply"]
            gc = outcomes["gc"]
            if not isinstance(reply, dict) or not isinstance(gc, dict):
                self.fail("reply and GC workers must return envelopes")
            self.assertEqual(reply["stage"], "spooled")
            self.assertIn(identifier, gc["request"]["removed"])
            self.assertFalse(directory.exists())
            self.assertFalse(CONTROLLER.request_lock_path(runtime, directory).exists())

    def test_managed_result_rejects_directories_and_devices(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-result-") as directory:
            root = Path(directory)
            destination = root / "destination"
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.managed_copy(str(root), destination)
            self.assertEqual(raised.exception.code, "result_file_invalid")
            if Path("/dev/null").exists():
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.managed_copy("/dev/null", destination)
                self.assertEqual(raised.exception.code, "result_file_invalid")

    def test_v2_ttl_is_rechecked_after_managed_copy_without_consuming_seq(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-v2-copy-") as root:
            runtime = CONTROLLER.RuntimeState(str(Path(root) / "runtime"))
            identifier = "wa-20260722T000000-000000000201"
            directory = CONTROLLER.request_dir(runtime, identifier)
            for child in (
                directory,
                directory / "events",
                directory / "notifications",
                directory / "result",
            ):
                child.mkdir(mode=0o700, parents=True, exist_ok=True)
            CONTROLLER.atomic_write_json(
                directory / "request.json",
                {
                    "version": 2,
                    "request_id": identifier,
                    "created_at": CONTROLLER.iso_now(),
                    "created_epoch": 100.0,
                    "phase": "active",
                    "child": {},
                    "caller": {"kind": "external"},
                    "notify_mode": "spool",
                    "notify_armed": False,
                    "reply_ttl_seconds": 1.0,
                    "dispatched_epoch": 100.0,
                    "result_dir": str((directory / "result").resolve()),
                    "limits": CONTROLLER.v2_request_limits(),
                },
                exclusive=True,
            )
            result_file = Path(root) / "result.txt"
            result_file.write_text("copied before deadline", encoding="utf-8")
            with mock.patch.object(CONTROLLER.time, "time", side_effect=(100.5, 101.1)):
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.command_reply(
                        SimpleNamespace(
                            request_id=identifier,
                            status="done",
                            message="late",
                            file=str(result_file),
                        ),
                        runtime,
                        None,
                    )
            self.assertEqual(raised.exception.code, "reply_ticket_expired")
            self.assertEqual(list((directory / "events").iterdir()), [])
            self.assertFalse((directory / "result" / "000001").exists())

    def test_secret_flags_are_rejected_for_presets(self) -> None:
        CONTROLLER.reject_secret_argv(["agent", "--model", "safe"])
        for argv in (
            ["agent", "--api-key", "secret"],
            ["agent", "--access_token=secret"],
            ["env", "PASSWORD=secret", "agent"],
        ):
            with self.assertRaises(CONTROLLER.WAError):
                CONTROLLER.reject_secret_argv(argv)

    def test_preset_rejects_nul_before_launch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-preset-") as directory:
            config = CONTROLLER.ConfigState(directory)
            path = config.presets / "invalid.json"
            CONTROLLER.atomic_write_json(
                path,
                {
                    "version": 1,
                    "agent_type": "external",
                    "pane_name": "invalid",
                    "argv": ["agent-cli", "bad\x00argument"],
                },
            )
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.load_preset(config, "invalid")
            self.assertEqual(raised.exception.code, "invalid_preset")

    def test_preset_dry_run_does_not_create_the_config_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-dry-run-") as directory:
            root = Path(directory)
            runtime = CONTROLLER.RuntimeState(str(root / "runtime"))
            config = CONTROLLER.ConfigState(str(root / "config"))
            args = SimpleNamespace(
                socket=None,
                source="reviewer",
                name="sample",
                dry_run=True,
            )
            value = {
                "version": 1,
                "agent_type": "external",
                "pane_name": "reviewer",
                "argv": ["agent-cli"],
            }
            with mock.patch.object(CONTROLLER, "preset_from_pane", return_value=value):
                result = CONTROLLER.command_preset_save(args, runtime, config)
            self.assertEqual(result["stage"], "dry_run")
            self.assertFalse(config.root.exists())

    def test_partial_send_stages_are_preserved(self) -> None:
        class FakeClient:
            def __init__(
                self,
                fail_submit: bool = False,
                fail_capture: bool = False,
                timeout_write: bool = False,
                timeout_submit: bool = False,
            ) -> None:
                self.fail_submit = fail_submit
                self.fail_capture = fail_capture
                self.timeout_write = timeout_write
                self.timeout_submit = timeout_submit
                self.calls = 0

            def pane(self, _target: str) -> dict:
                return pane

            def server(self) -> dict:
                return {
                    "socket_path": pane["socket_path"],
                    "server_pid": pane["server_pid"],
                }

            def run(self, arguments, **_kwargs):
                if arguments[0] == "send-keys":
                    self.calls += 1
                    if self.calls == 1 and self.timeout_write:
                        raise CONTROLLER.WAError(
                            "tmux_timeout", "write timed out", stage="text_not_written"
                        )
                    if self.calls == 2 and self.timeout_submit:
                        raise CONTROLLER.WAError(
                            "tmux_timeout",
                            "submit timed out",
                            stage="text_written_not_submitted",
                        )
                    if self.calls == 2 and self.fail_submit:
                        raise CONTROLLER.WAError(
                            "tmux_command_failed",
                            "submit failed",
                            stage="text_written_not_submitted",
                        )
                return subprocess.CompletedProcess(arguments, 0, "", "")

            def capture(self, _pane_id: str, _lines: int = 80) -> str:
                if self.fail_capture:
                    raise CONTROLLER.WAError("tmux_command_failed", "capture failed")
                return "› "

        pane = {
            "kind": "pane",
            "socket_path": "/tmp/fake-tmux.sock",
            "server_pid": 123,
            "pane_id": "%1",
            "pane_pid": 456,
            "owned": False,
            "run_id": None,
            "dead": False,
        }
        with tempfile.TemporaryDirectory(prefix="with-agents-unit-") as directory:
            runtime = CONTROLLER.RuntimeState(directory)
            with mock.patch.dict(
                os.environ, {"WITH_AGENTS_CALLER_ID": "unit"}, clear=False
            ):
                CONTROLLER.mark_observed(runtime, pane)
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.send_core(
                        runtime,
                        FakeClient(fail_submit=True),
                        pane,
                        message="hello",
                        allow_foreign=True,
                    )
                self.assertEqual(raised.exception.stage, "text_written_not_submitted")
                CONTROLLER.mark_observed(runtime, pane)
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.send_core(
                        runtime,
                        FakeClient(fail_capture=True),
                        pane,
                        message="hello",
                        allow_foreign=True,
                    )
                self.assertEqual(raised.exception.code, "submitted_state_unknown")
                CONTROLLER.mark_observed(runtime, pane)
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.send_core(
                        runtime,
                        FakeClient(timeout_write=True),
                        pane,
                        message="hello",
                        allow_foreign=True,
                    )
                self.assertEqual(raised.exception.stage, "text_written_not_submitted")
                CONTROLLER.mark_observed(runtime, pane)
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.send_core(
                        runtime,
                        FakeClient(timeout_submit=True),
                        pane,
                        message="hello",
                        allow_foreign=True,
                    )
                self.assertEqual(raised.exception.stage, "submitted_state_unknown")
                CONTROLLER.mark_observed(runtime, pane)
                observation = CONTROLLER.observation_path(runtime, pane)

                class InterruptingDelay:
                    def __float__(self) -> float:
                        raise KeyboardInterrupt

                with (
                    mock.patch.object(
                        CONTROLLER,
                        "adapter_for_send",
                        return_value=(
                            "generic",
                            {
                                "multiline": False,
                                "delay": InterruptingDelay(),
                                "submit_key": "Enter",
                            },
                        ),
                    ),
                    self.assertRaises(CONTROLLER.WAError) as raised,
                ):
                    CONTROLLER.send_core(
                        runtime,
                        FakeClient(),
                        pane,
                        message="hello",
                        allow_foreign=True,
                    )
                self.assertEqual(raised.exception.code, "interrupted")
                self.assertEqual(raised.exception.stage, "text_written_not_submitted")
                self.assertFalse(observation.exists())

    def test_reply_interrupt_after_spooling_is_reported_as_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-reply-interrupt-") as root:
            runtime = CONTROLLER.RuntimeState(str(Path(root) / "runtime"))
            identifier = "wa-20260721T000000-000000000003"
            directory = CONTROLLER.request_dir(runtime, identifier)
            directory.mkdir(mode=0o700)
            CONTROLLER.atomic_write_json(
                directory / "request.json",
                {
                    "version": 1,
                    "request_id": identifier,
                    "created_at": CONTROLLER.iso_now(),
                    "created_epoch": time.time(),
                    "phase": "active",
                    "caller": {"kind": "external"},
                    "notify_mode": "pane",
                    "notify_armed": True,
                    "reply_ttl_seconds": None,
                },
                exclusive=True,
            )
            with mock.patch.object(
                CONTROLLER, "notify_caller", side_effect=KeyboardInterrupt
            ):
                result = CONTROLLER.command_reply(
                    SimpleNamespace(
                        request_id=identifier,
                        status="done",
                        message="complete",
                        file=None,
                    ),
                    runtime,
                    None,
                )
            self.assertEqual(result["stage"], "spooled")
            self.assertTrue(result["notification"]["spooled"])
            self.assertTrue(result["notification"]["injection_attempted"])
            self.assertEqual(
                result["notification"]["reason"],
                "notification_interrupted_state_unknown",
            )
            self.assertTrue((directory / "reply.json").is_file())
            self.assertEqual(
                CONTROLLER.safe_read_json(directory / "notification.json")["reason"],
                "notification_interrupted_state_unknown",
            )

    def test_state_fallback_gc_only_removes_old_terminal_requests(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-state-") as directory:
            environment = os.environ.copy()
            try:
                os.environ.pop("XDG_RUNTIME_DIR", None)
                os.environ.pop("WITH_AGENTS_RUNTIME_DIR", None)
                os.environ["XDG_STATE_HOME"] = directory
                runtime = CONTROLLER.RuntimeState()
                for identifier, terminal in (
                    ("wa-20200101T000000-000000000001", True),
                    ("wa-20200101T000000-000000000002", False),
                ):
                    request_directory = runtime.requests / identifier
                    request_directory.mkdir(mode=0o700)
                    CONTROLLER.atomic_write_json(
                        request_directory / "request.json",
                        {
                            "version": 1,
                            "request_id": identifier,
                            "created_epoch": 1,
                            "phase": "active",
                        },
                    )
                    if terminal:
                        CONTROLLER.atomic_write_json(
                            request_directory / "reply.json",
                            {"version": 1, "request_id": identifier},
                        )
                    old = time.time() - CONTROLLER.AUTO_GC_TERMINAL_SECONDS - 10
                    os.utime(request_directory, (old, old))
                CONTROLLER.RuntimeState()
                self.assertFalse(
                    (runtime.requests / "wa-20200101T000000-000000000001").exists()
                )
                self.assertTrue(
                    (runtime.requests / "wa-20200101T000000-000000000002").exists()
                )
            finally:
                os.environ.clear()
                os.environ.update(environment)

    def test_state_fallback_gc_uses_v2_terminal_event_and_aborted_epoch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-state-v2-") as directory:
            environment = os.environ.copy()
            try:
                os.environ.pop("XDG_RUNTIME_DIR", None)
                os.environ.pop("WITH_AGENTS_RUNTIME_DIR", None)
                os.environ["XDG_STATE_HOME"] = directory
                runtime = CONTROLLER.RuntimeState()
                old = time.time() - CONTROLLER.AUTO_GC_TERMINAL_SECONDS - 10

                def make_request(
                    identifier: str, *, phase: str, status: str | None = None
                ) -> Path:
                    request_directory = runtime.requests / identifier
                    for child in (
                        request_directory,
                        request_directory / "events",
                        request_directory / "notifications",
                        request_directory / "result",
                    ):
                        child.mkdir(mode=0o700, parents=True, exist_ok=True)
                    record = {
                        "version": 2,
                        "request_id": identifier,
                        "created_at": CONTROLLER.iso_now(),
                        "created_epoch": old,
                        "phase": phase,
                        "child": {},
                        "caller": {"kind": "external"},
                        "notify_mode": "spool",
                        "notify_armed": False,
                        "reply_ttl_seconds": None,
                        "result_dir": str((request_directory / "result").resolve()),
                        "limits": CONTROLLER.v2_request_limits(),
                    }
                    if phase == "aborted":
                        record["dispatch_finished_epoch"] = old
                    else:
                        record["dispatched_epoch"] = old
                    CONTROLLER.atomic_write_json(
                        request_directory / "request.json", record, exclusive=True
                    )
                    if status is not None:
                        CONTROLLER.atomic_write_json(
                            request_directory / "events" / "000001.json",
                            {
                                "version": 1,
                                "request_id": identifier,
                                "seq": 1,
                                "created_at": CONTROLLER.iso_now(),
                                "created_epoch": old,
                                "status": status,
                                "terminal": status == "done",
                                "message": None,
                                "result": None,
                            },
                            exclusive=True,
                        )
                    return request_directory

                terminal = make_request(
                    "wa-20200101T000000-000000000201",
                    phase="active",
                    status="done",
                )
                pending = make_request(
                    "wa-20200101T000000-000000000202",
                    phase="active",
                    status="progress",
                )
                aborted = make_request(
                    "wa-20200101T000000-000000000203", phase="aborted"
                )

                CONTROLLER.RuntimeState()

                self.assertFalse(terminal.exists())
                self.assertTrue(pending.exists())
                self.assertFalse(aborted.exists())
            finally:
                os.environ.clear()
                os.environ.update(environment)

    def test_read_does_not_observe_a_screen_across_identity_change(self) -> None:
        initial = {
            "kind": "pane",
            "socket_path": "/tmp/fake.sock",
            "server_pid": 10,
            "pane_id": "%1",
            "pane_pid": 20,
            "owned": False,
            "run_id": None,
        }
        replaced = {**initial, "pane_pid": 21}

        class ReplacedDuringCapture:
            def __init__(self, _socket=None) -> None:
                pass

            def resolve(self, _target: str) -> dict:
                return initial

            def capture(self, _pane_id: str, _lines: int) -> str:
                return "old screen"

            def pane(self, _pane_id: str) -> dict:
                return replaced

        with tempfile.TemporaryDirectory(prefix="with-agents-read-race-") as directory:
            runtime = CONTROLLER.RuntimeState(directory)
            args = SimpleNamespace(socket=None, target="%1", lines=20)
            with mock.patch.object(CONTROLLER, "TmuxClient", ReplacedDuringCapture):
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.command_read(args, runtime, mock.Mock())
            self.assertEqual(raised.exception.code, "target_identity_changed")
            self.assertEqual(list(runtime.observations.iterdir()), [])

    def test_create_only_observes_after_initial_screen_and_state_succeed(self) -> None:
        pane = {
            "kind": "pane",
            "socket_path": "/tmp/fake.sock",
            "server_pid": 10,
            "pane_id": "%1",
            "pane_pid": 20,
            "owned": True,
            "run_id": "run-created",
        }

        class CaptureClient:
            def __init__(self, _socket=None) -> None:
                pass

            def capture(self, _pane_id: str, _lines: int) -> str:
                return "shell screen"

        with tempfile.TemporaryDirectory(prefix="with-agents-create-observe-") as root:
            runtime = CONTROLLER.RuntimeState(str(Path(root) / "runtime"))
            args = SimpleNamespace(
                socket=None,
                cwd=root,
                name="shell",
                session=None,
                split=None,
            )
            with (
                mock.patch.object(CONTROLLER, "TmuxClient", CaptureClient),
                mock.patch.object(
                    CONTROLLER,
                    "create_owned_shell",
                    return_value=(pane, Path(root) / "record.json"),
                ),
                mock.patch.object(
                    CONTROLLER,
                    "mark_observed",
                    side_effect=CONTROLLER.WAError("state_failed", "injected"),
                ),
                self.assertRaises(CONTROLLER.WAError) as raised,
            ):
                CONTROLLER.command_create(args, runtime, None)
            self.assertEqual(raised.exception.stage, "create_state_unknown")
            self.assertEqual(raised.exception.target["pane_id"], "%1")
            self.assertEqual(list(runtime.observations.iterdir()), [])

    def test_version_has_no_runtime_or_config_side_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="with-agents-version-") as directory:
            root = Path(directory)
            runtime = root / "runtime"
            config = root / "config"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "--json",
                    "--runtime-dir",
                    str(runtime),
                    "--config-dir",
                    str(config),
                    "version",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(runtime.exists())
            self.assertFalse(config.exists())


class IntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = Harness()

    def tearDown(self) -> None:
        self.harness.close()

    def _v2_request(
        self,
        identifier: str,
        *,
        caller: dict | None = None,
        ttl: float | None = None,
        phase: str = "active",
        created_epoch: float | None = None,
    ) -> Path:
        """Create a protocol-v2 ticket fixture without dispatching a pane task."""
        created_epoch = time.time() if created_epoch is None else created_epoch
        directory = self.harness.runtime / "requests" / identifier
        for child in (
            directory,
            directory / "events",
            directory / "notifications",
            directory / "result",
        ):
            child.mkdir(mode=0o700, parents=True, exist_ok=True)
        record = {
            "version": 2,
            "request_id": identifier,
            "created_at": CONTROLLER.iso_now(),
            "created_epoch": created_epoch,
            "phase": phase,
            "child": {
                "kind": "pane",
                "socket_path": "/tmp/child.sock",
                "server_pid": 1,
                "pane_id": "%9",
                "pane_pid": 9,
                "run_id": "run-child",
            },
            "caller": caller or {"kind": "external"},
            "notify_mode": "spool",
            "notify_armed": False,
            "reply_ttl_seconds": ttl,
            "result_dir": str((directory / "result").resolve()),
            "limits": {
                "message_bytes": 1024,
                "nonterminal_events": 64,
                "terminal_events": 1,
                "result_bytes_per_event": 16 * 1024 * 1024,
                "result_bytes_per_request": 64 * 1024 * 1024,
                "files_per_event": 1,
            },
        }
        CONTROLLER.atomic_write_json(directory / "request.json", record, exclusive=True)
        return directory

    @staticmethod
    def _event_fixture(
        directory: Path,
        seq: int,
        status: str,
        *,
        message: str = "fixture",
        created_epoch: float | None = None,
        result: dict | None = None,
    ) -> None:
        terminal = status in {"done", "blocked", "failed"}
        CONTROLLER.atomic_write_json(
            directory / "events" / f"{seq:06d}.json",
            {
                "version": 1,
                "request_id": directory.name,
                "seq": seq,
                "created_at": CONTROLLER.iso_now(),
                "created_epoch": (
                    time.time() if created_epoch is None else created_epoch
                ),
                "status": status,
                "terminal": terminal,
                "message": message,
                "result": result,
            },
            exclusive=True,
        )

    def _write_agent_config(self, agents: dict[str, dict[str, object]]) -> Path:
        config = self.harness.config / "config.json"
        config.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        CONTROLLER.atomic_write_json(config, {"version": 1, "agents": agents})
        return config

    def test_launch_send_read_wait_and_close(self) -> None:
        argv_record = self.harness.root / "argv.json"
        injection_marker = self.harness.root / "must-not-exist"
        literal_substitution = f"$(touch {injection_marker})"
        launched, log = self.harness.launch_mock(
            "mock",
            extra=[
                "--record-argv",
                str(argv_record),
                "two words",
                "--literal=$value",
                literal_substitution,
            ],
        )
        self.assertTrue(launched["ok"])
        self.assertIn("MOCK_READY", launched["screen"]["tail"])
        self.assertEqual(
            launched["target"]["launch"]["argv"][-3:],
            ["two words", "--literal=$value", literal_substitution],
        )
        recorded = json.loads(argv_record.read_text(encoding="utf-8"))
        self.assertIn("two words", recorded)
        self.assertIn("--literal=$value", recorded)
        self.assertIn(literal_substitution, recorded)
        self.assertFalse(injection_marker.exists())

        sent, _ = self.harness.run("send", "mock", "--", "hello world")
        self.assertEqual(sent["stage"], "submitted")
        self.assertEqual(sent["target"]["submission"]["tui_acceptance"], "unverified")
        self.assertEqual(self.harness.read_log(log), ["hello world"])

        failed, _ = self.harness.run("send", "mock", "--", "blind", ok=False)
        self.assertEqual(failed["error"]["code"], "observation_required")
        read, _ = self.harness.run("read", "mock", "--lines", "30")
        self.assertIn("RECEIVED:hello world", read["screen"]["tail"])
        waited, _ = self.harness.run(
            "wait", "mock", "--timeout", "0.05", "--interval", "0.01"
        )
        self.assertIn(waited["stage"], ("unchanged", "changed"))
        closed, _ = self.harness.run("close", "mock")
        self.assertEqual(closed["stage"], "closed")

    def test_key_is_one_observed_atomic_input_event(self) -> None:
        _, log = self.harness.launch_mock("target")
        sent, _ = self.harness.run("key", "target", "--", "x", "Enter")
        self.assertEqual(sent["stage"], "sent")
        self.assertEqual(self.harness.read_log(log), ["x"])
        rejected, _ = self.harness.run("key", "target", "Enter", ok=False)
        self.assertEqual(rejected["error"]["code"], "observation_required")

    def test_observation_is_bound_to_caller(self) -> None:
        self.harness.launch_mock("mock")
        self.harness.run("read", "mock", caller_id="caller-a")
        failed, _ = self.harness.run(
            "send", "mock", "--", "from b", ok=False, caller_id="caller-b"
        )
        self.assertEqual(failed["error"]["code"], "observation_required")
        sent, _ = self.harness.run("send", "mock", "--", "from a", caller_id="caller-a")
        self.assertTrue(sent["ok"])

    def test_foreign_write_requires_read_and_explicit_authorization(self) -> None:
        self.harness.launch_mock("owned")
        command = shlex.join([sys.executable, "-u", str(FIXTURE)])
        pane_id = self.harness.tmux(
            "new-window",
            "-d",
            "-P",
            "-F",
            "#{pane_id}",
            "-t",
            "with-agents:",
            command,
        ).stdout.strip()
        self.harness.run("read", pane_id)
        denied, _ = self.harness.run("send", pane_id, "--", "hello", ok=False)
        self.assertEqual(denied["error"]["code"], "foreign_write_denied")
        self.harness.run("read", pane_id)
        accepted, _ = self.harness.run(
            "send", pane_id, "--allow-foreign", "--", "hello"
        )
        self.assertTrue(accepted["ok"])

    def test_multiline_unknown_adapter_fails_before_writing(self) -> None:
        self.harness.launch_mock("mock")
        failed, _ = self.harness.run("send", "mock", "--", "one\ntwo", ok=False)
        self.assertEqual(failed["error"]["code"], "multiline_not_safe")
        self.assertEqual(failed["stage"], "text_not_written")

    def test_failed_launch_can_restart_in_same_pane(self) -> None:
        failed, _ = self.harness.run(
            "launch",
            "--name",
            "broken",
            "--",
            "/definitely/not/a/with-agents-executable",
            ok=False,
        )
        self.assertEqual(failed["error"]["code"], "executable_not_found")
        pane_id = failed["target"]["pane_id"]
        waited, _ = self.harness.run("wait", "broken", "--timeout", "0")
        self.assertEqual(waited["stage"], "process_exit")
        dead_send, _ = self.harness.run(
            "send", "broken", "--", "must not be written", ok=False
        )
        self.assertEqual(dead_send["error"]["code"], "target_process_exited")
        restarted, _ = self.harness.run(
            "restart",
            "broken",
            "--",
            sys.executable,
            "-u",
            str(FIXTURE),
        )
        self.assertEqual(restarted["target"]["pane_id"], pane_id)
        self.assertNotEqual(restarted["target"]["run_id"], failed["target"]["run_id"])

    def test_preset_create_update_dry_run_remove_and_secret_guard(self) -> None:
        self.harness.launch_mock("source")
        saved, _ = self.harness.run("preset", "save", "sample", "--from", "source")
        preset_path = Path(saved["target"]["path"])
        self.assertTrue(preset_path.is_file())
        self.assertEqual(
            saved["target"]["digest"],
            hashlib.sha256(preset_path.read_bytes()).hexdigest(),
        )
        shown, _ = self.harness.run("preset", "show", "sample")
        self.assertEqual(shown["target"]["argv"], saved["target"]["argv"])
        listed, _ = self.harness.run("preset", "list")
        self.assertEqual(
            [item["name"] for item in listed["target"]["items"]], ["sample"]
        )
        duplicate, _ = self.harness.run(
            "preset", "save", "sample", "--from", "source", ok=False
        )
        self.assertEqual(duplicate["error"]["code"], "preset_exists")
        dry, _ = self.harness.run(
            "preset", "save", "dry", "--from", "source", "--dry-run"
        )
        self.assertEqual(dry["stage"], "dry_run")
        self.assertFalse(Path(dry["target"]["path"]).exists())
        missing_replace, _ = self.harness.run(
            "preset", "update", "sample", "--from", "source", ok=False
        )
        self.assertEqual(missing_replace["error"]["code"], "replace_required")
        updated, _ = self.harness.run(
            "preset", "update", "sample", "--from", "source", "--replace"
        )
        self.assertEqual(updated["stage"], "updated")
        self.harness.run("close", "source")
        shortcut = SKILL_ROOT / "scripts" / "launch-agent"
        completed = subprocess.run(
            [
                str(shortcut),
                "--json",
                "--socket",
                str(self.harness.socket),
                "--runtime-dir",
                str(self.harness.runtime),
                "--config-dir",
                str(self.harness.config),
                "--preset",
                "sample",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.harness.environment,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        launched = json.loads(completed.stdout)
        Harness.assert_envelope(launched)
        self.assertEqual(launched["target"]["launch"]["preset"], "sample")
        self.assertEqual(launched["target"]["name"], "source")
        self.harness.run("close", "source")
        removed, _ = self.harness.run("preset", "remove", "sample")
        self.assertEqual(removed["stage"], "removed")
        self.assertFalse(preset_path.exists())

        self.harness.launch_mock("secret", extra=["--api-key", "not-persisted"])
        rejected, _ = self.harness.run(
            "preset", "save", "secret", "--from", "secret", ok=False
        )
        self.assertEqual(rejected["error"]["code"], "preset_secret_suspected")

    def test_preset_suffix_uses_current_prefix_and_allows_ambiguous_names(self) -> None:
        pi = self.harness.make_agent_executable("pi")
        self.harness.launch_mock("pi-default", executable=pi)
        saved, _ = self.harness.run(
            "preset", "save", "deepseek-flash", "--from", "pi-default"
        )
        self.assertEqual(saved["target"]["agent_type"], "pi")
        digest = saved["target"]["digest"]
        self.harness.run("close", "pi-default")

        first, _ = self.harness.run(
            "launch",
            "--preset",
            "deepseek-flash",
            "--name-suffix",
            "worker",
        )
        second, _ = self.harness.run(
            "launch",
            "--preset",
            "deepseek-flash",
            "--name-suffix",
            "worker",
        )
        self.assertEqual(first["target"]["name"], "pi-worker")
        self.assertEqual(second["target"]["name"], "pi-worker")
        ambiguous, _ = self.harness.run("read", "pi-worker", ok=False)
        self.assertEqual(ambiguous["error"]["code"], "target_ambiguous")
        self.harness.run("close", first["target"]["pane_id"])
        self.harness.run("close", second["target"]["pane_id"])

        CONTROLLER.atomic_write_json(
            self.harness.config / "config.json",
            {"version": 1, "agents": {"pi": {"pane_prefix": "dsp"}}},
        )
        shown, _ = self.harness.run("preset", "show", "deepseek-flash")
        self.assertEqual(shown["target"]["digest"], digest)
        renamed, _ = self.harness.run(
            "launch",
            "--preset",
            "deepseek-flash",
            "--name-suffix",
            "trans",
        )
        self.assertEqual(renamed["target"]["name"], "dsp-trans")
        self.harness.run("close", renamed["target"]["pane_id"])

        full, _ = self.harness.run(
            "launch", "--preset", "deepseek-flash", "--name", "one-off-review"
        )
        self.assertEqual(full["target"]["name"], "one-off-review")
        self.harness.run("close", full["target"]["pane_id"])
        default, _ = self.harness.run("launch", "--preset", "deepseek-flash")
        self.assertEqual(default["target"]["name"], "pi-default")

    def test_invalid_agent_config_only_blocks_consuming_commands(self) -> None:
        pi = self.harness.make_agent_executable("pi")
        self.harness.launch_mock("source", executable=pi)
        self.harness.run("preset", "save", "sample", "--from", "source")
        self.harness.run("close", "source")
        _, log = self.harness.launch_mock("observer")
        config_path = self.harness.config / "config.json"
        config_path.write_text("{invalid json", encoding="utf-8")

        version, _ = self.harness.run("version")
        self.assertEqual(version["target"]["version"], CONTROLLER.VERSION)
        listed, _ = self.harness.run("list")
        self.assertIn("observer", [item["name"] for item in listed["target"]["items"]])
        self.harness.run("read", "observer")
        self.harness.run("send", "observer", "--", "config independent")
        self.assertEqual(self.harness.read_log(log), ["config independent"])

        direct, _ = self.harness.launch_mock("direct-full-name")
        self.harness.run("close", direct["target"]["pane_id"])
        default, _ = self.harness.run("launch", "--preset", "sample")
        self.assertEqual(default["target"]["name"], "source")
        self.harness.run("close", default["target"]["pane_id"])
        full, _ = self.harness.run(
            "launch", "--preset", "sample", "--name", "preset-full-name"
        )
        self.harness.run("close", full["target"]["pane_id"])

        suffix, _ = self.harness.run(
            "launch", "--preset", "sample", "--name-suffix", "worker", ok=False
        )
        self.assertEqual(suffix["error"]["code"], "invalid_agent_config")
        save, _ = self.harness.run(
            "preset", "save", "blocked", "--from", "observer", ok=False
        )
        self.assertEqual(save["error"]["code"], "invalid_agent_config")
        doctor, _ = self.harness.run("doctor", ok=False)
        self.assertEqual(doctor["error"]["code"], "doctor_issues")
        self.assertEqual(
            doctor["target"]["checks"]["agent_config"]["error"]["code"],
            "invalid_agent_config",
        )

    def test_create_list_doctor_version_and_launch_agent_shortcut(self) -> None:
        created, _ = self.harness.run("create", "--name", "shell")
        self.assertEqual(created["event"], "create")
        listed, _ = self.harness.run("list")
        self.assertIn("shell", [item["name"] for item in listed["target"]["items"]])
        doctor, _ = self.harness.run("doctor")
        self.assertEqual(doctor["stage"], "ok")
        notification = doctor["target"]["checks"]["notification"]
        self.assertFalse(notification["callback_version_gate"])
        self.assertEqual(
            notification["adapters"]["codex"]["forward_tested_major_minor"],
            [0, 145],
        )
        self.assertEqual(notification["generic_submit_key"], "Enter")
        version, _ = self.harness.run("version")
        self.assertEqual(version["target"]["version"], CONTROLLER.VERSION)

        shortcut = SKILL_ROOT / "scripts" / "launch-agent"
        completed = subprocess.run(
            [
                str(shortcut),
                "--json",
                "--socket",
                str(self.harness.socket),
                "--runtime-dir",
                str(self.harness.runtime),
                "--config-dir",
                str(self.harness.config),
                "--name",
                "shortcut",
                "--",
                sys.executable,
                "-u",
                str(FIXTURE),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self.harness.environment,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        Harness.assert_envelope(payload)
        self.assertEqual(payload["event"], "launch")

    def test_doctor_accepts_an_absent_server_that_launch_can_create(self) -> None:
        doctor, _ = self.harness.run("doctor")
        self.assertEqual(doctor["stage"], "ok")
        self.assertFalse(doctor["target"]["checks"]["tmux"]["server_running"])

    def test_slow_launch_reports_unverified_readiness_then_waits(self) -> None:
        launched, _ = self.harness.launch_mock("slow", extra=["--startup-delay", "0.6"])
        self.assertIsNone(launched["target"]["readiness"]["ready_for_send"])
        waited, _ = self.harness.run(
            "wait", "slow", "--timeout", "1", "--interval", "0.05"
        )
        self.assertIn("MOCK_READY", waited["screen"]["tail"])

    def test_known_codex_adapter_keeps_multiline_as_one_input(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        _, log = self.harness.launch_mock("caller", executable=codex)
        sent, _ = self.harness.run("send", "caller", "--", "first\nsecond")
        self.assertTrue(sent["ok"])
        self.assertEqual(self.harness.read_log(log), ["first\nsecond"])
        buffers = self.harness.tmux(
            "list-buffers", "-F", "#{buffer_name}", check=False
        ).stdout
        self.assertNotIn("with-agents-", buffers)

    def test_target_respawn_invalidates_observation(self) -> None:
        launched, _ = self.harness.launch_mock("target")
        pane_id = launched["target"]["pane_id"]
        self.harness.run("read", "target")
        command = shlex.join([sys.executable, "-u", str(FIXTURE)])
        self.harness.tmux("respawn-pane", "-k", "-t", pane_id, command)
        failed, _ = self.harness.run("send", "target", "--", "stale", ok=False)
        self.assertEqual(failed["error"]["code"], "observation_expired")

    def test_concurrent_send_serializes_and_consumes_one_observation(self) -> None:
        _, log = self.harness.launch_mock("target")
        commands = [
            self.harness.command("send", "target", "--", f"message {index}")
            for index in range(2)
        ]
        processes = [
            subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.harness.environment,
            )
            for command in commands
        ]
        results = [
            process.communicate(timeout=30) + (process.returncode,)
            for process in processes
        ]
        self.assertEqual(sorted(result[2] for result in results), [0, 1])
        self.assertEqual(len(self.harness.read_log(log)), 1)

    def test_send_and_key_share_the_same_input_lock(self) -> None:
        _, log = self.harness.launch_mock("target")
        commands = [
            self.harness.command("send", "target", "--", "whole message"),
            self.harness.command("key", "target", "x", "Enter"),
        ]
        processes = [
            subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.harness.environment,
            )
            for command in commands
        ]
        results = [
            process.communicate(timeout=30) + (process.returncode,)
            for process in processes
        ]
        self.assertEqual(sorted(result[2] for result in results), [0, 1])
        self.assertIn(self.harness.read_log(log), (["whole message"], ["x"]))

    def test_send_and_close_cannot_cross_the_lifecycle_boundary(self) -> None:
        launched, log = self.harness.launch_mock("target")
        commands = [
            self.harness.command("send", "target", "--", "before close"),
            self.harness.command("close", "target"),
        ]
        processes = [
            subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.harness.environment,
            )
            for command in commands
        ]
        results = [
            process.communicate(timeout=30) + (process.returncode,)
            for process in processes
        ]
        self.assertEqual(sorted(result[2] for result in results), [0, 1])
        self.assertIn(self.harness.read_log(log), ([], ["before close"]))
        pane_id = launched["target"]["pane_id"]
        still_present = (
            self.harness.tmux(
                "display-message", "-p", "-t", pane_id, "#{pane_id}", check=False
            ).returncode
            == 0
        )
        if still_present:
            self.harness.run("read", pane_id)
            self.harness.run("close", pane_id)

    def test_request_and_restart_serialize_without_splitting_the_task(self) -> None:
        _, log = self.harness.launch_mock("target")
        restart_argv = [
            sys.executable,
            "-u",
            str(FIXTURE),
            "--log",
            str(log),
            "--mode",
            "idle",
        ]
        commands = [
            self.harness.command("request", "target", "--", "review atomically"),
            self.harness.command("restart", "target", "--", *restart_argv),
        ]
        processes = [
            subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.harness.environment,
            )
            for command in commands
        ]
        results = [
            process.communicate(timeout=30) + (process.returncode,)
            for process in processes
        ]
        self.assertEqual(results[0][2], 0, results[0][1])
        logged = self.harness.read_log(log)
        self.assertEqual(len(logged), 1)
        self.assertIn("review atomically", logged[0])

    def test_reply_notification_and_send_do_not_interleave(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        _, caller_log = self.harness.launch_mock("caller", executable=codex)
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        identifier = requested["request"]["request_id"]
        commands = [
            self.harness.command("send", "caller", "--", "ordinary message"),
            self.harness.command(
                "reply", identifier, "--status", "done", "--message", "doorbell"
            ),
        ]
        processes = [
            subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.harness.environment,
            )
            for command in commands
        ]
        results = [
            process.communicate(timeout=30) + (process.returncode,)
            for process in processes
        ]
        self.assertEqual([result[2] for result in results], [0, 0])
        logged = self.harness.read_log(caller_log)
        self.assertEqual(len(logged), 2)
        self.assertIn("ordinary message", logged)
        self.assertEqual(sum("doorbell" in message for message in logged), 1)

    def test_request_reply_file_inbox_terminal_and_gc(self) -> None:
        self.harness.launch_mock("child")
        requested, _ = self.harness.run("request", "child", "--", "review this")
        identifier = requested["request"]["request_id"]
        self.assertFalse(requested["request"]["notify_armed"])
        result_file = self.harness.root / "review.md"
        result_file.write_text("long review", encoding="utf-8")
        replied, _ = self.harness.run(
            "reply",
            identifier,
            "--status",
            "done",
            "--message",
            "review complete",
            "--file",
            str(result_file),
        )
        self.assertTrue(replied["notification"]["spooled"])
        self.assertEqual(replied["notification"]["reason"], "spool_only")
        managed = replied["request"]["result"]
        self.assertEqual(managed["sha256"], hashlib.sha256(b"long review").hexdigest())
        self.assertTrue(Path(managed["path"]).is_file())
        duplicate, _ = self.harness.run(
            "reply", identifier, "--status", "done", ok=False
        )
        self.assertEqual(duplicate["error"]["code"], "reply_stream_terminated")
        inbox, _ = self.harness.run("inbox", identifier)
        self.assertEqual(inbox["request"]["events"][0]["message"], "review complete")
        self.harness.run("gc")
        missing, _ = self.harness.run("inbox", identifier, ok=False)
        self.assertEqual(missing["error"]["code"], "reply_ticket_invalid")

    def test_new_requests_are_v2_and_v1_fixture_keeps_legacy_reply(self) -> None:
        self.harness.launch_mock("child")
        requested, _ = self.harness.run("request", "child", "--", "v2 task")
        identifier = requested["request"]["request_id"]
        record = json.loads(
            (self.harness.runtime / "requests" / identifier / "request.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(record["version"], 2)
        self.assertEqual(record["limits"]["nonterminal_events"], 64)
        self.assertEqual(record["limits"]["terminal_events"], 1)

        legacy_id = "wa-20260722T000000-000000000101"
        legacy = self.harness.runtime / "requests" / legacy_id
        legacy.mkdir(mode=0o700, parents=True)
        CONTROLLER.atomic_write_json(
            legacy / "request.json",
            {
                "version": 1,
                "request_id": legacy_id,
                "created_at": CONTROLLER.iso_now(),
                "created_epoch": time.time(),
                "phase": "active",
                "caller": {"kind": "external"},
                "notify_mode": "spool",
                "notify_armed": False,
                "reply_ttl_seconds": None,
            },
            exclusive=True,
        )
        unsupported, _ = self.harness.run(
            "reply", legacy_id, "--status", "progress", ok=False
        )
        self.assertEqual(unsupported["error"]["code"], "reply_ticket_invalid")
        replied, _ = self.harness.run(
            "reply", legacy_id, "--status", "question", "--message", "legacy"
        )
        self.assertEqual(replied["stage"], "spooled")
        duplicate, _ = self.harness.run(
            "reply", legacy_id, "--status", "done", ok=False
        )
        self.assertEqual(duplicate["error"]["code"], "already_replied")
        inbox, _ = self.harness.run("inbox", legacy_id)
        self.assertIn("items", inbox["request"])
        self.assertEqual(inbox["request"]["items"][0]["message"], "legacy")

    def test_v2_progress_and_question_append_until_terminal(self) -> None:
        identifier = "wa-20260722T000000-000000000102"
        directory = self._v2_request(identifier)
        for status, message in (
            ("progress", "started"),
            ("question", "need input"),
            ("done", "complete"),
        ):
            result, _ = self.harness.run(
                "reply", identifier, "--status", status, "--message", message
            )
            self.assertTrue(result["ok"])
        events = sorted((directory / "events").glob("*.json"))
        self.assertEqual(
            [path.name for path in events],
            ["000001.json", "000002.json", "000003.json"],
        )
        values = [CONTROLLER.safe_read_json(path) for path in events]
        self.assertEqual(
            [value["status"] for value in values],
            ["progress", "question", "done"],
        )
        self.assertEqual([value["terminal"] for value in values], [False, False, True])
        rejected, _ = self.harness.run(
            "reply", identifier, "--status", "failed", ok=False
        )
        self.assertEqual(rejected["error"]["code"], "reply_stream_terminated")
        inbox, _ = self.harness.run("inbox", identifier)
        self.assertEqual(
            [event["status"] for event in inbox["request"]["events"]],
            ["progress", "question", "done"],
        )

    def test_v2_dispatch_residual_phases_can_reply_but_aborted_cannot(self) -> None:
        for index, phase in enumerate(("dispatching", "dispatch_unknown"), start=114):
            identifier = f"wa-20260722T000000-000000000{index}"
            self._v2_request(identifier, phase=phase)
            replied, _ = self.harness.run(
                "reply", identifier, "--status", "done", "--message", phase
            )
            self.assertTrue(replied["ok"])
        aborted_id = "wa-20260722T000000-000000000116"
        self._v2_request(aborted_id, phase="aborted")
        rejected, _ = self.harness.run(
            "reply", aborted_id, "--status", "done", ok=False
        )
        self.assertEqual(rejected["error"]["code"], "reply_ticket_invalid")

    def test_v2_concurrent_replies_allocate_contiguous_seq_once(self) -> None:
        identifier = "wa-20260722T000000-000000000103"
        directory = self._v2_request(identifier)
        commands = [
            self.harness.command(
                "reply",
                identifier,
                "--status",
                "progress",
                "--message",
                f"progress {index}",
            )
            for index in range(2)
        ]
        processes = [
            subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.harness.environment,
            )
            for command in commands
        ]
        results = [
            process.communicate(timeout=30) + (process.returncode,)
            for process in processes
        ]
        self.assertEqual([result[2] for result in results], [0, 0])
        events = sorted((directory / "events").glob("*.json"))
        self.assertEqual([path.name for path in events], ["000001.json", "000002.json"])
        self.assertEqual(
            [CONTROLLER.safe_read_json(path)["seq"] for path in events], [1, 2]
        )

    def test_v2_event_is_readable_while_notification_is_still_blocked(self) -> None:
        identifier = "wa-20260722T000000-000000000118"
        self._v2_request(identifier)
        runtime = CONTROLLER.RuntimeState(str(self.harness.runtime))
        notification_entered = threading.Event()
        release_notification = threading.Event()
        inbox_finished = threading.Event()
        outcomes: dict[str, object] = {}

        def blocked_notification(*_arguments: object) -> dict:
            notification_entered.set()
            if not release_notification.wait(5):
                raise AssertionError("notification test was not released")
            return CONTROLLER.event_notification_result(identifier, 1, "spool_only")

        def reply_worker() -> None:
            try:
                outcomes["reply"] = CONTROLLER.command_reply(
                    SimpleNamespace(
                        request_id=identifier,
                        status="progress",
                        message="published",
                        file=None,
                    ),
                    runtime,
                    None,
                )
            except BaseException as exc:
                outcomes["reply_error"] = exc

        def inbox_worker() -> None:
            try:
                outcomes["inbox"] = CONTROLLER.command_inbox(
                    SimpleNamespace(request_id=identifier), runtime, None
                )
            except BaseException as exc:
                outcomes["inbox_error"] = exc
            finally:
                inbox_finished.set()

        reply_thread = threading.Thread(target=reply_worker)
        inbox_thread = threading.Thread(target=inbox_worker)
        with mock.patch.object(
            CONTROLLER, "notify_event_caller", side_effect=blocked_notification
        ):
            reply_thread.start()
            try:
                self.assertTrue(notification_entered.wait(5))
                inbox_thread.start()
                self.assertTrue(inbox_finished.wait(2))
            finally:
                release_notification.set()
                reply_thread.join(5)
                if inbox_thread.ident is not None:
                    inbox_thread.join(5)

        self.assertFalse(reply_thread.is_alive())
        self.assertFalse(inbox_thread.is_alive())
        self.assertNotIn("reply_error", outcomes)
        self.assertNotIn("inbox_error", outcomes)
        inbox = outcomes["inbox"]
        if not isinstance(inbox, dict):
            self.fail("inbox worker must return an envelope")
        self.assertEqual(inbox["request"]["count"], 1)
        self.assertEqual(inbox["request"]["events"][0]["status"], "progress")
        self.assertEqual(
            inbox["request"]["events"][0]["notification"]["state"], "missing"
        )

    def test_v2_event_write_failure_cleans_result_and_reuses_sequence(self) -> None:
        identifier = "wa-20260722T000000-000000000120"
        directory = self._v2_request(identifier)
        runtime = CONTROLLER.RuntimeState(str(self.harness.runtime))
        source = self.harness.root / "retry-result.txt"
        source.write_text("retry", encoding="utf-8")
        real_atomic_write = CONTROLLER.atomic_write_json

        def fail_event_write(path: Path, value: dict, *, exclusive: bool = False):
            if path.parent.name == "events":
                raise CONTROLLER.WAError("event_write_failed", "fixture failure")
            return real_atomic_write(path, value, exclusive=exclusive)

        with mock.patch.object(
            CONTROLLER, "atomic_write_json", side_effect=fail_event_write
        ):
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.command_reply(
                    SimpleNamespace(
                        request_id=identifier,
                        status="progress",
                        message="first attempt",
                        file=str(source),
                    ),
                    runtime,
                    None,
                )
        self.assertEqual(raised.exception.code, "event_write_failed")
        self.assertEqual(list((directory / "events").iterdir()), [])
        self.assertEqual(list((directory / "result").iterdir()), [])

        replied = CONTROLLER.command_reply(
            SimpleNamespace(
                request_id=identifier,
                status="done",
                message="retry",
                file=str(source),
            ),
            runtime,
            None,
        )
        self.assertEqual(replied["request"]["event"]["seq"], 1)
        self.assertTrue((directory / "events" / "000001.json").is_file())
        self.assertTrue((directory / "result" / "000001" / source.name).is_file())

    def test_v2_interrupt_after_event_publication_preserves_terminal_outcome(
        self,
    ) -> None:
        identifier = "wa-20260722T000000-000000000121"
        directory = self._v2_request(identifier)
        runtime = CONTROLLER.RuntimeState(str(self.harness.runtime))
        real_atomic_write = CONTROLLER.atomic_write_json

        def publish_then_interrupt(
            path: Path, value: dict, *, exclusive: bool = False
        ) -> None:
            real_atomic_write(path, value, exclusive=exclusive)
            if path.parent.name == "events":
                raise KeyboardInterrupt

        with (
            mock.patch.object(
                CONTROLLER, "atomic_write_json", side_effect=publish_then_interrupt
            ),
            mock.patch.object(CONTROLLER, "notify_event_caller") as notify,
        ):
            replied = CONTROLLER.command_reply(
                SimpleNamespace(
                    request_id=identifier,
                    status="done",
                    message="published before interrupt",
                    file=None,
                ),
                runtime,
                None,
            )

        notify.assert_not_called()
        self.assertEqual(replied["stage"], "outcome_persisted")
        self.assertTrue((directory / "events" / "000001.json").is_file())
        self.assertEqual(
            replied["notification"]["reason"],
            "notification_interrupted_before_attempt",
        )
        notification = CONTROLLER.safe_read_json(
            directory / "notifications" / "000001.json"
        )
        self.assertEqual(
            notification["reason"], "notification_interrupted_before_attempt"
        )

    def test_v2_nonterminal_budget_reserves_one_terminal_event(self) -> None:
        identifier = "wa-20260722T000000-000000000104"
        directory = self._v2_request(identifier)
        for seq in range(1, 65):
            self._event_fixture(directory, seq, "progress", message=f"fixture {seq}")
        rejected, _ = self.harness.run(
            "reply", identifier, "--status", "progress", ok=False
        )
        self.assertEqual(rejected["error"]["code"], "reply_event_limit")
        result_file = self.harness.root / "terminal-result.txt"
        result_file.write_text("terminal", encoding="utf-8")
        rejected, _ = self.harness.run(
            "reply",
            identifier,
            "--status",
            "done",
            "--file",
            str(result_file),
            ok=False,
        )
        self.assertEqual(rejected["error"]["code"], "reply_event_limit")
        accepted, _ = self.harness.run(
            "reply", identifier, "--status", "done", "--message", "terminal"
        )
        self.assertTrue(accepted["ok"])
        self.assertTrue((directory / "events" / "000065.json").is_file())

    def test_v2_managed_result_limit_and_file_budget(self) -> None:
        oversized_id = "wa-20260722T000000-000000000112"
        self._v2_request(oversized_id)
        oversized = self.harness.root / "oversized-v2.bin"
        with oversized.open("wb") as handle:
            handle.truncate(16 * 1024 * 1024 + 1)
        rejected, _ = self.harness.run(
            "reply",
            oversized_id,
            "--status",
            "done",
            "--file",
            str(oversized),
            ok=False,
        )
        self.assertEqual(rejected["error"]["code"], "result_file_too_large")
        self.assertEqual(
            list(
                (self.harness.runtime / "requests" / oversized_id / "events").iterdir()
            ),
            [],
        )
        accepted, _ = self.harness.run(
            "reply", oversized_id, "--status", "done", "--message", "retry"
        )
        self.assertTrue(accepted["ok"])
        self.assertTrue(
            (
                self.harness.runtime
                / "requests"
                / oversized_id
                / "events"
                / "000001.json"
            ).is_file()
        )

        budget_id = "wa-20260722T000000-000000000113"
        budget = self._v2_request(budget_id)
        one_result = b"\0" * (16 * 1024 * 1024)
        one_digest = hashlib.sha256(one_result).hexdigest()
        for seq in range(1, 5):
            result_dir = budget / "result" / f"{seq:06d}"
            result_dir.mkdir(mode=0o700)
            result_file = result_dir / "fixture.bin"
            result_file.write_bytes(one_result)
            self._event_fixture(
                budget,
                seq,
                "progress",
                result={
                    "path": str(result_file.resolve()),
                    "bytes": 16 * 1024 * 1024,
                    "sha256": one_digest,
                },
            )
        exhausted = self.harness.root / "budget-exhausted.bin"
        exhausted.write_bytes(b"x")
        rejected, _ = self.harness.run(
            "reply",
            budget_id,
            "--status",
            "progress",
            "--file",
            str(exhausted),
            ok=False,
        )
        self.assertEqual(rejected["error"]["code"], "reply_result_budget_exhausted")
        self.assertFalse((budget / "events" / "000005.json").exists())
        terminal, _ = self.harness.run(
            "reply", budget_id, "--status", "done", "--message", "budget terminal"
        )
        self.assertTrue(terminal["ok"])

    def test_v2_sliding_ttl_renews_on_event_but_expires_without_one(self) -> None:
        identifier = "wa-20260722T000000-000000000105"
        self._v2_request(identifier, ttl=1.0)
        time.sleep(0.2)
        self.harness.run(
            "reply", identifier, "--status", "progress", "--message", "renew"
        )
        time.sleep(0.2)
        replied, _ = self.harness.run("reply", identifier, "--status", "done")
        self.assertTrue(replied["ok"])

        expired_id = "wa-20260722T000000-000000000106"
        self._v2_request(expired_id, ttl=0.05)
        time.sleep(0.1)
        expired, _ = self.harness.run("reply", expired_id, "--status", "done", ok=False)
        self.assertEqual(expired["error"]["code"], "reply_ticket_expired")

    def test_v2_event_gap_and_symlink_fail_closed(self) -> None:
        gap_id = "wa-20260722T000000-000000000107"
        gap = self._v2_request(gap_id)
        self._event_fixture(gap, 2, "progress")
        rejected, _ = self.harness.run("reply", gap_id, "--status", "done", ok=False)
        self.assertEqual(rejected["error"]["code"], "reply_ticket_invalid")
        self.assertFalse((gap / "events" / "000001.json").exists())

        symlink_id = "wa-20260722T000000-000000000108"
        symlink = self._v2_request(symlink_id)
        source = self.harness.root / "event-source.json"
        source.write_text("{}", encoding="utf-8")
        (symlink / "events" / "000001.json").symlink_to(source)
        rejected, _ = self.harness.run(
            "reply", symlink_id, "--status", "done", ok=False
        )
        self.assertEqual(rejected["error"]["code"], "reply_ticket_invalid")

    def test_v2_temporary_event_is_ignored_but_schema_mismatch_fails_closed(
        self,
    ) -> None:
        identifier = "wa-20260722T000000-000000000119"
        directory = self._v2_request(identifier)
        temporary = directory / "events" / ".000001.json.interrupted"
        temporary.write_text("partial", encoding="utf-8")
        inbox, _ = self.harness.run("inbox", identifier)
        self.assertEqual(inbox["request"]["count"], 0)

        self._event_fixture(directory, 1, "progress")
        event_path = directory / "events" / "000001.json"
        event = CONTROLLER.safe_read_json(event_path)
        event["terminal"] = True
        CONTROLLER.atomic_write_json(event_path, event)
        rejected, _ = self.harness.run("inbox", identifier, ok=False)
        self.assertEqual(rejected["error"]["code"], "reply_ticket_invalid")

    def test_v2_missing_or_corrupt_notification_does_not_hide_event(self) -> None:
        identifier = "wa-20260722T000000-000000000117"
        directory = self._v2_request(identifier)
        self._event_fixture(directory, 1, "progress", message="event survives")
        notifications = directory / "notifications"
        notifications.mkdir(exist_ok=True)
        (notifications / "000001.json").write_text("{not-json", encoding="utf-8")
        inbox, _ = self.harness.run("inbox", identifier)
        event = inbox["request"]["events"][0]
        self.assertEqual(event["message"], "event survives")
        self.assertEqual(event["notification"]["state"], "invalid")
        (notifications / "000001.json").unlink()
        inbox, _ = self.harness.run("inbox", identifier)
        self.assertEqual(
            inbox["request"]["events"][0]["notification"]["state"], "missing"
        )

    def test_mixed_v1_v2_inbox_and_gc_keep_pending_requests(self) -> None:
        caller, _ = self.harness.launch_mock("caller")
        caller_identity = CONTROLLER.identity_of(caller["target"])
        caller_route = {"kind": "tmux", **caller_identity}
        v1_id = "wa-20260722T000000-000000000109"
        v1 = self.harness.runtime / "requests" / v1_id
        v1.mkdir(mode=0o700, parents=True)
        CONTROLLER.atomic_write_json(
            v1 / "request.json",
            {
                "version": 1,
                "request_id": v1_id,
                "created_at": CONTROLLER.iso_now(),
                "created_epoch": time.time(),
                "phase": "active",
                "caller": caller_route,
                "notify_mode": "spool",
                "notify_armed": False,
                "reply_ttl_seconds": None,
            },
            exclusive=True,
        )
        CONTROLLER.atomic_write_json(
            v1 / "reply.json",
            {
                "version": 1,
                "request_id": v1_id,
                "created_at": CONTROLLER.iso_now(),
                "status": "done",
                "message": "v1",
            },
            exclusive=True,
        )
        v2_id = "wa-20260722T000000-000000000110"
        v2 = self._v2_request(v2_id, caller=caller_route)
        self._event_fixture(v2, 1, "done", message="v2")
        pending_id = "wa-20260722T000000-000000000111"
        self._v2_request(pending_id, caller=caller_route)

        environment = self.harness.environment.copy()
        environment["TMUX"] = f"{self.harness.socket},0,0"
        environment["TMUX_PANE"] = caller["target"]["pane_id"]
        environment.pop("WITH_AGENTS_CALLER_ID", None)
        completed = subprocess.run(
            self.harness.command("inbox"),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        inbox = json.loads(completed.stdout)
        self.assertEqual(inbox["request"]["count"], 2)
        self.assertEqual(
            [item["request_id"] for item in inbox["request"]["items"]], [v1_id, v2_id]
        )
        v2_items = [
            item
            for item in inbox["request"].get("items", [])
            if item["request_id"] == v2_id
        ]
        self.assertEqual(v2_items[0]["protocol_version"], 2)

        collected, _ = self.harness.run("gc")
        self.assertIn(v1_id, collected["request"]["removed"])
        self.assertIn(v2_id, collected["request"]["removed"])
        self.assertTrue((self.harness.runtime / "requests" / pending_id).exists())

    def test_caller_inbox_lists_replies_but_not_pending_requests(self) -> None:
        caller, _ = self.harness.launch_mock("caller")
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request", "child", "--reply-to", "caller", "--", "review"
        )
        environment = self.harness.environment.copy()
        environment["TMUX"] = f"{self.harness.socket},0,0"
        environment["TMUX_PANE"] = caller["target"]["pane_id"]
        environment.pop("WITH_AGENTS_CALLER_ID", None)

        def caller_inbox() -> dict:
            completed = subprocess.run(
                self.harness.command("inbox"),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=environment,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(completed.stdout)

        self.assertEqual(caller_inbox()["request"]["count"], 0)
        self.harness.run(
            "reply", requested["request"]["request_id"], "--status", "done"
        )
        inbox = caller_inbox()
        self.assertEqual(inbox["request"]["count"], 1)
        self.assertEqual(
            inbox["request"]["items"][0]["request_id"],
            requested["request"]["request_id"],
        )

    def test_send_creates_no_ticket_and_request_does_not_persist_task_text(
        self,
    ) -> None:
        _, child_log = self.harness.launch_mock("child")
        self.harness.run("send", "child", "--", "fire and forget")
        request_root = self.harness.runtime / "requests"
        self.assertEqual(list(request_root.iterdir()), [])

        self.harness.run("read", "child")
        task = "unique task text that must not enter request state"
        requested, _ = self.harness.run("request", "child", "--", task)
        identifier = requested["request"]["request_id"]
        record_path = request_root / identifier / "request.json"
        record_text = record_path.read_text(encoding="utf-8")
        record = json.loads(record_text)
        self.assertNotIn(task, record_text)
        self.assertEqual(
            record["result_dir"], str((request_root / identifier / "result").resolve())
        )
        self.assertEqual(record["limits"]["message_bytes"], 1024)
        self.assertEqual(record["limits"]["result_bytes_per_event"], 16 * 1024 * 1024)
        self.assertEqual(record["limits"]["files_per_event"], 1)
        self.assertIn(task, self.harness.read_log(child_log)[-1])
        self.assertIn(str(CLI.resolve()), self.harness.read_log(child_log)[-1])
        self.assertIn(
            str(self.harness.runtime.resolve()), self.harness.read_log(child_log)[-1]
        )

    def test_invalid_request_text_creates_no_ticket(self) -> None:
        self.harness.launch_mock("child")
        rejected, _ = self.harness.run("request", "child", "", ok=False)
        self.assertEqual(rejected["error"]["code"], "empty_message")
        self.assertEqual(list((self.harness.runtime / "requests").iterdir()), [])

        rejected, _ = self.harness.run(
            "request",
            "child",
            "--reply-socket",
            str(self.harness.socket),
            "--",
            "task",
            ok=False,
        )
        self.assertEqual(rejected["error"]["code"], "reply_route_invalid")
        self.assertEqual(list((self.harness.runtime / "requests").iterdir()), [])

    def test_nonfinite_durations_are_rejected(self) -> None:
        self.harness.launch_mock("child")
        waited, _ = self.harness.run("wait", "child", "--timeout", "nan", ok=False)
        self.assertEqual(waited["error"]["code"], "invalid_wait")
        requested, _ = self.harness.run(
            "request", "child", "--reply-ttl", "inf", "--", "task", ok=False
        )
        self.assertEqual(requested["error"]["code"], "invalid_reply_ttl")
        collected, _ = self.harness.run("gc", "--stale", "nan", ok=False)
        self.assertEqual(collected["error"]["code"], "invalid_stale_age")

    def test_request_preflight_failure_aborts_its_ticket(self) -> None:
        self.harness.launch_mock("child")
        self.harness.run("send", "child", "--", "consume observation")
        rejected, _ = self.harness.run(
            "request", "child", "--", "must not dispatch", ok=False
        )
        self.assertEqual(rejected["error"]["code"], "observation_required")
        identifier = rejected["request"]["request_id"]
        self.assertEqual(rejected["request"]["phase"], "aborted")
        reply, _ = self.harness.run("reply", identifier, "--status", "done", ok=False)
        self.assertEqual(reply["error"]["code"], "reply_ticket_invalid")

    def test_result_file_rejects_symlink_and_oversize(self) -> None:
        self.harness.launch_mock("child")
        request_one, _ = self.harness.run("request", "child", "--", "one")
        original = self.harness.root / "original.txt"
        original.write_text("content", encoding="utf-8")
        link = self.harness.root / "link.txt"
        link.symlink_to(original)
        rejected, _ = self.harness.run(
            "reply",
            request_one["request"]["request_id"],
            "--status",
            "done",
            "--file",
            str(link),
            ok=False,
        )
        self.assertEqual(rejected["error"]["code"], "result_file_invalid")

        self.harness.run("read", "child")
        request_two, _ = self.harness.run("request", "child", "--", "two")
        oversized = self.harness.root / "oversized.bin"
        with oversized.open("wb") as handle:
            handle.truncate(16 * 1024 * 1024 + 1)
        rejected, _ = self.harness.run(
            "reply",
            request_two["request"]["request_id"],
            "--status",
            "done",
            "--file",
            str(oversized),
            ok=False,
        )
        self.assertEqual(rejected["error"]["code"], "result_file_too_large")

    def test_codex_notification_positive_idle_and_danger_veto(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        _, caller_log = self.harness.launch_mock(
            "caller", executable=codex, mode="codex-background"
        )
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        self.assertTrue(requested["request"]["notify_armed"])
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "all good",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertIn("all good", self.harness.read_log(caller_log)[0])

        _, danger_log = self.harness.launch_mock(
            "danger", executable=codex, mode="danger"
        )
        self.harness.run("read", "child")
        danger_request, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "danger",
            "--",
            "review again",
        )
        danger_reply, _ = self.harness.run(
            "reply",
            danger_request["request"]["request_id"],
            "--status",
            "progress",
            "--message",
            "do not inject",
        )
        self.assertEqual(
            danger_reply["notification"]["reason"], "unsafe_callback_state"
        )
        self.assertFalse(danger_reply["notification"]["injection_attempted"])
        self.harness.run(
            "restart",
            "danger",
            "--",
            str(codex),
            "--log",
            str(danger_log),
            "--mode",
            "idle",
        )
        recovered, _ = self.harness.run(
            "reply",
            danger_request["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "later event still attempts",
        )
        self.assertTrue(recovered["notification"]["tmux_accepted"])
        self.assertIn(
            "later event still attempts", self.harness.read_log(danger_log)[0]
        )

    def test_codex_busy_notification_uses_enter_steering_key(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        caller, caller_log = self.harness.launch_mock(
            "caller", executable=codex, mode="busy"
        )
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "queued result",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertIn("queued result", self.harness.read_log(caller_log)[0])
        captured = self.harness.tmux(
            "capture-pane",
            "-p",
            "-t",
            caller["target"]["pane_id"],
            "-S",
            "-40",
        ).stdout
        self.assertIn("RECEIVED:", captured)
        self.assertNotIn("QUEUED:", captured)

    def test_self_target_is_denied_even_with_foreign_authorization(self) -> None:
        launched, _ = self.harness.launch_mock("caller")
        pane_id = launched["target"]["pane_id"]
        environment = self.harness.environment.copy()
        environment["TMUX"] = f"{self.harness.socket},0,0"
        environment["TMUX_PANE"] = pane_id
        environment.pop("WITH_AGENTS_CALLER_ID", None)
        completed = subprocess.run(
            self.harness.command(
                "send", "caller", "--allow-foreign", "--", "must be rejected"
            ),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            timeout=30,
            check=False,
        )
        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stderr)
        Harness.assert_envelope(payload)
        self.assertEqual(payload["error"]["code"], "self_target_denied")

    def test_pi_notification_uses_enter_without_extended_keys(self) -> None:
        pi = self.harness.make_agent_executable("pi")
        caller, caller_log = self.harness.launch_mock(
            "caller", executable=pi, mode="busy"
        )
        _, child_log = self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "pi steering",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        child_messages = self.harness.read_log(child_log)
        self.assertEqual(len(child_messages), 1)
        self.assertTrue(
            child_messages[0].startswith("review  [with-agents async request=")
        )
        self.assertIn("pi steering", self.harness.read_log(caller_log)[0])
        captured = self.harness.tmux(
            "capture-pane",
            "-p",
            "-t",
            caller["target"]["pane_id"],
            "-S",
            "-40",
        ).stdout
        self.assertIn("RECEIVED:", captured)
        self.assertNotIn("QUEUED:", captured)

    def test_pi_notification_does_not_depend_on_pane_key_mode(self) -> None:
        pi = self.harness.make_agent_executable("pi")
        caller, caller_log = self.harness.launch_mock(
            "caller",
            executable=pi,
            mode="busy",
            extra=["--request-extended-keys"],
        )
        self.harness.tmux("set-option", "-s", "extended-keys", "on")
        self.harness.tmux("set-option", "-s", "extended-keys-format", "csi-u")
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "late config is irrelevant",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertEqual(len(self.harness.read_log(caller_log)), 1)
        pane_mode = self.harness.tmux(
            "display-message",
            "-p",
            "-t",
            caller["target"]["pane_id"],
            "#{pane_key_mode}",
        ).stdout.strip()
        self.assertEqual(pane_mode, "VT10x")

    def test_pi_notification_uses_enter_even_in_ext_2_mode(self) -> None:
        self.harness.launch_mock("bootstrap")
        self.harness.tmux("set-option", "-s", "extended-keys", "on")
        self.harness.tmux("set-option", "-s", "extended-keys-format", "csi-u")
        pi = self.harness.make_agent_executable("pi")
        caller, caller_log = self.harness.launch_mock(
            "caller",
            executable=pi,
            mode="busy",
            extra=["--request-extended-keys"],
        )
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "pi queued",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertEqual(len(self.harness.read_log(caller_log)), 1)
        self.assertNotIn("\x1b", self.harness.read_log(caller_log)[0])
        captured = self.harness.tmux(
            "capture-pane",
            "-p",
            "-t",
            caller["target"]["pane_id"],
            "-S",
            "-40",
        ).stdout
        self.assertIn("RECEIVED:", captured)
        self.assertNotIn("QUEUED:", captured)

    def test_same_pane_agent_respawn_uses_current_capability(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        caller, caller_log = self.harness.launch_mock("caller", executable=codex)
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        restarted, _ = self.harness.run(
            "restart",
            "caller",
            "--",
            str(codex),
            "--log",
            str(caller_log),
            "--mode",
            "idle",
        )
        self.assertEqual(restarted["target"]["pane_id"], caller["target"]["pane_id"])
        self.assertNotEqual(
            restarted["target"]["pane_pid"], caller["target"]["pane_pid"]
        )
        self.assertNotEqual(restarted["target"]["run_id"], caller["target"]["run_id"])
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "spool survives",
        )
        self.assertTrue(replied["notification"]["spooled"])
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertEqual(replied["notification"]["reason"], "tmux_accepted")
        self.assertIn("spool survives", self.harness.read_log(caller_log)[0])

    def test_same_route_non_agent_process_is_not_injected(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        self.harness.launch_mock("caller", executable=codex)
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        non_agent_log = self.harness.root / "non-agent.jsonl"
        self.harness.run(
            "restart",
            "caller",
            "--",
            sys.executable,
            "-u",
            str(FIXTURE),
            "--log",
            str(non_agent_log),
            "--mode",
            "idle",
        )
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "must remain spooled",
        )
        self.assertEqual(replied["notification"]["reason"], "caller_not_agent")
        self.assertFalse(replied["notification"]["injection_attempted"])
        self.assertEqual(self.harness.read_log(non_agent_log), [])

    def test_registered_generic_notification_uses_enter_with_unverified_tui(
        self,
    ) -> None:
        self._write_agent_config(
            {
                "opencode": {
                    "pane_prefix": "oc",
                    "executables": ["opencode"],
                }
            }
        )
        opencode = self.harness.make_agent_executable("opencode")
        _, caller_log = self.harness.launch_mock("caller", executable=opencode)
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "generic result",
        )
        notification = replied["notification"]
        self.assertTrue(notification["text_attempted"])
        self.assertTrue(notification["text_tmux_accepted"])
        self.assertTrue(notification["submit_attempted"])
        self.assertTrue(notification["submit_tmux_accepted"])
        self.assertTrue(notification["tmux_accepted"])
        self.assertEqual(notification["tui_acceptance"], "unverified")
        self.assertIn("generic result", self.harness.read_log(caller_log)[0])

    def test_registry_agent_type_cannot_grant_codex_capability(self) -> None:
        self._write_agent_config({"codex": {"executables": ["mycodex"]}})
        mycodex = self.harness.make_agent_executable("mycodex")
        _, caller_log = self.harness.launch_mock(
            "caller", executable=mycodex, mode="danger"
        )
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "generic despite agent type",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertEqual(replied["notification"]["tui_acceptance"], "unverified")
        self.assertIn(
            "generic despite agent type", self.harness.read_log(caller_log)[0]
        )

    def test_invalid_config_keeps_builtin_callback_but_degrades_custom_generic(
        self,
    ) -> None:
        config = self._write_agent_config(
            {
                "opencode": {
                    "pane_prefix": "oc",
                    "executables": ["opencode"],
                }
            }
        )
        codex = self.harness.make_agent_executable("codex")
        opencode = self.harness.make_agent_executable("opencode")
        _, codex_log = self.harness.launch_mock("codex-caller", executable=codex)
        _, generic_log = self.harness.launch_mock("generic-caller", executable=opencode)
        self.harness.launch_mock("child-one")
        self.harness.launch_mock("child-two")
        builtin_request, _ = self.harness.run(
            "request",
            "child-one",
            "--notify",
            "pane",
            "--reply-to",
            "codex-caller",
            "--",
            "builtin",
        )
        generic_request, _ = self.harness.run(
            "request",
            "child-two",
            "--notify",
            "pane",
            "--reply-to",
            "generic-caller",
            "--",
            "generic",
        )
        config.write_text("{invalid", encoding="utf-8")

        builtin_reply, _ = self.harness.run(
            "reply",
            builtin_request["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "builtin survives",
        )
        generic_reply, _ = self.harness.run(
            "reply",
            generic_request["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "custom degrades",
        )
        self.assertTrue(builtin_reply["notification"]["tmux_accepted"])
        self.assertIn("builtin survives", self.harness.read_log(codex_log)[0])
        self.assertEqual(
            generic_reply["notification"]["reason"], "invalid_agent_config"
        )
        self.assertFalse(generic_reply["notification"]["injection_attempted"])
        self.assertEqual(self.harness.read_log(generic_log), [])
        inbox, _ = self.harness.run("inbox", generic_request["request"]["request_id"])
        self.assertTrue(inbox["request"]["terminal"])

    def test_deleted_capability_executable_does_not_gate_callback(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        _, caller_log = self.harness.launch_mock("caller", executable=codex)
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        codex.unlink()
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "no version probe",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertIn("no version probe", self.harness.read_log(caller_log)[0])

    def test_forward_version_is_diagnostic_not_callback_gate(self) -> None:
        self.harness.environment["MOCK_AGENT_VERSION"] = "codex-cli 9.9.9"
        codex = self.harness.make_agent_executable("codex")
        _, caller_log = self.harness.launch_mock("caller", executable=codex)
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "forward version",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertIn("forward version", self.harness.read_log(caller_log)[0])

    def test_closed_pane_id_is_not_reused_for_callback(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        caller, _ = self.harness.launch_mock("caller", executable=codex)
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        old_pane_id = caller["target"]["pane_id"]
        self.harness.tmux("kill-pane", "-t", old_pane_id)
        replacement, replacement_log = self.harness.launch_mock(
            "replacement", executable=codex
        )
        self.assertNotEqual(replacement["target"]["pane_id"], old_pane_id)
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "old route",
        )
        self.assertEqual(replied["notification"]["reason"], "caller_identity_mismatch")
        self.assertEqual(self.harness.read_log(replacement_log), [])

    def test_replaced_server_pid_stops_old_callback_route(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        caller, _ = self.harness.launch_mock("caller", executable=codex)
        self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        old_server_pid = caller["target"]["server_pid"]
        old_pane_id = caller["target"]["pane_id"]
        self.harness.tmux("kill-server")
        replacement, replacement_log = self.harness.launch_mock(
            "replacement", executable=codex
        )
        self.assertNotEqual(replacement["target"]["server_pid"], old_server_pid)
        self.assertEqual(replacement["target"]["pane_id"], old_pane_id)
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "old server route",
        )
        self.assertEqual(replied["notification"]["reason"], "caller_identity_mismatch")
        self.assertEqual(self.harness.read_log(replacement_log), [])

    def test_claude_notification_capability_does_not_gate_dispatch(self) -> None:
        claude = self.harness.make_agent_executable("claude")
        _, caller_log = self.harness.launch_mock("caller", executable=claude)
        _, child_log = self.harness.launch_mock("child")
        requested, _ = self.harness.run(
            "request",
            "child",
            "--notify",
            "pane",
            "--reply-to",
            "caller",
            "--",
            "review",
        )
        self.assertTrue(requested["request"]["notify_armed"])
        self.assertIn("review", self.harness.read_log(child_log)[0])
        replied, _ = self.harness.run(
            "reply",
            requested["request"]["request_id"],
            "--status",
            "done",
            "--message",
            "generic builtin",
        )
        self.assertTrue(replied["notification"]["tmux_accepted"])
        self.assertEqual(replied["notification"]["tui_acceptance"], "unverified")
        self.assertIn("generic builtin", self.harness.read_log(caller_log)[0])

    def test_question_is_nonterminal_and_reply_ttl_expires(self) -> None:
        self.harness.launch_mock("child")
        requested, _ = self.harness.run("request", "child", "--", "question")
        identifier = requested["request"]["request_id"]
        self.harness.run(
            "reply", identifier, "--status", "question", "--message", "clarify"
        )
        terminal, _ = self.harness.run("reply", identifier, "--status", "done")
        self.assertTrue(terminal["request"]["event"]["terminal"])

        self.harness.run("read", "child")
        expiring, _ = self.harness.run(
            "request", "child", "--reply-ttl", "0.05", "--", "expires"
        )
        time.sleep(0.08)
        expired, _ = self.harness.run(
            "reply", expiring["request"]["request_id"], "--status", "done", ok=False
        )
        self.assertEqual(expired["error"]["code"], "reply_ticket_expired")

    def test_reply_ttl_starts_after_dispatch_finishes(self) -> None:
        codex = self.harness.make_agent_executable("codex")
        self.harness.launch_mock("child", executable=codex)
        requested, _ = self.harness.run(
            "request", "child", "--reply-ttl", "0.2", "--", "fast reply"
        )
        identifier = requested["request"]["request_id"]
        record = json.loads(
            (self.harness.runtime / "requests" / identifier / "request.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertGreaterEqual(record["dispatched_epoch"], record["created_epoch"])
        replied, _ = self.harness.run("reply", identifier, "--status", "done")
        self.assertEqual(replied["stage"], "outcome_persisted")

    def test_stale_gc_reports_then_explicitly_deletes_pending(self) -> None:
        self.harness.launch_mock("child")
        requested, _ = self.harness.run("request", "child", "--", "pending")
        identifier = requested["request"]["request_id"]
        reported, _ = self.harness.run("gc", "--stale", "0")
        self.assertIn(identifier, reported["request"]["stale"])
        self.harness.run("inbox", identifier)
        deleted, _ = self.harness.run("gc", "--stale", "0", "--delete-stale")
        self.assertIn(identifier, deleted["request"]["removed"])
        missing, _ = self.harness.run("inbox", identifier, ok=False)
        self.assertEqual(missing["error"]["code"], "reply_ticket_invalid")

    def test_concurrent_terminal_reply_publishes_once(self) -> None:
        self.harness.launch_mock("child")
        requested, _ = self.harness.run("request", "child", "--", "review")
        identifier = requested["request"]["request_id"]
        commands = [
            self.harness.command(
                "reply", identifier, "--status", "done", "--message", f"reply {index}"
            )
            for index in range(2)
        ]
        processes = [
            subprocess.Popen(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.harness.environment,
            )
            for command in commands
        ]
        results = [
            process.communicate(timeout=30) + (process.returncode,)
            for process in processes
        ]
        self.assertEqual(sorted(result[2] for result in results), [0, 1])
        inbox, _ = self.harness.run("inbox", identifier)
        self.assertIn(inbox["request"]["events"][0]["message"], ("reply 0", "reply 1"))


if __name__ == "__main__":
    unittest.main()
