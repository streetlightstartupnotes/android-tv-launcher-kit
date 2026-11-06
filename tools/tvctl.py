#!/usr/bin/env python3
"""Small, explicit Android TV maintenance operations. The default is an offline JSON plan."""
import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import uuid

SCHEMA_VERSION = 1
TOOL = "android-tv-launcher-kit.tvctl"
STARTUP = ("system", "start_3rd_app")
STANDBY = ("global", "disable_back_home_whitelist")
SERVICES = ("secure", "enabled_accessibility_services")
GLOBAL_ACCESSIBILITY = ("secure", "accessibility_enabled")
PACKAGE_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+")
COMPONENT_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)/([A-Za-z_.$][A-Za-z0-9_.$]*)")


class OperationError(Exception):
    """Safe machine-readable errors; never include raw ADB output or local paths."""


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def document(kind, operation):
    return {"schema_version": SCHEMA_VERSION, "tool": TOOL, "document_type": kind,
            "operation": operation, "created_utc": utc_now()}


def canonical_component(value):
    match = COMPONENT_PATTERN.fullmatch(value)
    if not match:
        raise OperationError("invalid_component")
    package, activity = match.groups()
    return package + "/" + (package + activity if activity.startswith(".") else activity)


def remove_component(value, component):
    if value is None:
        return None
    wanted = canonical_component(component)
    remaining = []
    for item in value.split(":"):
        try:
            matches = canonical_component(item) == wanted
        except OperationError:
            matches = False
        if not matches:
            remaining.append(item)
    return ":".join(remaining) if remaining else None


def protected_roots(script_path=None):
    script = Path(script_path or __file__).resolve()
    # Both tools/tvctl.py and a copied scripts/tvctl.py have an enclosing project root.
    roots = {script.parent.parent}
    for ancestor in script.parents:
        if (ancestor / "kit.json").is_file() or (ancestor / "SKILL.md").is_file():
            roots.add(ancestor)
    return roots


def external_directory(value, script_path=None):
    try:
        directory = Path(value).expanduser().resolve()
    except (OSError, RuntimeError) as error:
        raise OperationError("private_state_directory_unavailable") from error
    for root in protected_roots(script_path):
        if directory == root or root in directory.parents:
            raise OperationError("state_directory_is_inside_a_shareable_project")
    for ancestor in (directory, *directory.parents):
        if (ancestor / "kit.json").is_file() or (ancestor / "SKILL.md").is_file():
            raise OperationError("state_directory_is_inside_a_shareable_project")
    return directory


class StateStore:
    def __init__(self, directory):
        self.directory = external_directory(directory)
        try:
            self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not self.directory.is_dir():
                raise OSError()
        except OSError as error:
            raise OperationError("private_state_directory_unavailable") from error

    def save(self, kind, payload):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        path = self.directory / (kind + "-" + stamp + "-" + uuid.uuid4().hex + ".json")
        try:
            descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except (OSError, ValueError) as error:
            raise OperationError("private_state_write_failed") from error
        return path.name


class Adb:
    def __init__(self, executable, serial):
        self.executable, self.serial = executable, serial

    def shell(self, *arguments):
        # The host never invokes a shell. Quote once for Android's remote shell.
        command = [self.executable, "-s", self.serial, "shell", shlex.join(map(str, arguments))]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        except UnicodeError as error:
            raise OperationError("adb_output_decode_failed") from error
        except (OSError, subprocess.TimeoutExpired) as error:
            raise OperationError("adb_unavailable_or_timed_out") from error
        if result.returncode:
            raise OperationError("adb_command_failed")
        output = result.stdout.rstrip("\r\n")
        if re.search(r"(?im)^\s*(?:Error(?::| type)|Exception occurred|Failure \[|Security exception:|SecurityException)", output):
            raise OperationError("adb_remote_command_failed")
        return output


def read_setting(adb, namespace, key):
    value = adb.shell("settings", "--user", "0", "get", namespace, key)
    return None if value == "null" else value


