"""Standard-library safety tests. Synthetic data only; real subprocess calls are blocked."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("tvctl", Path(__file__).resolve().parents[1] / "tools/tvctl.py")
tvctl = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tvctl)


class FakeAdb:
    def __init__(self):
        self.raw_identity = "synthetic-device-token-0001"
        self.settings = {
            ("global", "boot_count"): "7",
            tvctl.GLOBAL_ACCESSIBILITY: "1",
            tvctl.SERVICES: "org.example.reader/.Service:org.example.guard/.Service:org.example.voice/.Service",
        }
        self.calls = []
        self.ignore_writes = False
        self.global_side_effect = False
        self.before_write = None
        self.unavailable = set()
        self.input_dump = "InputFilterEnabled: false\nUnrelated private input metadata"

    def shell(self, *args):
        self.calls.append(args)
        if args in self.unavailable:
            raise tvctl.OperationError("adb_command_failed")
        if args[0] == "getprop":
            return self.raw_identity if args[1] == "ro.serialno" else ""
        if args[:3] == ("settings", "--user", "0"):
            action, namespace, key = args[3:6]
            target = (namespace, key)
            if action == "get":
                return self.settings.get(target, "null")
            if action not in {"put", "delete"}:
                raise AssertionError("Unexpected settings command")
            if self.before_write:
                self.before_write()
            if not self.ignore_writes:
                if action == "delete":
                    self.settings.pop(target, None)
                else:
                    self.settings[target] = args[6]
                if target == tvctl.SERVICES and self.global_side_effect:
                    self.settings[tvctl.GLOBAL_ACCESSIBILITY] = "0"
            return ""
        if args == ("cat", "/proc/uptime"):
            return "123.45 800.00"
        if args == ("dumpsys", "power"):
            return "mWakefulness=Awake\nmInteractive=true\nDisplay Power: state=ON\nUnrelated private wakelock"
        if args == ("dumpsys", "window"):
            return "Unrelated private window title\nmCurrentFocus=Window{private-id u0 org.example.player/.Playback}\nOther private UI"
        if args == ("dumpsys", "input"):
            return self.input_dump
        raise AssertionError("Unexpected or forbidden device command: " + repr(args))

    def writes(self):
        return [args for args in self.calls if args[:4] in {
            ("settings", "--user", "0", "put"), ("settings", "--user", "0", "delete")}]


class TvctlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.state = self.directory / "private-state"
        self.fake = FakeAdb()
        self.adb_class = tvctl.Adb
        self.stack = contextlib.ExitStack()
        self.stack.enter_context(patch.object(subprocess, "run", side_effect=AssertionError("Real subprocess forbidden")))
        self.stack.enter_context(patch.object(tvctl, "Adb", return_value=self.fake))

    def tearDown(self):
        self.stack.close()
        self.temp.cleanup()

    def invoke(self, arguments, live=True):
        output = io.StringIO()
        args = [arguments[0], "--serial", "DEVICE_PLACEHOLDER", *arguments[1:]]
        if live:
            args += ["--state-dir", str(self.state)]
        with contextlib.redirect_stdout(output):
            code = tvctl.main(args)
        text = output.getvalue()
        self.assertNotIn("DEVICE_PLACEHOLDER", text)
        self.assertNotIn(self.fake.raw_identity, text)
        self.assertNotIn(str(self.directory), text)
        return code, json.loads(text)

    def startup(self, *extra):
        return self.invoke(["set-startup", "--package", "org.example.launcher", "--vendor-profile", "xiaomi", *extra])

    def backup_from(self, output):
        path = self.state / output["backup_file"]
        return path, json.loads(path.read_text(encoding="utf-8"))

    def report_from(self, output):
        return json.loads((self.state / output["report_file"]).read_text(encoding="utf-8"))

    def test_every_default_operation_is_offline_without_files_or_adb(self):
        commands = [
            ["snapshot"],
            ["set-startup", "--package", "org.example.launcher", "--vendor-profile", "xiaomi"],
            ["standby-preserve", "--vendor-profile", "xiaomi"],
            ["retire-guard", "--component", "org.example.guard/.Service"],
            ["restore", "--backup", str(self.directory / "does-not-exist.json")],
        ]
        with patch.object(tvctl, "Adb", side_effect=AssertionError("No device construction")), \
                patch.object(tvctl, "StateStore", side_effect=AssertionError("No state creation")):
            for command in commands:
                with self.subTest(command=command[0]):
                    code, result = self.invoke(command, live=False)
                    self.assertEqual(code, 0)
                    self.assertEqual(result["mode"], "offline")
                    self.assertFalse(result["device_access"])
        self.assertEqual(self.fake.calls, [])
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_serial_is_mandatory_and_has_no_default(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            tvctl.main(["snapshot"])
        self.assertEqual(self.fake.calls, [])

    def test_live_access_requires_explicit_private_state_directory(self):
        code, result = self.invoke(["snapshot", "--inspect"], live=False)
        self.assertEqual((code, result["error"]), (1, "explicit_private_state_directory_required"))
        self.assertEqual(self.fake.calls, [])

    def test_firmware_operations_require_explicit_adapter_and_confirmation(self):
        for command in (["set-startup", "--package", "org.example.launcher", "--apply"],
                        ["standby-preserve", "--apply", "--evidence-confirmed"],
                        ["standby-preserve", "--apply", "--vendor-profile", "xiaomi"],
                        ["snapshot", "--apply"]):
            with self.subTest(command=command):
                code, _ = self.invoke(command)
                self.assertEqual(code, 1)
        self.assertEqual(self.fake.calls, [])
        self.assertFalse(self.state.exists())

    def test_snapshot_is_structured_and_never_persists_full_dumps(self):
        code, result = self.invoke(["snapshot", "--inspect"])
        self.assertEqual(code, 0)
        self.assertEqual(result["snapshot"]["boot_count"], 7)
        self.assertEqual(result["snapshot"]["uptime_seconds"], 123.45)
        self.assertEqual(result["snapshot"]["focus_component"], "org.example.player/.Playback")
        self.assertFalse(result["snapshot"]["input_filter_enabled"])
        self.assertEqual(result["snapshot"]["power"]["wakefulness"], "awake")
        self.assertTrue(tvctl.valid_identity(result["device"]))
        contents = (self.state / result["report_file"]).read_text(encoding="utf-8")
        for private in (self.fake.raw_identity, "DEVICE_PLACEHOLDER", "Unrelated private", "Other private", "private-id"):
            self.assertNotIn(private, contents)
        self.assertEqual(self.fake.writes(), [])
        self.assertFalse(any(call[0] in {"logcat", "input", "am", "pm", "reboot"} for call in self.fake.calls))

    def test_unknown_and_unavailable_snapshot_values_remain_unknown(self):
        self.fake.input_dump = "No recognized filter field"
        self.fake.unavailable.add(("dumpsys", "power"))
        code, result = self.invoke(["snapshot", "--inspect"])
        self.assertEqual(code, 0)
        self.assertIsNone(result["snapshot"]["input_filter_enabled"])
        self.assertIsNone(result["snapshot"]["power"])
        self.assertIn("power", result["snapshot"]["unavailable"])
        self.assertIn("input_filter_enabled", result["snapshot"]["unavailable"])

    def test_invalid_adb_encoding_returns_safe_error_without_device_writes(self):
        secret = b"SYNTHETIC_PRIVATE_VALUE\xff"
        private_path = "/".join(("", "synthetic-private-location", "trace.txt"))
        decoding_error = UnicodeDecodeError("utf-8", secret, len(secret) - 1, len(secret), private_path)
        adb = self.adb_class("adb", "DEVICE_PLACEHOLDER")
        with patch.object(tvctl, "Adb", return_value=adb), \
                patch.object(subprocess, "run", side_effect=decoding_error) as run:
            code, result = self.invoke(["snapshot", "--inspect"])
        self.assertEqual((code, result["error"]), (1, "adb_output_decode_failed"))
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertEqual(command, ["adb", "-s", "DEVICE_PLACEHOLDER", "shell", "getprop ro.serialno"])
        self.assertNotIn("errors", run.call_args.kwargs)
        report = self.report_from(result)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["write_attempted"])
        recorded = json.dumps(result) + json.dumps(report)
        for private in ("SYNTHETIC_PRIVATE_VALUE", private_path, "Traceback", "UnicodeDecodeError"):
            self.assertNotIn(private, recorded)
        self.assertEqual(list(self.state.glob("backup-*.json")), [])

    def test_inspect_setting_operations_never_write_or_make_restore_backups(self):
        for args in (["set-startup", "--package", "org.example.launcher", "--vendor-profile", "xiaomi", "--inspect"],
                     ["standby-preserve", "--vendor-profile", "xiaomi", "--inspect"],
                     ["retire-guard", "--component", "org.example.guard/.Service", "--inspect"]):
            code, result = self.invoke(args)
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "inspected")
        self.assertEqual(self.fake.writes(), [])
        self.assertEqual(list(self.state.glob("backup-*.json")), [])

    def test_startup_apply_persists_private_backup_before_its_only_write(self):
        def before_write():
            backups = list(self.state.glob("backup-*.json"))
            self.assertEqual(len(backups), 1)
            data = json.loads(backups[0].read_text(encoding="utf-8"))
            self.assertIsNone(data["changes"][0]["before"])
            self.assertEqual(data["changes"][0]["after"], "org.example.launcher")
        self.fake.before_write = before_write
        code, result = self.startup("--apply")
        self.assertEqual((code, result["status"]), (0, "applied"))
        self.assertEqual(self.fake.writes(), [("settings", "--user", "0", "put", "system", "start_3rd_app", "org.example.launcher")])
        path, backup = self.backup_from(result)
        self.assertEqual(tvctl.validate_backup(backup), backup)
        self.assertNotIn(self.fake.raw_identity, path.read_text(encoding="utf-8"))
        self.assertNotIn("DEVICE_PLACEHOLDER", path.read_text(encoding="utf-8"))

    def test_standby_apply_changes_only_the_confirmed_profile_key(self):
        before = dict(self.fake.settings)
        code, result = self.invoke(["standby-preserve", "--vendor-profile", "xiaomi", "--evidence-confirmed", "--apply"])
        self.assertEqual((code, result["status"]), (0, "applied"))
        before[tvctl.STANDBY] = "disable"
        self.assertEqual(self.fake.settings, before)
        _, backup = self.backup_from(result)
        self.assertTrue(backup["parameters"]["evidence_confirmed"])

    def test_retirement_preserves_other_components_order_and_global_switch(self):
        for global_value in ("0", "1", None):
            with self.subTest(global_value=global_value):
                self.fake.calls.clear()
                self.fake.settings[tvctl.SERVICES] = "org.example.reader/.Service:org.example.guard/.Service:org.example.voice/.Service:org.example.guard/org.example.guard.Service"
                if global_value is None:
                    self.fake.settings.pop(tvctl.GLOBAL_ACCESSIBILITY, None)
                else:
                    self.fake.settings[tvctl.GLOBAL_ACCESSIBILITY] = global_value
                code, result = self.invoke(["retire-guard", "--component", "org.example.guard/.Service", "--apply"])
                self.assertEqual((code, result["status"]), (0, "applied"))
                self.assertEqual(self.fake.settings[tvctl.SERVICES], "org.example.reader/.Service:org.example.voice/.Service")
                self.assertEqual(self.fake.settings.get(tvctl.GLOBAL_ACCESSIBILITY), global_value)
                self.assertEqual(len(self.fake.writes()), 1)
                self.assertEqual(self.fake.writes()[0][4:6], tvctl.SERVICES)

    def test_retirement_global_side_effect_is_failure_without_automatic_rollback(self):
        self.fake.global_side_effect = True
        code, result = self.invoke(["retire-guard", "--component", "org.example.guard/.Service", "--apply"])
        self.assertEqual((code, result["error"]), (1, "write_verification_failed"))
        report = self.report_from(result)
        self.assertFalse(report["global_accessibility_preserved"])
        self.assertEqual(len(self.fake.writes()), 1)

    def test_write_readback_failure_leaves_backup_and_stops(self):
        self.fake.ignore_writes = True
        code, result = self.startup("--apply")
        self.assertEqual((code, result["error"]), (1, "write_verification_failed"))
        self.assertTrue((self.state / result["backup_file"]).is_file())
        self.assertEqual(self.report_from(result)["status"], "failed")
        self.assertEqual(len(self.fake.writes()), 1)

    def test_backup_failure_prevents_all_device_writes(self):
        with patch.object(tvctl.StateStore, "save", side_effect=tvctl.OperationError("private_state_write_failed")):
            code, result = self.startup("--apply")
        self.assertEqual(code, 1)
        self.assertFalse(result["report_saved"])
        self.assertEqual(self.fake.writes(), [])

    def test_observed_concurrent_change_is_preserved(self):
        original = tvctl.StateStore.save
        def save(store, kind, payload):
            name = original(store, kind, payload)
            if kind == "backup":
                self.fake.settings[tvctl.STARTUP] = "org.example.newchoice"
            return name
        with patch.object(tvctl.StateStore, "save", new=save):
            code, result = self.startup("--apply")
        self.assertEqual((code, result["status"]), (0, "preserved-concurrent-change"))
        self.assertEqual(self.fake.writes(), [])
        self.assertEqual(self.fake.settings[tvctl.STARTUP], "org.example.newchoice")

    def test_restore_verifies_identity_before_any_setting_access(self):
        _, output = self.startup("--apply")
        path, backup = self.backup_from(output)
        self.fake.raw_identity = "synthetic-different-device"
        self.fake.calls.clear()
        code, result = self.invoke(["restore", "--backup", str(path), "--apply"])
        self.assertEqual((code, result["error"]), (1, "backup_device_identity_mismatch"))
        self.assertEqual(self.fake.writes(), [])
        self.assertFalse(any(call[0] == "settings" for call in self.fake.calls))
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), backup)

    def test_restore_deletes_originally_missing_key_and_preserves_backup(self):
        _, output = self.startup("--apply")
        path, _ = self.backup_from(output)
        before_bytes = path.read_bytes()
        self.fake.calls.clear()
        code, result = self.invoke(["restore", "--backup", str(path), "--apply"])
        self.assertEqual((code, result["status"]), (0, "restored"))
        self.assertNotIn(tvctl.STARTUP, self.fake.settings)
        self.assertEqual(self.fake.writes(), [("settings", "--user", "0", "delete", "system", "start_3rd_app")])
        self.assertEqual(path.read_bytes(), before_bytes)

    def test_restore_preserves_later_user_values_and_inspect_is_read_only(self):
        self.fake.settings[tvctl.STARTUP] = "org.example.original"
        _, output = self.startup("--apply")
        path, _ = self.backup_from(output)
        self.fake.calls.clear()
        code, result = self.invoke(["restore", "--backup", str(path), "--inspect"])
        self.assertEqual((code, result["status"]), (0, "would-restore"))
        self.assertEqual(self.fake.writes(), [])
        self.fake.settings[tvctl.STARTUP] = "org.example.userchoice"
        code, result = self.invoke(["restore", "--backup", str(path), "--apply"])
        self.assertEqual((code, result["status"]), (0, "preserved-later-change"))
        self.assertEqual(self.fake.settings[tvctl.STARTUP], "org.example.userchoice")
        self.assertEqual(self.fake.writes(), [])

    def test_restore_writes_original_existing_value(self):
        self.fake.settings[tvctl.STARTUP] = "org.example.original"
        _, output = self.startup("--apply")
        path, _ = self.backup_from(output)
        self.fake.calls.clear()
        code, result = self.invoke(["restore", "--backup", str(path), "--apply"])
        self.assertEqual((code, result["status"]), (0, "restored"))
        self.assertEqual(self.fake.settings[tvctl.STARTUP], "org.example.original")

    def test_guard_restore_preserves_a_later_global_switch_choice(self):
        original_services = self.fake.settings[tvctl.SERVICES]
        _, output = self.invoke(["retire-guard", "--component", "org.example.guard/.Service", "--apply"])
        path, _ = self.backup_from(output)
        self.fake.settings[tvctl.GLOBAL_ACCESSIBILITY] = "0"
        self.fake.calls.clear()
        code, result = self.invoke(["restore", "--backup", str(path), "--apply"])
        self.assertEqual((code, result["status"]), (0, "restored"))
        self.assertEqual(self.fake.settings[tvctl.SERVICES], original_services)
        self.assertEqual(self.fake.settings[tvctl.GLOBAL_ACCESSIBILITY], "0")
        self.assertEqual(len(self.fake.writes()), 1)
        self.assertEqual(self.fake.writes()[0][4:6], tvctl.SERVICES)

    def test_guard_restore_preserves_later_service_list_changes(self):
        _, output = self.invoke(["retire-guard", "--component", "org.example.guard/.Service", "--apply"])
        path, _ = self.backup_from(output)
        self.fake.settings[tvctl.SERVICES] += ":org.example.newreader/.Service"
        expected = self.fake.settings[tvctl.SERVICES]
        self.fake.calls.clear()
        code, result = self.invoke(["restore", "--backup", str(path), "--apply"])
        self.assertEqual((code, result["status"]), (0, "preserved-later-change"))
        self.assertEqual(self.fake.settings[tvctl.SERVICES], expected)
        self.assertEqual(self.fake.writes(), [])

    def test_missing_identity_prevents_setting_mutations(self):
        self.fake.raw_identity = ""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = tvctl.main(["set-startup", "--serial", "DEVICE_PLACEHOLDER", "--state-dir", str(self.state),
                               "--package", "org.example.launcher", "--vendor-profile", "xiaomi", "--apply"])
        result = json.loads(output.getvalue())
        self.assertEqual((code, result["error"]), (1, "stable_device_identity_unavailable"))
        self.assertEqual(self.fake.writes(), [])
        self.assertEqual(list(self.state.glob("backup-*.json")), [])

    def test_invalid_backup_scope_is_rejected_before_device_access(self):
        _, output = self.startup("--apply")
        path, backup = self.backup_from(output)
        backup["changes"][0]["key"] = "unrelated_setting"
        path.write_text(json.dumps(backup), encoding="utf-8")
        self.fake.calls.clear()
        code, result = self.invoke(["restore", "--backup", str(path), "--apply"])
        self.assertEqual(code, 1)
        self.assertEqual(result["error"], "unsupported_or_inconsistent_backup_scope")
        self.assertEqual(self.fake.calls, [])

    def test_backups_and_reports_have_unique_names_and_do_not_overwrite(self):
        _, first = self.startup("--apply")
        path, _ = self.backup_from(first)
        content = path.read_bytes()
        _, second = self.startup("--apply")
        self.assertNotEqual(first["backup_file"], second["backup_file"])
        self.assertNotEqual(first["report_file"], second["report_file"])
        self.assertEqual(path.read_bytes(), content)

    def test_nested_skill_cannot_write_to_itself_or_outer_kit(self):
        kit = self.directory / "portable-project"
        skill = kit / "nested" / "portable-skill"
        (skill / "scripts").mkdir(parents=True)
        (kit / "kit.json").write_text("{}", encoding="utf-8")
        (skill / "SKILL.md").write_text("synthetic marker", encoding="utf-8")
        script = skill / "scripts" / "tvctl.py"
        for target in (kit, kit / "private", skill / "state", skill / "scripts"):
            with self.subTest(target=target.name), self.assertRaises(tvctl.OperationError):
                tvctl.external_directory(target, script)
        self.assertEqual(tvctl.external_directory(self.state, script), self.state.resolve())

    def test_unmarked_script_project_and_separate_marked_tree_are_protected(self):
        project = self.directory / "plain-project"
        script = project / "tools" / "tvctl.py"
        with self.assertRaises(tvctl.OperationError):
            tvctl.external_directory(project / "state", script)
        other = self.directory / "another-shareable-skill"
        other.mkdir()
        (other / "SKILL.md").write_text("synthetic marker", encoding="utf-8")
        with self.assertRaises(tvctl.OperationError):
            tvctl.external_directory(other / "state", script)

    def test_symlink_into_shareable_tree_is_rejected(self):
        kit = self.directory / "shareable"
        kit.mkdir()
        (kit / "kit.json").write_text("{}", encoding="utf-8")
        link = self.directory / "apparently-private"
        try:
            link.symlink_to(kit, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Host does not allow creating symlinks")
        with self.assertRaises(tvctl.OperationError):
            tvctl.external_directory(link / "state")


if __name__ == "__main__":
    unittest.main()
