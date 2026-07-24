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
PLUGIN_ROOT = TEST_ROOT.parent
SKILL_ROOT = PLUGIN_ROOT / "skills" / "with-agents"
ZH_OVERLAY_ROOT = PLUGIN_ROOT / "variants" / "zh"
CLI = SKILL_ROOT / "scripts" / "with-agents"
LAUNCHER = SKILL_ROOT / "scripts" / "launch-agent"
FIXTURE = TEST_ROOT / "fixtures" / "mock_agent.py"
TOP_FIELDS = [
    "ok",
    "event",
    "stage",
    "target",
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
    heading_levels: list[int] = []
    fenced_blocks: list[tuple[str, ...]] = []
    inline_code: list[str] = []
    link_paths: list[str] = []
    current_block: list[str] | None = None
    fence = chr(96) * 3
    for line in text.splitlines():
        if line.startswith(fence):
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
        inline_code.extend(re.findall(r"\x60([^\x60]+)\x60", line))
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
    def __init__(self, *, socket_name: str = "tmux.sock") -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="with-agents-test-")
        self.root = Path(self.temporary.name)
        self.socket = self.root / socket_name
        self.runtime = self.root / "runtime"
        self.config = self.root / "config"
        self.environment = os.environ.copy()
        self.environment.pop("TMUX", None)
        self.environment.pop("TMUX_PANE", None)

    def command(
        self,
        *arguments: str,
        json_output: bool = True,
        include_socket: bool = True,
        runtime: Path | None = None,
        config: Path | None = None,
    ) -> list[str]:
        command = [sys.executable, str(CLI)]
        if json_output:
            command.append("--json")
        if include_socket:
            command.extend(["--socket", str(self.socket)])
        command.extend(
            [
                "--runtime-dir",
                str(runtime or self.runtime),
                "--config-dir",
                str(config or self.config),
                *arguments,
            ]
        )
        return command

    def run(
        self,
        *arguments: str,
        ok: bool = True,
        environment: dict[str, str] | None = None,
        timeout: float = 30,
        include_socket: bool = True,
        runtime: Path | None = None,
        config: Path | None = None,
    ) -> tuple[dict, subprocess.CompletedProcess[str]]:
        completed = subprocess.run(
            self.command(
                *arguments,
                include_socket=include_socket,
                runtime=runtime,
                config=config,
            ),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment or self.environment,
            timeout=timeout,
            check=False,
        )
        payload_text = completed.stdout if completed.stdout.strip() else completed.stderr
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"non-JSON output for {arguments}:\n"
                f"stdout={completed.stdout}\nstderr={completed.stderr}"
            ) from exc
        if list(payload) != TOP_FIELDS:
            raise AssertionError(f"unstable envelope: {list(payload)}")
        if ok and completed.returncode != 0:
            raise AssertionError(f"command failed: {arguments}\n{payload_text}")
        if not ok and completed.returncode == 0:
            raise AssertionError(
                f"command unexpectedly succeeded: {arguments}\n{payload_text}"
            )
        return payload, completed

    def run_text(
        self,
        *arguments: str,
        ok: bool = True,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            self.command(*arguments, json_output=False),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment or self.environment,
            timeout=30,
            check=False,
        )
        if ok and completed.returncode != 0:
            raise AssertionError(
                f"command failed: {arguments}\n{completed.stdout}{completed.stderr}"
            )
        if not ok and completed.returncode == 0:
            raise AssertionError(f"command unexpectedly succeeded: {arguments}")
        return completed

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

    def launch_mock(
        self,
        name: str,
        *,
        mode: str = "idle",
        startup_delay: float = 0,
        no_wait: bool = False,
        bracketed_paste: bool = True,
    ) -> tuple[dict, Path]:
        log = self.root / f"{name}-{uuid.uuid4().hex}.jsonl"
        argv = [
            sys.executable,
            "-u",
            str(FIXTURE),
            "--log",
            str(log),
            "--mode",
            mode,
            "--startup-delay",
            str(startup_delay),
        ]
        if not bracketed_paste:
            argv.append("--no-bracketed-paste")
        arguments = [
            "launch",
            "--name",
            name,
            "--cwd",
            str(TEST_ROOT),
            "--ready-timeout",
            "4",
        ]
        if no_wait:
            arguments.append("--no-wait")
        arguments.extend(["--", *argv])
        payload, _ = self.run(*arguments)
        return payload, log

    def launch_split_mock(
        self, target: str, *, ready_timeout: str = "4"
    ) -> tuple[dict, Path]:
        log = self.root / f"split-{uuid.uuid4().hex}.jsonl"
        payload, _ = self.run(
            "launch",
            "--split",
            target,
            "--cwd",
            str(TEST_ROOT),
            "--ready-timeout",
            ready_timeout,
            "--",
            sys.executable,
            "-u",
            str(FIXTURE),
            "--log",
            str(log),
        )
        return payload, log

    def caller_environment(self, pane_id: str) -> dict[str, str]:
        server_pid = self.tmux("display-message", "-p", "#{pid}").stdout.strip()
        environment = self.environment.copy()
        environment["TMUX"] = f"{self.socket},{server_pid},0"
        environment["TMUX_PANE"] = pane_id
        return environment

    def route(self, target: str) -> str:
        payload, _ = self.run("route", target)
        return payload["target"]["route"]

    @staticmethod
    def read_log(path: Path) -> list[str]:
        if not path.is_file():
            return []
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def wait_for_log(self, path: Path, count: int) -> list[str]:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            values = self.read_log(path)
            if len(values) >= count:
                return values
            time.sleep(0.05)
        return self.read_log(path)

    def close(self) -> None:
        self.tmux("kill-server", check=False)
        self.temporary.cleanup()


class FakeClient:
    def __init__(self) -> None:
        self.current = {
            "kind": "pane",
            "socket_path": "/tmp/with-agents-fake.sock",
            "server_pid": 100,
            "pane_id": "%1",
            "pane_pid": 200,
            "session": "fake",
            "window_index": "0",
            "pane_index": "0",
            "session_window_pane": "fake:0.0",
            "process": "agent",
            "cwd": str(TEST_ROOT),
            "dead": False,
            "dead_status": None,
            "name": "fake",
            "title": "fake",
        }
        self.fail_run_command: str | None = None
        self.fail_code = "tmux_timeout"
        self.fail_capture = False
        self.missing = False
        self.calls: list[list[str]] = []

    def pane(self, target: str) -> dict:
        if self.missing or target != self.current["pane_id"]:
            raise CONTROLLER.WAError(
                "target_not_found", f"cannot resolve pane target: {target}"
            )
        return dict(self.current)

    def capture(self, _: str, __: int = 80) -> str:
        if self.fail_capture:
            raise CONTROLLER.WAError("tmux_timeout", "capture timed out")
        return "screen"

    def run(
        self,
        arguments,
        *,
        input_text=None,
        stage="tmux",
        check=True,
    ) -> SimpleNamespace:
        del input_text, check
        self.calls.append(list(arguments))
        if arguments and arguments[0] == self.fail_run_command:
            raise CONTROLLER.WAError(self.fail_code, "injected failure", stage=stage)
        return SimpleNamespace(stdout="", stderr="", returncode=0)