def identity(adb):
    for source in ("ro.serialno", "ro.boot.serialno", "android_id"):
        value = (read_setting(adb, "secure", source) if source == "android_id"
                 else adb.shell("getprop", source))
        value = value.strip() if value else ""
        if value and value.lower() not in {"unknown", "null"}:
            digest = hashlib.sha256((TOOL + ":identity:v1:" + source + ":" + value).encode("utf-8")).hexdigest()
            return {"algorithm": "sha256", "source": source, "id_sha256": digest}
    raise OperationError("stable_device_identity_unavailable")


def valid_identity(value):
    return (isinstance(value, dict) and value.get("algorithm") == "sha256"
            and isinstance(value.get("source"), str)
            and value.get("source") in {"ro.serialno", "ro.boot.serialno", "android_id"}
            and isinstance(value.get("id_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", value["id_sha256"]) is not None)


def parse_boolean(text, pattern):
    match = re.search(pattern + r"\s*[:=]\s*(true|false)\b", text, re.I)
    return match.group(1).lower() == "true" if match else None


def snapshot(adb):
    result = {"boot_count": None, "uptime_seconds": None, "power": None,
              "focus_component": None, "input_filter_enabled": None, "unavailable": []}
    reads = {
        "boot_count": lambda: read_setting(adb, "global", "boot_count"),
        "uptime_seconds": lambda: adb.shell("cat", "/proc/uptime"),
        "power": lambda: adb.shell("dumpsys", "power"),
        "focus_component": lambda: adb.shell("dumpsys", "window"),
        "input_filter_enabled": lambda: adb.shell("dumpsys", "input"),
    }
    for key, read in reads.items():
        try:
            raw = read()
            if key == "boot_count":
                result[key] = int(raw) if raw is not None and re.fullmatch(r"\d+", raw) else None
            elif key == "uptime_seconds":
                value = float(raw.split()[0])
                result[key] = value if math.isfinite(value) and value >= 0 else None
            elif key == "power":
                wake = re.search(r"\bmWakefulness\s*=\s*(Awake|Asleep|Dozing|Dreaming)\b", raw, re.I)
                display = re.search(r"Display Power:\s*state=(ON|OFF|DOZE|DOZE_SUSPEND|UNKNOWN)\b", raw, re.I)
                result[key] = {"wakefulness": wake.group(1).lower() if wake else None,
                               "display_state": display.group(1).upper() if display else None,
                               "interactive": parse_boolean(raw, r"\bmInteractive")}
            elif key == "focus_component":
                for line in raw.splitlines():
                    if "mCurrentFocus=" in line:
                        match = re.search(r"\b([A-Za-z_][A-Za-z0-9_.]*/[A-Za-z0-9_.$]+)", line)
                        result[key] = match.group(1) if match else None
                        break
            else:
                result[key] = parse_boolean(raw, r"\b(?:mInputFilterEnabled|InputFilterEnabled)")
            if result[key] is None:
                result["unavailable"].append(key)
        except (OperationError, ValueError, IndexError):
            result["unavailable"].append(key)
    return result


def validate_backup(backup):
    if (not isinstance(backup, dict) or backup.get("schema_version") != SCHEMA_VERSION
            or backup.get("tool") != TOOL or backup.get("document_type") != "backup"
            or not valid_identity(backup.get("device"))):
        raise OperationError("invalid_backup_schema_or_identity")
    records = backup.get("changes")
    parameters = backup.get("parameters")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(parameters, dict):
        raise OperationError("invalid_backup_scope")
    record = records[0]
    if (not isinstance(record, dict) or not {"namespace", "key", "before", "after"}.issubset(record)
            or any(record[key] is not None and not isinstance(record[key], str) for key in ("before", "after"))):
        raise OperationError("invalid_backup_values")
    target = (record["namespace"], record["key"])
    operation = backup.get("operation")
    if operation == "set-startup":
        allowed = (target == STARTUP and parameters.get("vendor_profile") == "xiaomi"
                   and isinstance(record["after"], str) and PACKAGE_PATTERN.fullmatch(record["after"]) is not None)
    elif operation == "standby-preserve":
        allowed = (target == STANDBY and parameters.get("vendor_profile") == "xiaomi"
                   and parameters.get("evidence_confirmed") is True and record["after"] == "disable")
    elif operation == "retire-guard":
        component = parameters.get("component")
        allowed = (target == SERVICES and isinstance(component, str)
                   and remove_component(record["before"], component) == record["after"])
    else:
        allowed = False
    if not allowed:
        raise OperationError("unsupported_or_inconsistent_backup_scope")
    return backup


def load_backup(path):
    # A backup may be in a different private directory, but never in a shareable tree.
    external_directory(Path(path).expanduser().resolve().parent)
    try:
        with Path(path).expanduser().open(encoding="utf-8") as handle:
            return validate_backup(json.load(handle))
    except (OSError, ValueError) as error:
        raise OperationError("backup_unreadable_or_invalid_json") from error


def target_change(args, adb):
    parameters = {}
    if args.command == "set-startup":
        target, after = STARTUP, args.package
        parameters["vendor_profile"] = args.vendor_profile
    elif args.command == "standby-preserve":
        target, after = STANDBY, "disable"
        parameters.update(vendor_profile=args.vendor_profile, evidence_confirmed=args.evidence_confirmed)
    else:
        target = SERVICES
        parameters["component"] = args.component
        after = None
    before = read_setting(adb, *target)
    if args.command == "retire-guard":
        after = remove_component(before, args.component)
    return {"namespace": target[0], "key": target[1], "before": before, "after": after}, parameters


def apply_value(adb, record, observed, desired, report):
    target = (record["namespace"], record["key"])
    is_services = target == SERVICES
    global_before = read_setting(adb, *GLOBAL_ACCESSIBILITY) if is_services else None
    if is_services:
        report["global_accessibility_before"] = global_before
    current = read_setting(adb, *target)
    if current != observed:
        report["observed_after"] = current
        return "preserved-concurrent-change"
    if is_services and read_setting(adb, *GLOBAL_ACCESSIBILITY) != global_before:
        return "preserved-concurrent-change"
    if current == desired:
        return "unchanged"
    report["write_attempted"] = True
    if desired is None:
        adb.shell("settings", "--user", "0", "delete", *target)
    else:
        adb.shell("settings", "--user", "0", "put", *target, desired)
    observed_after = read_setting(adb, *target)
    report["observed_after"] = observed_after
    report["target_verified"] = observed_after == desired
    if is_services:
        global_after = read_setting(adb, *GLOBAL_ACCESSIBILITY)
        report["global_accessibility_after"] = global_after
        report["global_accessibility_preserved"] = global_after == global_before
    if not report["target_verified"] or (is_services and not report["global_accessibility_preserved"]):
        raise OperationError("write_verification_failed")
    return "restored" if report["operation"] == "restore" else "applied"


def execute(args, adb, store, report, backup=None):
    device = identity(adb)
    report["device"] = device
    if args.command == "snapshot":
        report["snapshot"] = snapshot(adb)
        return {"status": "inspected", "device": device, "snapshot": report["snapshot"]}
    if args.command == "restore":
        if device != backup["device"]:
            raise OperationError("backup_device_identity_mismatch")
        record = backup["changes"][0]
        report["change"] = record
        now = read_setting(adb, record["namespace"], record["key"])
        report["observed_before"] = now
        if now == record["before"]:
            status = "already-restored"
        elif now != record["after"]:
            status = "preserved-later-change"
        elif args.inspect:
            status = "would-restore"
        else:
            status = apply_value(adb, record, now, record["before"], report)
        return {"status": status}
    record, parameters = target_change(args, adb)
    report["change"] = record
    if args.inspect:
        if args.command == "retire-guard":
            report["global_accessibility_before"] = read_setting(adb, *GLOBAL_ACCESSIBILITY)
        return {"status": "inspected", "would_change": record["before"] != record["after"]}
    prepared = document("backup", args.command)
    prepared.update(device=device, parameters=parameters, changes=[record], status="prepared-before-write")
    backup_name = store.save("backup", prepared)  # Must succeed before any device mutation.
    report["backup_file"] = backup_name
    status = apply_value(adb, record, record["before"], record["after"], report)
    return {"status": status, "backup_file": backup_name}


def parser():
    result = argparse.ArgumentParser(prog="tvctl.py", description=__doc__)
    subcommands = result.add_subparsers(dest="command", required=True)
    for name in ("snapshot", "set-startup", "standby-preserve", "retire-guard", "restore"):
        command = subcommands.add_parser(name)
        command.add_argument("--serial", required=True, help="Caller-supplied device selector; never discovered or connected automatically")
        command.add_argument("--adb", default="adb", help="Existing adb executable (no installation or device discovery)")
        command.add_argument("--state-dir", help="Private directory outside every kit/skill sharing tree; required for device access")
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--inspect", action="store_true", help="Read the selected device; never modify it")
        mode.add_argument("--apply", action="store_true", help="Apply the one named operation after backup and checks")
        if name in {"set-startup", "standby-preserve"}:
            command.add_argument("--vendor-profile", choices=["xiaomi"], help="Explicit firmware-specific adapter, not universal support")
        if name == "set-startup":
            command.add_argument("--package", required=True)
        if name == "standby-preserve":
            command.add_argument("--evidence-confirmed", action="store_true", help="You verified this exact firmware's code/log condition; required to apply")
        if name == "retire-guard":
            command.add_argument("--component", required=True)
        if name == "restore":
            command.add_argument("--backup", required=True, help="Private backup file made by this CLI")
    return result


def make_plan(args):
    if not args.serial.strip():
        raise OperationError("explicit_nonempty_serial_required")
    if args.command in {"set-startup", "standby-preserve"} and args.vendor_profile != "xiaomi":
        raise OperationError("explicit_vendor_profile_required")
    if args.command == "set-startup" and not PACKAGE_PATTERN.fullmatch(args.package):
        raise OperationError("invalid_package")
    if args.command == "retire-guard":
        canonical_component(args.component)
    if args.command == "snapshot" and args.apply:
        raise OperationError("snapshot_supports_inspect_only")
    if args.command == "standby-preserve" and args.apply and not args.evidence_confirmed:
        raise OperationError("firmware_evidence_confirmation_required")
    plan = document("plan", args.command)
    plan.update(mode="offline", device_access=False, device_changes=False,
                user_id=0, apply_requires_private_state=True)
    if args.command == "snapshot":
        plan["fields"] = ["boot_count", "uptime_seconds", "power", "focus_component", "input_filter_enabled", "device_identity_hash"]
    elif args.command == "restore":
        plan["checks"] = ["backup_schema", "device_identity", "current_equals_backup_after", "write_readback"]
    else:
        target = STARTUP if args.command == "set-startup" else STANDBY if args.command == "standby-preserve" else SERVICES
        plan["target"] = {"namespace": target[0], "key": target[1]}
        if args.command in {"set-startup", "standby-preserve"}:
            plan["vendor_profile"] = args.vendor_profile
            plan["universal_firmware_support"] = False
        if args.command == "standby-preserve":
            plan["apply_requires_firmware_evidence"] = True
            plan["requested_value"] = "disable"
        if args.command == "retire-guard":
            plan["global_accessibility_switch_changes"] = False
            plan["requested_component"] = args.component
        if args.command == "set-startup":
            plan["requested_package"] = args.package
    return plan


def main(argv=None):
    args = parser().parse_args(argv)
    report, store = None, None
    try:
        plan = make_plan(args)
        if not args.inspect and not args.apply:
            print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
            return 0
        if not args.state_dir:
            raise OperationError("explicit_private_state_directory_required")
        external_directory(args.state_dir)
        backup = load_backup(args.backup) if args.command == "restore" else None
        store = StateStore(args.state_dir)
        report = document("report", args.command)
        report.update(mode="inspect" if args.inspect else "apply", write_attempted=False)
        result = execute(args, Adb(args.adb, args.serial), store, report, backup)
        report.update(status="completed", result=result)
        report_name = store.save("report", report)
        print(json.dumps({"schema_version": SCHEMA_VERSION, "operation": args.command,
                          "mode": report["mode"], **result, "report_file": report_name},
                         ensure_ascii=False, sort_keys=True))
        return 0
    except OperationError as error:
        output = {"schema_version": SCHEMA_VERSION, "operation": args.command,
                  "status": "failed", "error": str(error)}
        if report is not None and store is not None:
            report.update(status="failed", error=str(error))
            if "backup_file" in report:
                output["backup_file"] = report["backup_file"]
            try:
                output["report_file"] = store.save("report", report)
            except OperationError:
                output["report_saved"] = False
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    sys.exit(main())