class PureContractTests(unittest.TestCase):
    def test_sparse_translation_overlay_and_single_executable(self) -> None:
        files = {
            path.relative_to(ZH_OVERLAY_ROOT).as_posix()
            for path in ZH_OVERLAY_ROOT.rglob("*")
            if path.is_file()
        }
        self.assertEqual(files, TRANSLATABLE_FILES)
        self.assertFalse((ZH_OVERLAY_ROOT / "scripts").exists())
        self.assertTrue(os.access(CLI, os.X_OK))
        self.assertFalse(LAUNCHER.exists())

    def test_translation_structure_matches_english_base(self) -> None:
        for relative in sorted(TRANSLATABLE_FILES):
            english = (SKILL_ROOT / relative).read_text(encoding="utf-8")
            chinese = (ZH_OVERLAY_ROOT / relative).read_text(encoding="utf-8")
            if relative.endswith(".md"):
                en_contract = markdown_translation_contract(english)
                zh_contract = markdown_translation_contract(chinese)
                self.assertEqual(
                    en_contract[0], zh_contract[0], f"heading levels: {relative}"
                )
                self.assertEqual(
                    en_contract[1], zh_contract[1], f"code fences: {relative}"
                )
                self.assertEqual(
                    en_contract[2], zh_contract[2], f"inline code: {relative}"
                )
                self.assertEqual(
                    en_contract[3], zh_contract[3], f"links: {relative}"
                )

    def test_recovery_examples_keep_the_exact_socket(self) -> None:
        for root in (SKILL_ROOT, ZH_OVERLAY_ROOT):
            text = (root / "references" / "tmux-recovery.md").read_text(
                encoding="utf-8"
            )
            self.assertIn('rest="${TMUX%,*}"', text)
            self.assertIn('socket_path="${rest%,*}"', text)
            in_bash = False
            for line in text.splitlines():
                if line == "```bash":
                    in_bash = True
                    continue
                if line == "```":
                    in_bash = False
                    continue
                if in_bash and re.search(r"\btmux ", line):
                    self.assertRegex(
                        line,
                        r'\btmux (?:-V|-S "\$(?:socket_path|recovery_socket)")',
                    )

    def test_skill_entrypoints_do_not_restore_removed_contracts(self) -> None:
        text = "\n".join(
            (SKILL_ROOT / relative).read_text(encoding="utf-8")
            for relative in ("SKILL.md", "agents/openai.yaml")
        )
        for removed in (
            "low-freedom",
            "ticket",
            "spool",
            "notification",
            "request_id",
            "request command",
            "launch-agent",
            "run ID",
            "ownership",
            "adapter capability",
            "observation credential",
        ):
            with self.subTest(removed=removed):
                self.assertNotIn(removed, text)
        self.assertIsNone(re.search(r"\bchild\b", text, flags=re.IGNORECASE))

    def test_final_cli_surface_order_and_standard_version_option(self) -> None:
        parser = CONTROLLER.build_parser()
        subparsers = next(
            action
            for action in parser._actions
            if isinstance(action, CONTROLLER.argparse._SubParsersAction)
        )
        self.assertEqual(
            list(subparsers.choices),
            [
                "read",
                "send",
                "list",
                "launch",
                "wait",
                "key",
                "close",
                "preset",
                "doctor",
                "route",
            ],
        )
        completed = subprocess.run(
            [sys.executable, str(CLI), "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, "0.3.0\n")
        source = CLI.read_text(encoding="utf-8")
        for removed in (
            "command_request",
            "command_restart",
            "command_create",
            "command_version",
            "@with_agents_",
            "launch_record",
            "request_id",
            "route_identity_mismatch",
            "preset_from_pane",
            "PROCESS_LAUNCHERS",
            "--from",
        ):
            self.assertNotIn(removed, source)

    def test_literal_route_and_params_round_trip(self) -> None:
        pane = {
            "name": r"name&part]slash\end",
            "pane_id": "%75",
            "socket_path": r"/tmp/wa&part]slash\socket",
        }
        params = {
            "reply": "required",
            "correlation_id": "A1b2C3d4",
            "note": "check api, tests\nthen docs = '界' & ] \\",
        }
        route = CONTROLLER.render_route(pane, params=params)
        self.assertIn(r"name=name\&part\]slash\\end", route)
        self.assertIn("pane_id=75", route)
        self.assertNotIn("%2Ftmp", route)
        address, parsed_params = CONTROLLER.parse_route(route)
        self.assertEqual(address["name"], pane["name"])
        self.assertEqual(address["pane_id"], pane["pane_id"])
        self.assertEqual(
            address["socket_path"],
            os.path.realpath(pane["socket_path"]),
        )
        self.assertEqual(parsed_params, params)
        terminated_address, terminated_params = CONTROLLER.parse_route(route + "]")
        self.assertEqual(terminated_address, address)
        self.assertEqual(terminated_params, params)

        huge_address, _ = CONTROLLER.parse_route(
            "with-agents:tmux?name=huge&pane_id="
            + "0" * 5000
            + "75&socket=/tmp/huge.sock"
        )
        self.assertEqual(huge_address["pane_id"], "%75")

    def test_route_parser_rejects_each_malformed_class(self) -> None:
        malformed = [
            "with-agents:http?name=x&pane_id=1&socket=/tmp/x",
            "with-agents:tmux?pane_id=1&name=x&socket=/tmp/x",
            "with-agents:tmux?name=x&pane_id=1",
            "with-agents:tmux?name=x&pane_id=1&pane_id=2&socket=/tmp/x",
            "with-agents:tmux?name=x&pane_id=1&socket=/tmp/x&unknown=y",
            r"with-agents:tmux?name=bad\x&pane_id=1&socket=/tmp/x",
            "with-agents:tmux?name=x&pane_id=%1&socket=/tmp/x",
            "with-agents:tmux?name=x&pane_id=abc&socket=/tmp/x",
            "with-agents:tmux?name=x&pane_id=1&socket=relative",
            "with-agents:tmux?name=x\nbad&pane_id=1&socket=/tmp/x",
            "with-agents:tmux?name=x\u2028bad&pane_id=1&socket=/tmp/x",
            "with-agents:tmux?name=x\u2029bad&pane_id=1&socket=/tmp/x",
            "with-agents:tmux?name=x&pane_id=1&socket=/tmp/bad\x00socket",
            "with-agents:tmux?name=x&pane_id=1&socket=/tmp/x&params='x=%ZZ'",
            "with-agents:tmux?name=x&pane_id=1&socket=/tmp/x&params=",
            "with-agents:tmux?name=x&pane_id=1&socket=/tmp/x&params=''",
            "with-agents:tmux?name=x&pane_id=1&socket=/tmp/x&params=x=y",
            "with-agents:tmux?name=x&pane_id=1&socket=/tmp/x]tail",
        ]
        for value in malformed:
            with self.subTest(value=value):
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.parse_route(value)
                self.assertEqual(raised.exception.code, "route_invalid")

    def test_tmux_environment_is_parsed_from_the_right(self) -> None:
        self.assertEqual(
            CONTROLLER.parse_tmux_environment("/tmp/tmux,comma,sock,1234,7"),
            ("/tmp/tmux,comma,sock", 1234, 7),
        )
        for value in (
            "",
            "/tmp/sock,1234",
            "relative,1234,7",
            "/tmp/sock,pid,7",
            "/tmp/sock,1234,index",
            "/tmp/sock,１２３４,7",
            "/tmp/bad\x00socket,1234,7",
        ):
            with self.subTest(value=value):
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.parse_tmux_environment(value)
                self.assertEqual(
                    raised.exception.code, "caller_identity_unavailable"
                )

    def test_tmux_vis_window_names_decode_before_routing(self) -> None:
        encoded = r"slash\\tab\tnewline\nctrl\001escape\033"
        self.assertEqual(
            CONTROLLER.decode_tmux_vis(encoded),
            "slash\\tab\tnewline\nctrl\x01escape\x1b",
        )
        for value in ("trailing\\", r"unknown\x", r"short\12"):
            with self.subTest(value=value):
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.decode_tmux_vis(value)
                self.assertEqual(raised.exception.code, "tmux_output_invalid")
        for name in ("bad\tname", "bad\nname", "bad\u2028name", "bad\u2029name"):
            with self.subTest(name=name):
                self.assertEqual(
                    CONTROLLER.route_name({"name": name, "pane_id": "%75"}),
                    "pane-75",
                )

    def test_private_directory_errors_are_domain_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular_file = root / "file"
            regular_file.write_text("not a directory", encoding="utf-8")
            symlink = root / "link"
            symlink.symlink_to(root)
            for path in (regular_file, symlink):
                with self.subTest(path=path):
                    with self.assertRaises(CONTROLLER.WAError) as raised:
                        CONTROLLER.ensure_private_dir(path)
                    self.assertEqual(raised.exception.code, "unsafe_state_path")

            owned = root / "owned"
            owned.mkdir(mode=0o700)
            with (
                mock.patch.object(CONTROLLER.os, "getuid", return_value=os.getuid() + 1),
                self.assertRaises(CONTROLLER.WAError) as raised,
            ):
                CONTROLLER.ensure_private_dir(owned)
            self.assertEqual(raised.exception.code, "unsafe_state_path")

            if os.geteuid() != 0:
                blocked = root / "blocked"
                blocked.mkdir(mode=0o700)
                blocked.chmod(0)
                try:
                    with self.assertRaises(CONTROLLER.WAError) as raised:
                        CONTROLLER.ensure_private_dir(blocked / "child")
                    self.assertEqual(raised.exception.code, "unsafe_state_path")
                finally:
                    blocked.chmod(0o700)

    def test_split_target_is_revalidated_inside_its_pane_lock(self) -> None:
        for condition, error_code in (
            ("missing", "target_not_found"),
            ("dead", "target_process_exited"),
        ):
            with self.subTest(condition=condition):
                client = FakeClient()
                resolved = CONTROLLER.ResolvedTarget(client, client.current)
                lock = mock.MagicMock()

                def change_target() -> None:
                    if condition == "missing":
                        client.missing = True
                    else:
                        client.current = {**client.current, "dead": True}

                lock.__enter__.side_effect = change_target
                with (
                    tempfile.TemporaryDirectory() as directory,
                    mock.patch.object(
                        CONTROLLER, "resolve_target", return_value=resolved
                    ),
                    mock.patch.object(CONTROLLER, "pane_lock", return_value=lock),
                    self.assertRaises(CONTROLLER.WAError) as raised,
                ):
                    CONTROLLER.choose_new_pane(
                        client,
                        CONTROLLER.RuntimeState(directory),
                        name=None,
                        cwd=str(TEST_ROOT),
                        session=None,
                        split=(
                            "with-agents:tmux?name=fake&pane_id=1"
                            "&socket=/tmp/with-agents-fake.sock"
                        ),
                    )
                self.assertEqual(raised.exception.code, error_code)
                self.assertEqual(client.calls, [])

    def test_route_without_target_uses_one_caller_pane_snapshot(self) -> None:
        client = FakeClient()
        snapshot = {**client.current, "name": "caller-snapshot"}
        with mock.patch.object(
            CONTROLLER,
            "resolve_caller_pane",
            return_value=(client, snapshot),
        ) as resolve_caller:
            result = CONTROLLER.command_route(
                SimpleNamespace(target=None, socket=None),
                CONTROLLER.RuntimeState("/tmp/unused-with-agents-runtime"),
                CONTROLLER.ConfigState("/tmp/unused-with-agents-config"),
            )
        resolve_caller.assert_called_once_with(required=True)
        self.assertEqual(result["target"]["name"], "caller-snapshot")
        self.assertIn("name=caller-snapshot", result["target"]["route"])
        self.assertEqual(client.calls, [])

    def test_strict_json_params_and_canonical_message_header(self) -> None:
        target_client = FakeClient()
        caller_client = FakeClient()
        caller_client.current = {
            **caller_client.current,
            "pane_id": "%2",
            "name": "caller",
        }
        resolved = CONTROLLER.ResolvedTarget(target_client, target_client.current)
        args = SimpleNamespace(
            message="review",
            no_header=False,
            request=True,
            correlation_id=None,
            params='{"scope":"api","note":"a,b\\n界"}',
        )
        with mock.patch.object(
            CONTROLLER,
            "resolve_caller_pane",
            return_value=(caller_client, caller_client.current),
        ):
            message, metadata = CONTROLLER.build_send_message(args, resolved)
        self.assertRegex(metadata["correlation_id"], r"^[A-Za-z0-9]{8}$")
        sender = metadata["sender_route"]
        self.assertTrue(message.startswith(f"[{sender}] review"))
        self.assertIn(
            "&params='reply=required,correlation_id=",
            sender,
        )
        self.assertLess(sender.index("reply="), sender.index("correlation_id="))
        self.assertLess(sender.index("correlation_id="), sender.index("scope="))
        _, params = CONTROLLER.parse_route(sender)
        self.assertEqual(params, metadata["params"])
        self.assertEqual(params["note"], "a,b\n界")

        invalid = [
            ("[]", "params_invalid"),
            ('{"x":1}', "params_invalid"),
            ('{"x":true}', "params_invalid"),
            ('{"x":null}', "params_invalid"),
            ('{"x":"a","x":"b"}', "params_invalid"),
            ('{"x":"\\ud800"}', "params_invalid"),
            ('{"reply":"required"}', "params_source_conflict"),
            ('{"correlation_id":"x"}', "params_source_conflict"),
        ]
        for raw, code in invalid:
            with self.subTest(raw=raw):
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.parse_extra_params(raw)
                self.assertEqual(raised.exception.code, code)

        self.assertEqual(
            CONTROLLER.route_name({"name": "bad\tname", "pane_id": "%75"}),
            "pane-75",
        )

        raw = SimpleNamespace(
            message="/clear",
            no_header=True,
            request=False,
            correlation_id=None,
            params=None,
        )
        message, metadata = CONTROLLER.build_send_message(raw, resolved)
        self.assertEqual(message, "/clear")
        self.assertFalse(metadata["header"])
        for overrides in (
            {"request": True},
            {"correlation_id": "A1b2C3d4"},
            {"params": '{"scope":"api"}'},
        ):
            with self.subTest(overrides=overrides):
                conflicted = SimpleNamespace(**{**vars(raw), **overrides})
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.build_send_message(conflicted, resolved)
                self.assertEqual(raised.exception.code, "message_option_conflict")

    def test_public_pane_naming_rules(self) -> None:
        config_path = Path("/tmp/with-agents-config.json")
        self.assertEqual(CONTROLLER.validate_generated_suffix("a1B2"), "a1B2")
        self.assertEqual(CONTROLLER.validate_pane_name("explicit.name-1"), "explicit.name-1")
        for invalid in ("", "abcdefg", "has-dash"):
            with self.subTest(suffix=invalid):
                with self.assertRaises(CONTROLLER.WAError):
                    CONTROLLER.validate_generated_suffix(invalid)
        for prefix in ("x", "xyz", "x-"):
            with self.subTest(prefix=prefix):
                with self.assertRaises(CONTROLLER.WAError) as raised:
                    CONTROLLER.validate_agent_registry(
                        {"custom": {"pane_prefix": prefix}}, path=config_path
                    )
                self.assertEqual(raised.exception.code, "invalid_agent_config")

    def test_send_partial_stages_preserve_no_blind_replay_boundary(self) -> None:
        cases = [
            ("load-buffer", "tmux_timeout", "text_not_written"),
            ("paste-buffer", "tmux_timeout", "text_written_not_submitted"),
            ("send-keys", "tmux_command_failed", "text_written_not_submitted"),
            ("send-keys", "tmux_timeout", "submitted_state_unknown"),
        ]
        for command, code, expected_stage in cases:
            with self.subTest(command=command, code=code):
                with tempfile.TemporaryDirectory() as directory:
                    client = FakeClient()
                    client.fail_run_command = command
                    client.fail_code = code
                    resolved = CONTROLLER.ResolvedTarget(client, client.current)
                    with self.assertRaises(CONTROLLER.WAError) as raised:
                        CONTROLLER.atomic_submit(
                            CONTROLLER.RuntimeState(directory),
                            resolved,
                            message="body",
                        )
                    self.assertEqual(raised.exception.stage, expected_stage)

        with tempfile.TemporaryDirectory() as directory:
            client = FakeClient()
            resolved = CONTROLLER.ResolvedTarget(client, client.current)
            resolved, baseline = CONTROLLER.atomic_submit(
                CONTROLLER.RuntimeState(directory),
                resolved,
                message="body",
            )
            commands = [call[0] for call in client.calls]
            self.assertEqual(commands.count("load-buffer"), 1)
            self.assertEqual(commands.count("paste-buffer"), 1)
            self.assertEqual(commands.count("send-keys"), 1)
            send_keys = next(call for call in client.calls if call[0] == "send-keys")
            self.assertEqual(send_keys[-1], "Enter")
            self.assertNotIn("-l", send_keys)
            client.fail_capture = True
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.post_action_observation(
                    resolved,
                    baseline=baseline,
                    uncertain_stage="submitted_state_unknown",
                )
            self.assertEqual(raised.exception.stage, "submitted_state_unknown")

    def test_same_pane_id_without_socket_identity_fails_closed(self) -> None:
        client = FakeClient()
        with mock.patch.dict(os.environ, {"TMUX_PANE": "%1"}, clear=True):
            with self.assertRaises(CONTROLLER.WAError) as raised:
                CONTROLLER.ensure_not_self(client.current)
        self.assertEqual(raised.exception.code, "self_target_unverified")


@unittest.skipUnless(shutil.which("tmux"), "tmux is required")
class TargetAndRouteIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = Harness()

    def tearDown(self) -> None:
        self.harness.close()

    def test_compact_detail_canonical_route_and_live_window_rename(self) -> None:
        launched, _ = self.harness.launch_mock("alpha")
        pane_id = launched["target"]["pane_id"]
        route = launched["target"]["route"]
        self.assertIn(f"&socket={self.harness.socket}", route)

        listed, _ = self.harness.run("list")
        item = next(
            value for value in listed["target"]["items"] if value["pane_id"] == pane_id
        )
        self.assertEqual(item["route"], route)
        for hidden in ("socket_path", "server_pid", "pane_pid", "dead"):
            self.assertNotIn(hidden, item)
        listed_text = self.harness.run_text("list").stdout
        listed_lines = listed_text.splitlines()
        listed_header = listed_lines[1].split("\t")
        listed_row = next(
            line.split("\t")
            for line in listed_lines[2:]
            if line.startswith(f"{pane_id}\t")
        )
        self.assertEqual(dict(zip(listed_header, listed_row))["ROUTE"], route)

        detailed, _ = self.harness.run("list", "--detail")
        detail = next(
            value
            for value in detailed["target"]["items"]
            if value["pane_id"] == pane_id
        )
        for field in ("socket_path", "server_pid", "pane_pid", "dead"):
            self.assertIn(field, detail)
        self.assertEqual(detail["route"], route)
        self.assertEqual(detail["route"], self.harness.route(pane_id))
        detailed_text = self.harness.run_text("list", "--detail").stdout
        detailed_lines = detailed_text.splitlines()
        detailed_header = detailed_lines[1].split("\t")
        detailed_row = next(
            line.split("\t")
            for line in detailed_lines[2:]
            if line.startswith(f"{pane_id}\t")
        )
        self.assertEqual(
            dict(zip(detailed_header, detailed_row))["ROUTE"], detail["route"]
        )

        location = launched["target"]["session_window_pane"]
        for target in ("alpha", pane_id, location, route):
            with self.subTest(target=target):
                read, _ = self.harness.run("read", target)
                self.assertEqual(read["target"]["pane_id"], pane_id)

        window_target = (
            f"{launched['target']['session']}:{launched['target']['window_index']}"
        )
        self.harness.tmux("rename-window", "-t", window_target, "renamed")
        read, _ = self.harness.run("read", route)
        self.assertEqual(read["target"]["name"], "renamed")
        self.assertIn("name=renamed", read["target"]["route"])
        missing, _ = self.harness.run("read", "alpha", ok=False)
        self.assertEqual(missing["error"]["code"], "target_not_found")

    def test_window_names_decode_and_routes_remain_single_line(self) -> None:
        caller, _ = self.harness.launch_mock("caller-name")
        recipient, recipient_log = self.harness.launch_mock("name-recipient")
        caller_environment = self.harness.caller_environment(
            caller["target"]["pane_id"]
        )
        window_target = (
            f"{caller['target']['session']}:{caller['target']['window_index']}"
        )
        names = (
            r"bad\name",
            "bad\tname",
            "bad\nname",
            "bad\u2028name",
            "bad\u2029name",
            "bad&name",
            "bad]name",
        )
        for index, name in enumerate(names, start=1):
            with self.subTest(name=repr(name)):
                self.harness.tmux("rename-window", "-t", window_target, name)
                listed, _ = self.harness.run("list")
                item = next(
                    value
                    for value in listed["target"]["items"]
                    if value["pane_id"] == caller["target"]["pane_id"]
                )
                self.assertEqual(item["name"], name)

                read, _ = self.harness.run("read", name)
                route = read["target"]["route"]
                self.assertTrue(CONTROLLER.is_line_safe(route))
                address, _ = CONTROLLER.parse_route(route)
                expected_route_name = (
                    name
                    if CONTROLLER.is_line_safe(name)
                    else f"pane-{caller['target']['pane_id'][1:]}"
                )
                self.assertEqual(address["name"], expected_route_name)

                sent, _ = self.harness.run(
                    "send",
                    recipient["target"]["route"],
                    "--",
                    f"probe-{index}",
                    environment=caller_environment,
                )
                sender_route = sent["target"]["message"]["sender_route"]
                self.assertTrue(CONTROLLER.is_line_safe(sender_route))
                sender_address, _ = CONTROLLER.parse_route(sender_route)
                self.assertEqual(sender_address["name"], expected_route_name)
        self.assertEqual(len(self.harness.wait_for_log(recipient_log, len(names))), len(names))

    def test_split_panes_share_name_but_routes_remain_exact(self) -> None:
        first, _ = self.harness.launch_mock("shared")
        second, _ = self.harness.launch_split_mock(first["target"]["pane_id"])
        self.assertEqual(first["target"]["name"], second["target"]["name"])
        self.assertNotEqual(first["target"]["pane_id"], second["target"]["pane_id"])
        ambiguous, _ = self.harness.run("read", "shared", ok=False)
        self.assertEqual(ambiguous["error"]["code"], "target_ambiguous")
        for pane in (first["target"], second["target"]):
            read, _ = self.harness.run("read", pane["route"])
            self.assertEqual(read["target"]["pane_id"], pane["pane_id"])
        options = self.harness.tmux(
            "show-options", "-p", "-t", second["target"]["pane_id"]
        ).stdout
        self.assertNotIn("@with_agents_", options)

    def test_stale_name_process_respawn_and_server_rebuild_do_not_mismatch(self) -> None:
        launched, _ = self.harness.launch_mock("old")
        route = self.harness.route(launched["target"]["pane_id"])
        self.harness.tmux(
            "respawn-pane",
            "-k",
            "-t",
            launched["target"]["pane_id"],
            "sleep 5",
        )
        read, _ = self.harness.run("read", route)
        self.assertEqual(read["target"]["pane_id"], launched["target"]["pane_id"])

        self.harness.tmux("kill-server")
        replacement, _ = self.harness.launch_mock("replacement")
        self.assertEqual(
            replacement["target"]["pane_id"], launched["target"]["pane_id"]
        )
        read, _ = self.harness.run("read", route)
        self.assertEqual(read["target"]["name"], "replacement")

    def test_route_errors_never_fall_back_to_bare_target(self) -> None:
        self.harness.launch_mock("seed")
        malformed = [
            "with-agents:http?name=seed&pane_id=0",
            "with-agents:tmux?name=seed&pane_id=0&unknown=x",
            r"with-agents:tmux?name=seed\x&pane_id=0",
        ]
        for target in malformed:
            with self.subTest(target=target):
                payload, _ = self.harness.run("read", target, ok=False)
                self.assertEqual(payload["error"]["code"], "route_invalid")

    def test_route_keeps_a_dead_remain_on_exit_pane_observable(self) -> None:
        launched, _ = self.harness.launch_mock("finished")
        pane_id = launched["target"]["pane_id"]
        self.harness.tmux(
            "respawn-pane",
            "-k",
            "-t",
            pane_id,
            f"{shlex.quote(sys.executable)} -c 'raise SystemExit(23)'",
        )
        deadline = time.monotonic() + 2
        dead = "0"
        while time.monotonic() < deadline:
            dead = self.harness.tmux(
                "display-message", "-p", "-t", pane_id, "#{pane_dead}"
            ).stdout.strip()
            if dead == "1":
                break
            time.sleep(0.05)
        self.assertEqual(dead, "1")
        routed, _ = self.harness.run("route", pane_id)
        self.assertEqual(routed["target"]["pane_id"], pane_id)
        self.assertIn("&socket=", routed["target"]["route"])
        detailed, _ = self.harness.run("list", "--detail")
        item = next(
            value
            for value in detailed["target"]["items"]
            if value["pane_id"] == pane_id
        )
        self.assertTrue(item["dead"])

    def test_wait_covers_timeout_change_exit_and_invalid_arguments(self) -> None:
        watched, _ = self.harness.launch_mock("wait-watch")
        route = watched["target"]["route"]
        unchanged, _ = self.harness.run(
            "wait", route, "--timeout", "0", "--interval", "0.05"
        )
        self.assertEqual(unchanged["stage"], "unchanged")
        self.assertEqual(unchanged["target"]["route"], route)

        errors: list[Exception] = []

        def type_into_pane() -> None:
            try:
                time.sleep(0.75)
                self.harness.tmux(
                    "send-keys",
                    "-t",
                    watched["target"]["pane_id"],
                    "-l",
                    "screen-change",
                )
                self.harness.tmux(
                    "send-keys", "-t", watched["target"]["pane_id"], "Enter"
                )
            except Exception as exc:
                errors.append(exc)

        writer = threading.Thread(target=type_into_pane)
        writer.start()
        changed, _ = self.harness.run(
            "wait", route, "--timeout", "3", "--interval", "0.05"
        )
        writer.join()
        self.assertEqual(errors, [])
        self.assertEqual(changed["stage"], "changed")
        self.assertEqual(changed["target"]["route"], route)

        exiting, _ = self.harness.launch_mock("wait-exit")

        def close_pane() -> None:
            try:
                time.sleep(0.75)
                self.harness.tmux(
                    "kill-pane", "-t", exiting["target"]["pane_id"]
                )
            except Exception as exc:
                errors.append(exc)

        closer = threading.Thread(target=close_pane)
        closer.start()
        exited, _ = self.harness.run(
            "wait",
            exiting["target"]["route"],
            "--timeout",
            "3",
            "--interval",
            "0.05",
        )
        closer.join()
        self.assertEqual(errors, [])
        self.assertEqual(exited["stage"], "process_exit")

        invalid_cases = (
            ("--timeout", "-1"),
            ("--timeout", "nan"),
            ("--interval", "0"),
            ("--interval", "inf"),
            ("--lines", "0"),
        )
        for option, value in invalid_cases:
            with self.subTest(option=option, value=value):
                invalid, _ = self.harness.run(
                    "wait", route, option, value, ok=False
                )
                self.assertEqual(invalid["error"]["code"], "invalid_wait")


@unittest.skipUnless(shutil.which("tmux"), "tmux is required")
class MessageIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = Harness()

    def tearDown(self) -> None:
        self.harness.close()

    def test_default_header_no_header_and_text_snapshot(self) -> None:
        caller, _ = self.harness.launch_mock("caller")
        recipient, recipient_log = self.harness.launch_mock("recipient")
        environment = self.harness.caller_environment(caller["target"]["pane_id"])

        payload, _ = self.harness.run(
            "send",
            recipient["target"]["pane_id"],
            "--",
            "hello",
            environment=environment,
        )
        expected = f"[{caller['target']['route']}] hello"
        self.assertEqual(self.harness.wait_for_log(recipient_log, 1), [expected])
        self.assertTrue(payload["target"]["message"]["header"])
        self.assertEqual(
            payload["target"]["message"]["sender_route"],
            caller["target"]["route"],
        )
        self.assertEqual(payload["stage"], "submitted")
        self.assertEqual(
            set(payload["target"]["message"]),
            {"header", "sender_route", "params", "correlation_id"},
        )

        caller_window = f"{caller['target']['session']}:{caller['target']['window_index']}"
        self.harness.tmux("rename-window", "-t", caller_window, "caller-renamed")
        renamed, _ = self.harness.run(
            "send",
            recipient["target"]["pane_id"],
            "--",
            "after rename",
            environment=environment,
        )
        renamed_route = renamed["target"]["message"]["sender_route"]
        self.assertIn("name=caller-renamed", renamed_route)
        renamed_message = f"[{renamed_route}] after rename"
        self.assertEqual(
            self.harness.wait_for_log(recipient_log, 2),
            [expected, renamed_message],
        )

        self.harness.run(
            "send",
            recipient["target"]["pane_id"],
            "--no-header",
            "--",
            "/clear",
        )
        self.assertEqual(
            self.harness.wait_for_log(recipient_log, 3),
            [expected, renamed_message, "/clear"],
        )

        text = self.harness.run_text(
            "send",
            recipient["target"]["pane_id"],
            "--",
            "snapshot",
            environment=environment,
        ).stdout
        self.assertNotIn("send: submitted", text)
        self.assertIn("RECEIVED:", text)

        failure, _ = self.harness.run(
            "send", recipient["target"]["pane_id"], "--", "outside", ok=False
        )
        self.assertEqual(
            failure["error"]["code"], "caller_identity_unavailable"
        )
        self.assertIn("--no-header", failure["recovery"])

    def test_request_params_correlation_and_target_params_do_not_propagate(self) -> None:
        caller, _ = self.harness.launch_mock("caller")
        recipient, recipient_log = self.harness.launch_mock("recipient")
        environment = self.harness.caller_environment(caller["target"]["pane_id"])
        payload, _ = self.harness.run(
            "send",
            recipient["target"]["pane_id"],
            "--request",
            "--params",
            '{"scope":"api","note":"check api, tests\\nthen docs"}',
            "--",
            "review",
            environment=environment,
        )
        metadata = payload["target"]["message"]
        self.assertRegex(metadata["correlation_id"], r"^[A-Za-z0-9]{8}$")
        sender_route = metadata["sender_route"]
        _, params = CONTROLLER.parse_route(sender_route)
        self.assertEqual(params["reply"], "required")
        self.assertEqual(
            params["correlation_id"], metadata["correlation_id"]
        )
        self.assertEqual(params["scope"], "api")
        self.assertEqual(
            self.harness.wait_for_log(recipient_log, 1),
            [f"[{sender_route}] review"],
        )

        recipient_environment = self.harness.caller_environment(
            recipient["target"]["pane_id"]
        )
        self.harness.run(
            "send",
            sender_route,
            "--correlation-id",
            metadata["correlation_id"],
            "--",
            "done",
            environment=recipient_environment,
        )
        caller_log = next(self.harness.root.glob("caller-*.jsonl"))
        reply = self.harness.wait_for_log(caller_log, 1)[0]
        reply_route = reply[1 : reply.index("] ")]
        _, reply_params = CONTROLLER.parse_route(reply_route)
        self.assertEqual(
            reply_params, {"correlation_id": metadata["correlation_id"]}
        )
        self.assertTrue(reply.endswith("] done"))
        self.assertNotIn("scope", reply_route)

    def test_cross_socket_reply_and_disappeared_caller(self) -> None:
        peer_harness = Harness()
        try:
            caller, caller_log = self.harness.launch_mock("caller")
            peer, peer_log = peer_harness.launch_mock("peer")
            caller_environment = self.harness.caller_environment(
                caller["target"]["pane_id"]
            )
            peer_route = peer_harness.route(peer["target"]["pane_id"])
            sent, _ = self.harness.run(
                "send",
                peer_route,
                "--request",
                "--",
                "cross",
                environment=caller_environment,
            )
            received = peer_harness.wait_for_log(peer_log, 1)[0]
            sender_route = sent["target"]["message"]["sender_route"]
            self.assertIn(f"&socket={self.harness.socket}", sender_route)
            self.assertEqual(received, f"[{sender_route}] cross")

            peer_environment = peer_harness.caller_environment(
                peer["target"]["pane_id"]
            )
            correlation = sent["target"]["message"]["correlation_id"]
            peer_harness.run(
                "send",
                sender_route,
                "--correlation-id",
                correlation,
                "--",
                "reply",
                environment=peer_environment,
            )
            reply = self.harness.wait_for_log(caller_log, 1)[0]
            self.assertIn(f"correlation_id={correlation}", reply)
            self.assertIn(f"&socket={peer_harness.socket}", reply)

            self.harness.tmux("kill-pane", "-t", caller["target"]["pane_id"])
            failure, _ = peer_harness.run(
                "send",
                sender_route,
                "--correlation-id",
                correlation,
                "--",
                "late",
                ok=False,
                environment=peer_environment,
            )
            self.assertEqual(failure["error"]["code"], "target_not_found")
        finally:
            peer_harness.close()

    def test_long_multiline_unicode_and_concurrent_raw_sends_queue(self) -> None:
        recipient, recipient_log = self.harness.launch_mock("queue")
        messages = [
            "x" * 12000,
            "第一行\nsecond line\nemoji: 🐍",
            "-leading-dash-body",
        ]
        results: list[subprocess.CompletedProcess[str]] = []
        guard = threading.Lock()

        def send(message: str) -> None:
            completed = subprocess.run(
                self.harness.command(
                    "send",
                    recipient["target"]["pane_id"],
                    "--no-header",
                    "--",
                    message,
                ),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.harness.environment,
                timeout=20,
                check=False,
            )
            with guard:
                results.append(completed)

        threads = [
            threading.Thread(target=send, args=(message,)) for message in messages
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), len(messages))
        for completed in results:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertIsNotNone(payload["screen"])
        self.assertCountEqual(
            self.harness.wait_for_log(recipient_log, len(messages)),
            messages,
        )

    def test_target_submission_count_depends_on_bracketed_paste(self) -> None:
        for bracketed_paste, expected in (
            (True, ["single", "one\ntwo"]),
            (False, ["single", "one", "two"]),
        ):
            with self.subTest(bracketed_paste=bracketed_paste):
                recipient, log = self.harness.launch_mock(
                    f"paste-{str(bracketed_paste).lower()}",
                    bracketed_paste=bracketed_paste,
                )
                for body in ("single", "one\ntwo"):
                    self.harness.run(
                        "send",
                        recipient["target"]["route"],
                        "--no-header",
                        "--",
                        body,
                    )
                self.assertEqual(
                    self.harness.wait_for_log(log, len(expected)), expected
                )

    def test_explicit_send_to_shell_matches_direct_tmux(self) -> None:
        seed, _ = self.harness.launch_mock("seed")
        session = seed["target"]["session"]
        pane_id = self.harness.tmux(
            "new-window",
            "-d",
            "-P",
            "-F",
            "#{pane_id}",
            "-t",
            f"{session}:",
            "-n",
            "shell",
            "-c",
            str(TEST_ROOT),
        ).stdout.strip()
        payload, _ = self.harness.run(
            "send",
            pane_id,
            "--no-header",
            "--",
            "printf WA_SHELL_OK",
        )
        self.assertIn("WA_SHELL_OK", payload["screen"]["tail"])


@unittest.skipUnless(shutil.which("tmux"), "tmux is required")
class LaunchPresetAndLifecycleIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.harness = Harness()

    def tearDown(self) -> None:
        self.harness.close()

    def fixture_argv(self, log: Path) -> list[str]:
        return [
            sys.executable,
            "-u",
            str(FIXTURE),
            "--log",
            str(log),
        ]

    def test_launch_observation_reports_stable_screen_without_ready_claim(self) -> None:
        def assert_compact_launch_target(payload: dict) -> None:
            self.assertEqual(
                set(payload["target"]),
                {
                    "kind",
                    "pane_id",
                    "name",
                    "session",
                    "window_index",
                    "pane_index",
                    "session_window_pane",
                    "process",
                    "cwd",
                    "title",
                    "route",
                    "launch",
                },
            )
            self.assertEqual(set(payload["target"]["launch"]), {"observation"})

        slow, _ = self.harness.launch_mock("slow", startup_delay=0.35)
        assert_compact_launch_target(slow)
        observation = slow["target"]["launch"]["observation"]
        self.assertEqual(
            observation,
            {"waited": True, "material_change": True, "stable": True},
        )
        self.assertIn("MOCK_READY", slow["screen"]["tail"])
        self.assertNotIn("readiness", slow["target"])

        danger, _ = self.harness.launch_mock("permission", mode="danger")
        self.assertTrue(danger["target"]["launch"]["observation"]["stable"])
        self.assertIn("Allow destructive action?", danger["screen"]["tail"])

        exited, _ = self.harness.run(
            "launch",
            "--name",
            "blank-exit",
            "--ready-timeout",
            "1",
            "--",
            sys.executable,
            "-c",
            "raise SystemExit(7)",
            ok=False,
        )
        self.assertEqual(exited["error"]["code"], "launch_process_exited")
        self.assertEqual(exited["stage"], "process_exited")
        assert_compact_launch_target(exited)

        blank, _ = self.harness.run(
            "launch",
            "--name",
            "blank",
            "--ready-timeout",
            "0.35",
            "--",
            sys.executable,
            "-c",
            "import time; time.sleep(3)",
            ok=False,
        )
        self.assertEqual(blank["error"]["code"], "launch_timeout")
        assert_compact_launch_target(blank)
        self.assertFalse(
            blank["target"]["launch"]["observation"]["material_change"]
        )

        animation_code = (
            "import sys,time\n"
            "n=0\n"
            "while True:\n"
            " sys.stdout.write(str(n)+'\\r'); sys.stdout.flush(); "
            "n+=1; time.sleep(.04)"
        )
        animated, _ = self.harness.run(
            "launch",
            "--name",
            "animated",
            "--ready-timeout",
            "0.5",
            "--",
            sys.executable,
            "-u",
            "-c",
            animation_code,
        )
        self.assertTrue(
            animated["target"]["launch"]["observation"]["material_change"]
        )
        self.assertFalse(
            animated["target"]["launch"]["observation"]["stable"]
        )

        no_wait, _ = self.harness.launch_mock("no-wait", no_wait=True)
        self.assertEqual(
            no_wait["target"]["launch"]["observation"]["waited"], False
        )
        self.assertIsNone(
            no_wait["target"]["launch"]["observation"]["stable"]
        )

        text_result = self.harness.run_text(
            "launch",
            "--name",
            "text-shape",
            "--ready-timeout",
            "1",
            "--",
            sys.executable,
            "-u",
            "-c",
            "print('TEXT_READY'); import time; time.sleep(2)",
        )
        self.assertNotIn("argv=", text_result.stdout)
        self.assertIn("launch_observation=", text_result.stdout)

    def test_explicit_preset_save_optional_name_generation_and_update(self) -> None:
        fixed_log = self.harness.root / "fixed.jsonl"
        saved, _ = self.harness.run(
            "preset",
            "save",
            "fixed",
            "--agent-type",
            "codex",
            "--pane-name",
            "fixed-pane",
            "--",
            *self.fixture_argv(fixed_log),
        )
        self.assertEqual(saved["target"]["agent_type"], "codex")
        self.assertEqual(saved["target"]["pane_name"], "fixed-pane")
        self.assertNotIn("cwd", saved["target"])
        fixed, _ = self.harness.run(
            "launch",
            "--preset",
            "fixed",
            "--ready-timeout",
            "4",
        )
        self.assertEqual(fixed["target"]["name"], "fixed-pane")

        auto_log = self.harness.root / "auto.jsonl"
        self.harness.run(
            "preset",
            "save",
            "auto",
            "--agent-type",
            "codex",
            "--",
            *self.fixture_argv(auto_log),
        )
        auto, _ = self.harness.run(
            "launch",
            "--preset",
            "auto",
            "--ready-timeout",
            "4",
        )
        self.assertRegex(auto["target"]["name"], r"^cx-[0-9]{4}$")
        suffixed, _ = self.harness.run(
            "launch",
            "--preset",
            "auto",
            "--name-suffix",
            "a1",
            "--ready-timeout",
            "4",
        )
        self.assertEqual(suffixed["target"]["name"], "cx-a1")

        failure, _ = self.harness.run(
            "preset",
            "update",
            "auto",
            "--agent-type",
            "pi",
            "--",
            *self.fixture_argv(auto_log),
            ok=False,
        )
        self.assertEqual(failure["error"]["code"], "replace_required")
        updated, _ = self.harness.run(
            "preset",
            "update",
            "auto",
            "--replace",
            "--agent-type",
            "pi",
            "--",
            *self.fixture_argv(auto_log),
        )
        self.assertEqual(updated["target"]["agent_type"], "pi")

    def test_split_name_conflicts_fail_before_creation(self) -> None:
        first, _ = self.harness.launch_mock("base")
        before, _ = self.harness.run("list")
        failure, _ = self.harness.run(
            "launch",
            "--split",
            first["target"]["pane_id"],
            "--name",
            "forbidden",
            "--",
            sys.executable,
            "-c",
            "print('never')",
            ok=False,
        )
        self.assertEqual(failure["error"]["code"], "pane_name_source_conflict")
        after, _ = self.harness.run("list")
        self.assertEqual(
            len(before["target"]["items"]), len(after["target"]["items"])
        )

    def test_split_revalidation_rejects_a_dead_target(self) -> None:
        target, _ = self.harness.launch_mock("dead-split-target")
        pane_id = target["target"]["pane_id"]
        self.harness.tmux(
            "respawn-pane",
            "-k",
            "-t",
            pane_id,
            f"{shlex.quote(sys.executable)} -c 'raise SystemExit(9)'",
        )
        deadline = time.monotonic() + 2
        dead = "0"
        while time.monotonic() < deadline:
            dead = self.harness.tmux(
                "display-message", "-p", "-t", pane_id, "#{pane_dead}"
            ).stdout.strip()
            if dead == "1":
                break
            time.sleep(0.05)
        self.assertEqual(dead, "1")
        before, _ = self.harness.run("list")
        failure, _ = self.harness.run(
            "launch",
            "--split",
            target["target"]["route"],
            "--",
            sys.executable,
            "-c",
            "print('must not launch')",
            ok=False,
        )
        self.assertEqual(failure["error"]["code"], "target_process_exited")
        after, _ = self.harness.run("list")
        self.assertEqual(
            len(before["target"]["items"]), len(after["target"]["items"])
        )

    def test_key_and_close_work_on_hand_created_non_self_pane(self) -> None:
        seed, _ = self.harness.launch_mock("seed")
        log = self.harness.root / "manual.jsonl"
        command = shlex.join(self.fixture_argv(log))
        pane_id = self.harness.tmux(
            "new-window",
            "-d",
            "-P",
            "-F",
            "#{pane_id}",
            "-t",
            f"{seed['target']['session']}:",
            "-n",
            "manual",
            command,
        ).stdout.strip()
        time.sleep(0.2)
        self.harness.run("key", pane_id, "--", "h", "i", "Enter")
        self.assertEqual(self.harness.wait_for_log(log, 1), ["hi"])
        closed, _ = self.harness.run("close", pane_id)
        self.assertEqual(closed["stage"], "closed")

    def test_config_rejects_removed_executables_field(self) -> None:
        self.harness.config.mkdir(mode=0o700, exist_ok=True)
        (self.harness.config / "config.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "agents": {
                        "codex": {
                            "pane_prefix": "cx",
                            "executables": ["codex"],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        invalid, _ = self.harness.run("doctor", ok=False)
        self.assertEqual(
            invalid["target"]["checks"]["agent_config"]["error"]["code"],
            "invalid_agent_config",
        )

    def test_file_roots_return_stable_errors_in_commands_and_doctor(self) -> None:
        target, target_log = self.harness.launch_mock("bad-roots-target")

        def assert_runtime_error(path: Path) -> None:
            failed_send, _ = self.harness.run(
                "send",
                target["target"]["route"],
                "--no-header",
                "--",
                "must-not-land",
                ok=False,
                runtime=path,
            )
            self.assertEqual(failed_send["error"]["code"], "unsafe_state_path")
            runtime_doctor, _ = self.harness.run(
                "doctor", ok=False, runtime=path
            )
            self.assertEqual(
                runtime_doctor["target"]["checks"]["runtime"]["error"]["code"],
                "unsafe_state_path",
            )

        def assert_config_error(path: Path) -> None:
            failed_preset, _ = self.harness.run(
                "preset", "list", ok=False, config=path
            )
            self.assertEqual(
                failed_preset["error"]["code"], "unsafe_state_path"
            )
            config_doctor, _ = self.harness.run(
                "doctor", ok=False, config=path
            )
            self.assertEqual(
                config_doctor["target"]["checks"]["agent_config"]["error"][
                    "code"
                ],
                "invalid_agent_config",
            )

        bad_runtime = self.harness.root / "runtime-file"
        bad_runtime.write_text("not a directory", encoding="utf-8")
        bad_config = self.harness.root / "config-file"
        bad_config.write_text("not a directory", encoding="utf-8")
        assert_runtime_error(bad_runtime)
        assert_config_error(bad_config)

        runtime_link = self.harness.root / "runtime-link"
        runtime_link.symlink_to(self.harness.root)
        config_link = self.harness.root / "config-link"
        config_link.symlink_to(self.harness.root)
        assert_runtime_error(runtime_link)
        assert_config_error(config_link)

        if os.geteuid() != 0:
            blocked = self.harness.root / "blocked"
            blocked.mkdir(mode=0o700)
            blocked.chmod(0)
            try:
                assert_runtime_error(blocked / "runtime")
                assert_config_error(blocked / "config")
            finally:
                blocked.chmod(0o700)

        self.assertEqual(self.harness.read_log(target_log), [])


@unittest.skipUnless(shutil.which("tmux"), "tmux is required")
class CrossSocketSelfTargetTests(unittest.TestCase):
    def test_recovery_sequence_stays_on_the_explicit_socket(self) -> None:
        local_harness = Harness()
        recovery_harness = Harness()
        try:
            local, _ = local_harness.launch_mock("recovery-local")
            remote, remote_log = recovery_harness.launch_mock("recovery-remote")
            self.assertEqual(local["target"]["pane_id"], remote["target"]["pane_id"])

            def raw_tmux(
                *arguments: str, input_text: str | None = None
            ) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    ["tmux", "-S", str(recovery_harness.socket), *arguments],
                    input=input_text,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=True,
                )

            listed = raw_tmux("list-panes", "-a", "-F", "#{pane_id}").stdout
            self.assertEqual(listed.strip(), remote["target"]["pane_id"])
            raw_tmux(
                "capture-pane",
                "-p",
                "-J",
                "-t",
                remote["target"]["pane_id"],
                "-S",
                "-40",
            )
            buffer_name = f"with-agents-recovery-{uuid.uuid4().hex}"
            raw_tmux(
                "load-buffer",
                "-b",
                buffer_name,
                "-",
                input_text="recovery-message",
            )
            raw_tmux(
                "paste-buffer",
                "-p",
                "-b",
                buffer_name,
                "-d",
                "-t",
                remote["target"]["pane_id"],
            )
            raw_tmux("send-keys", "-t", remote["target"]["pane_id"], "Enter")
            self.assertEqual(
                recovery_harness.wait_for_log(remote_log, 1),
                ["recovery-message"],
            )
            raw_tmux("kill-pane", "-t", remote["target"]["pane_id"])

            local_read, _ = local_harness.run("read", local["target"]["route"])
            self.assertEqual(local_read["target"]["name"], "recovery-local")
        finally:
            local_harness.close()
            recovery_harness.close()

    def test_returned_routes_keep_the_remote_socket_across_commands(self) -> None:
        caller_harness = Harness()
        target_harness = Harness()
        try:
            local, _ = caller_harness.launch_mock("local-side")
            remote, remote_log = target_harness.launch_mock("remote-side")
            self.assertEqual(local["target"]["pane_id"], remote["target"]["pane_id"])

            def remote_route(payload: dict) -> str:
                route = payload["target"]["route"]
                address, _ = CONTROLLER.parse_route(route)
                self.assertEqual(
                    address["socket_path"], os.path.realpath(target_harness.socket)
                )
                return route

            current = remote_route(remote)
            read, _ = caller_harness.run("read", current)
            current = remote_route(read)
            sent, _ = caller_harness.run(
                "send", current, "--no-header", "--", "remote-send"
            )
            current = remote_route(sent)
            keyed, _ = caller_harness.run(
                "key", current, "--", "r", "e", "m", "o", "t", "e", "Enter"
            )
            current = remote_route(keyed)
            waited, _ = caller_harness.run(
                "wait", current, "--timeout", "0", "--interval", "0.05"
            )
            current = remote_route(waited)
            closed, _ = caller_harness.run("close", current)
            remote_route(closed)

            self.assertEqual(
                target_harness.wait_for_log(remote_log, 2),
                ["remote-send", "remote"],
            )
            still_local, _ = caller_harness.run("read", local["target"]["route"])
            self.assertEqual(still_local["target"]["name"], "local-side")
        finally:
            caller_harness.close()
            target_harness.close()

    def test_comma_socket_preserves_caller_identity_and_self_target_stop(self) -> None:
        harness = Harness(socket_name="tmux,comma.sock")
        try:
            caller, _ = harness.launch_mock("comma-caller")
            recipient, recipient_log = harness.launch_mock("comma-recipient")
            environment = harness.caller_environment(caller["target"]["pane_id"])

            listed, _ = harness.run(
                "list", environment=environment, include_socket=False
            )
            self.assertEqual(len(listed["target"]["items"]), 2)
            self.assertTrue(
                all(
                    f"&socket={harness.socket}" in item["route"]
                    for item in listed["target"]["items"]
                )
            )
            routed, _ = harness.run(
                "route", environment=environment, include_socket=False
            )
            self.assertEqual(routed["target"]["route"], caller["target"]["route"])

            sent, _ = harness.run(
                "send",
                recipient["target"]["route"],
                "--",
                "comma-header",
                environment=environment,
            )
            sender_route = sent["target"]["message"]["sender_route"]
            self.assertEqual(sender_route, caller["target"]["route"])
            self.assertEqual(
                harness.wait_for_log(recipient_log, 1),
                [f"[{sender_route}] comma-header"],
            )

            for action, extra in (
                ("send", ("--no-header", "--", "self")),
                ("key", ("--", "Enter")),
                ("close", ()),
            ):
                with self.subTest(action=action):
                    denied, _ = harness.run(
                        action,
                        caller["target"]["route"],
                        *extra,
                        ok=False,
                        environment=environment,
                    )
                    self.assertEqual(
                        denied["error"]["code"], "self_target_denied"
                    )
        finally:
            harness.close()

    def test_same_pane_id_on_another_socket_is_allowed_but_real_self_is_denied(
        self,
    ) -> None:
        caller_harness = Harness()
        target_harness = Harness()
        try:
            caller, _ = caller_harness.launch_mock("caller")
            target, target_log = target_harness.launch_mock("target")
            self.assertEqual(caller["target"]["pane_id"], target["target"]["pane_id"])
            caller_environment = caller_harness.caller_environment(
                caller["target"]["pane_id"]
            )
            target_route = target_harness.route(target["target"]["pane_id"])
            completed = subprocess.run(
                target_harness.command(
                    "send",
                    target_route,
                    "--no-header",
                    "--",
                    "cross-server",
                ),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=caller_environment,
                timeout=20,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                target_harness.wait_for_log(target_log, 1), ["cross-server"]
            )

            denied, _ = caller_harness.run(
                "send",
                caller["target"]["route"],
                "--no-header",
                "--",
                "self",
                ok=False,
                environment=caller_environment,
            )
            self.assertEqual(denied["error"]["code"], "self_target_denied")
            for action, extra in (
                ("key", ("--", "Enter")),
                ("close", ()),
            ):
                with self.subTest(action=action):
                    denied, _ = caller_harness.run(
                        action,
                        caller["target"]["route"],
                        *extra,
                        ok=False,
                        environment=caller_environment,
                    )
                    self.assertEqual(
                        denied["error"]["code"], "self_target_denied"
                    )
            for action in ("read", "route"):
                with self.subTest(action=action):
                    observed, _ = caller_harness.run(
                        action,
                        caller["target"]["route"],
                        environment=caller_environment,
                    )
                    self.assertTrue(observed["ok"])
        finally:
            caller_harness.close()
            target_harness.close()


if __name__ == "__main__":
    unittest.main()
