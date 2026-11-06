#!/usr/bin/env python3
"""Audit this source-only kit before sharing it. Uses only the Python standard library.

The allowlist intentionally rejects new files until a reviewer approves their type
and location. Organization and person names belong in an external denylist, never
in this distributable tool. This audit supplements a human source/assets review.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata
from urllib.parse import parse_qsl, urlsplit
from typing import Sequence


KIT_ID = "android-tv-launcher-kit"
MAX_FILE_BYTES = 1_000_000
MAX_TOTAL_BYTES = 12_000_000
ROOT_FILES = frozenset({
    "README.md", "NOTICE.md", "PRIVACY.md", "VERIFICATION.md", "kit.json",
    "MANIFEST.sha256", "requirements-dev.txt", ".gitignore",
})
EXACT_FILES = frozenset({
    "tools/tvctl.py", "tools/audit_share.py", "tools/package_release.py",
    "tests/test_tvctl.py", "tests/test_audit_share.py",
    "skills/android-tv-launcher/SKILL.md",
    "skills/android-tv-launcher/agents/openai.yaml",
    "skills/android-tv-launcher/scripts/tvctl.py",
})
PROJECT_PREFIXES = ("project/", "skills/android-tv-launcher/assets/project/")
PROJECT_FILES = frozenset({
    "README.md", "NOTICE.md", "VALIDATION.md", ".gitignore", "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts", "gradle.properties",
    "gradle/libs.versions.toml", "tools/test-logic.py", "tools/verify-android.py",
    "tests/app/OwnedKeyPressTest.java", "tests/app/IntroPlaybackTest.java",
    "tests/app/DrawerNavigationTest.java", "tests/bridge/OwnedKeyPressTest.java",
    "tests/bridge/ForegroundHandoffTest.java", "tests/bridge/ColdBootPolicyTest.java",
    "tests/bridge/BootDecisionTest.java",
})
MODULE_NAME = r"(?:app|boot-bridge)"
PACKAGE_PATH = r"(?:[a-z][a-z0-9_]*/)*"
RESOURCE_DIRECTORY = r"(?:values|layout|drawable|mipmap|xml|menu|anim|animator)(?:-[a-z0-9-]+)?"
MODULE_FILE_RE = re.compile(
    rf"{MODULE_NAME}/(?:build\.gradle(?:\.kts)?|proguard-rules\.pro|"
    rf"src/main/AndroidManifest\.xml|"
    rf"src/main/(?:java|kotlin)/org/example/tvlauncher/{PACKAGE_PATH}[A-Za-z][A-Za-z0-9_]*\.(?:kt|java)|"
    rf"src/main/res/{RESOURCE_DIRECTORY}/[a-z][a-z0-9_]*\.xml)\Z"
)
REFERENCE_RE = re.compile(r"skills/android-tv-launcher/references/[a-z0-9][a-z0-9_-]*\.md\Z")
FORBIDDEN_DIRECTORIES = frozenset({
    ".git", ".gradle", ".idea", ".vscode", ".codex", ".session-rebuild",
    "__pycache__", "node_modules", ".cache", "cache", "caches", "build",
    "dist", "out", "target", "backup", "backups", "log", "logs", "vendor",
    "reverse", "decompiled", "screenshots", "captures", "recordings",
    ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache",
})
FORBIDDEN_SUFFIXES = frozenset({
    ".apk", ".aab", ".apks", ".jar", ".zip", ".7z", ".rar", ".tar",
    ".gz", ".tgz", ".bz2", ".xz", ".class", ".dex", ".so", ".dylib",
    ".dll", ".exe", ".bin", ".pyc", ".pyo", ".db", ".sqlite", ".sqlite3",
    ".pcap", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".icns", ".svg", ".pdf", ".ttf", ".otf", ".woff", ".woff2", ".mp4",
    ".mov", ".mp3", ".wav", ".m4a", ".ogg", ".keystore", ".jks", ".p12",
    ".pfx", ".pem", ".key", ".der", ".cer", ".crt", ".pub", ".log",
    ".bak", ".old", ".orig", ".tmp", ".swp", ".swo",
})
FORBIDDEN_NAMES = frozenset({
    ".ds_store", "local.properties", "credentials.json", "secrets.json",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "known_hosts",
    "authorized_keys", "adbkey", "adbkey.pub", "key.properties",
})
OFFICIAL_HOSTS = frozenset({
    "developer.android.com", "developer.android.google.cn", "source.android.com",
    "schemas.android.com", "android.googlesource.com", "docs.gradle.org",
    "services.gradle.org", "gradle.org", "kotlinlang.org", "docs.python.org",
    "www.python.org", "opensource.org", "spdx.org",
})
EXAMPLE_DOMAINS = frozenset({"example.com", "example.net", "example.org", "example.invalid", "example.test"})
DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("2001:db8::/32"),
)
LOCAL_PATH_RE = re.compile(
    r"(?i)(?:file:" r"/+|(?<![A-Za-z0-9_:/])/(?:Users|home|root|private|Volumes|Applications|"
    r"var|tmp|opt|usr|etc|mnt|media|workspace|workspaces)(?:/|\b)|"
    r"\b[A-Z]:[\\/]|(?<!\\)\\\\[A-Za-z0-9._-]+\\[A-Za-z0-9._-]+|~/[A-Za-z0-9_.-]+/)"
)
QUOTED_ABSOLUTE_PATH_RE = re.compile(r"(?P<quote>['\"])(?P<path>/(?!/)[^'\"\r\n]+)(?P=quote)")
ANDROID_PATH_PREFIXES = ("/system/", "/data/", "/sdcard/", "/storage/", "/proc/", "/dev/", "/sys/", "/product/", "/vendor/")
IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
IPV6_RE = re.compile(r"(?<![\w])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]*(?:%[0-9A-Za-z_.-]+)?(?![\w])")
MAC_RE = re.compile(r"(?<![0-9A-Fa-f:-])(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f:-])")
UUID_RE = re.compile(r"(?i)(?<![0-9a-f])[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}(?![0-9a-f])")
LONG_HEX_RE = re.compile(r"(?i)(?<![0-9a-f])(?:[0-9a-f]{128}|[0-9a-f]{64}|[0-9a-f]{40}|[0-9a-f]{32})(?![0-9a-f])")
FINGERPRINT_RE = re.compile(r"(?i)(?<![0-9a-f:-])(?:[0-9a-f]{2}[:-]){19,63}[0-9a-f]{2}(?![0-9a-f:-])")
EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])")
PHONE_RE = re.compile(r"(?<![\w])(?:\+[1-9][0-9 ()-]{7,18}[0-9]|1[3-9]\d{9})(?![\w])")
URL_RE = re.compile(r"(?i)https?://[^\s<>\"'`\])}]+")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN (?:[A-Z0-9 ]* )?PRIVATE KEY-----|-----BEGIN PGP PRIVATE " r"KEY BLOCK-----")
CREDENTIAL_RE = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|AIza[A-Za-z0-9_-]{30,}|"
    r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{16,}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b"
)
PRIVATE_CHAT_RE = re.compile(r"(?i)(?:codex|plugin)://|https?://(?:chatgpt\.com|chat\.openai\.com)/c/")
SENSITIVE_KEY = (
    r"(?:password|passwd|storePassword|keyPassword|api[_-]?key|client[_-]?secret|"
    r"access[_-]?token|refresh[_-]?token|auth[_-]?token|secret[_-]?key|authorization|cookie|"
    r"token|secret|access[_-]?key|private[_-]?key)"
)
IDENTITY_KEY = (
    r"(?:ssid|bssid|wifi[_-]?(?:name|mac)|bluetooth[_-]?(?:address|mac)|"
    r"device[_-]?(?:serial|id|fingerprint)|serial(?:[_-]?number)?|android[_-]?id|ro\.build\.fingerprint)"
)
LITERAL_ASSIGNMENT_RE = re.compile(
    rf"(?i)[\"']?(?P<key>{SENSITIVE_KEY}|{IDENTITY_KEY})[\"']?\s*[:=]\s*"
    r"(?P<quote>[\"'])(?P<value>[^\"'\r\n]+)(?P=quote)"
)
UNQUOTED_ASSIGNMENT_RE = re.compile(
    rf"(?im)^\s*[\"']?(?P<key>{SENSITIVE_KEY}|{IDENTITY_KEY})[\"']?\s*[:=]\s*(?P<value>[^\r\n]+)"
)
IDENTITY_KEY_RE = re.compile(rf"(?i){IDENTITY_KEY}\Z")
MANIFEST_LINE_RE = re.compile(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)\Z")


@dataclass(frozen=True, order=True)
class Finding:
    path: str
    rule: str


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _private_term(value: str, deny_terms: Sequence[str]) -> bool:
    value = _normalized(value)
    return any(term and _normalized(term) in value for term in deny_terms)


def _neutral_value(value: str) -> bool:
    value = value.strip().rstrip(",").strip().strip("\"'").strip()
    lowered = value.casefold()
    return (
        not value or lowered in {"none", "null", "false", "true", "redacted", "changeme", "example", "placeholder"}
        or (value.startswith("<") and value.endswith(">"))
        or value.startswith(("${", "$env:", "os.environ", "os.getenv", "args.", "config.", "self."))
        or value.startswith("YOUR_")
        or (len(value) >= 8 and set(value) <= {"0", ":", "-"})
    )


def _example_host(host: str) -> bool:
    host = host.casefold().rstrip(".")
    return any(host == domain or host.endswith("." + domain) for domain in EXAMPLE_DOMAINS)


def _permitted_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if address.is_loopback:
        return True
    return any(address.version == network.version and address in network for network in DOCUMENTATION_NETWORKS)


def _content_rules(text: str, relative: str, deny_terms: Sequence[str]) -> set[str]:
    rules: set[str] = set()
    if _private_term(text, deny_terms):
        rules.add("private-term")
    portable_shebang_removed = re.sub(r"(?m)^#!/(?:usr/bin/env (?:python3|bash)|bin/(?:sh|bash))\r?$", "", text)
    if LOCAL_PATH_RE.search(portable_shebang_removed):
        rules.add("local-absolute-path")
    for match in QUOTED_ABSOLUTE_PATH_RE.finditer(text):
        candidate = match["path"]
        # These are platform paths, not the author's workstation directories.
        # Pattern strings are not filesystem paths; reject other concrete literals.
        if not candidate.startswith(ANDROID_PATH_PREFIXES) and re.fullmatch(r"/[A-Za-z0-9_./ -]+", candidate):
            rules.add("local-absolute-path")
    for match in IPV4_RE.finditer(text):
        try:
            address = ipaddress.IPv4Address(match[0])
        except ValueError:
            continue
        if not _permitted_address(address):
            rules.add("network-address")
    for match in IPV6_RE.finditer(text):
        # A bare double colon is also Python/regex punctuation, not a device ID.
        if not re.search(r"[0-9a-fA-F]", match[0]):
            continue
        try:
            address = ipaddress.IPv6Address(match[0].rstrip("."))
        except ValueError:
            continue
        if not _permitted_address(address):
            rules.add("network-address")
    for match in MAC_RE.finditer(text):
        if any(character not in "0:-" for character in match[0]):
            rules.add("mac-address")
    for match in UUID_RE.finditer(text):
        if any(character not in "0-" for character in match[0]):
            rules.add("conversation-or-identity-uuid")
    if relative != "MANIFEST.sha256":
        if any(set(match[0]) != {"0"} for match in LONG_HEX_RE.finditer(text)):
            rules.add("unapproved-identity-digest")
    if any(any(character not in "0:-" for character in match[0]) for match in FINGERPRINT_RE.finditer(text)):
        rules.add("unapproved-identity-digest")
    if any(not _example_host(match[1]) for match in EMAIL_RE.finditer(text)):
        rules.add("personal-email")
    if PHONE_RE.search(text):
        rules.add("personal-phone")
    if PRIVATE_KEY_RE.search(text):
        rules.add("private-key")
    if CREDENTIAL_RE.search(text):
        rules.add("credential-token")
    if PRIVATE_CHAT_RE.search(text):
        rules.add("private-conversation-link")
    if _project_relative(relative) is not None:
        package_patterns = (
            r"(?m)^\s*package\s+([A-Za-z_][A-Za-z0-9_.]*)\s*;?",
            r"\b(?:namespace|applicationId)\s*(?:=\s*)?[\"']([A-Za-z_][A-Za-z0-9_.]*)[\"']",
        )
        for pattern in package_patterns:
            if any(match[1] != "org.example" and not match[1].startswith("org.example.") for match in re.finditer(pattern, text)):
                rules.add("non-neutral-app-namespace")
    for match in LITERAL_ASSIGNMENT_RE.finditer(text):
        if not _neutral_value(match["value"]):
            rules.add("device-identity" if IDENTITY_KEY_RE.fullmatch(match["key"]) else "credential-literal")
    if Path(relative).suffix in {".json", ".yaml", ".yml", ".toml", ".properties", ".md", ".txt"}:
        for match in UNQUOTED_ASSIGNMENT_RE.finditer(text):
            value = match["value"].strip()
            if not _neutral_value(value) and not value.startswith(("#", "//")):
                rules.add("device-identity" if IDENTITY_KEY_RE.fullmatch(match["key"]) else "credential-literal")
    for match in URL_RE.finditer(text):
        try:
            parsed = urlsplit(match[0].rstrip(".,;"))
            host = (parsed.hostname or "").casefold()
        except ValueError:
            rules.add("unapproved-external-link")
            continue
        if parsed.username is not None or parsed.password is not None:
            rules.add("url-credentials")
        for key, value in parse_qsl(parsed.query):
            if (re.fullmatch(SENSITIVE_KEY, key, re.IGNORECASE) or key.casefold() in {"signature", "sig", "x-amz-signature", "x-amz-credential"}) and not _neutral_value(value):
                rules.add("url-credentials")
        if host not in OFFICIAL_HOSTS and not _example_host(host):
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                rules.add("unapproved-external-link")
            else:
                if not _permitted_address(address):
                    rules.add("unapproved-external-link")
    return rules


def _project_relative(relative: str) -> str | None:
    for prefix in PROJECT_PREFIXES:
        if relative.startswith(prefix):
            return relative[len(prefix):]
    return None


def _allowed_file(relative: str) -> bool:
    if relative in ROOT_FILES or relative in EXACT_FILES or REFERENCE_RE.fullmatch(relative):
        return True
    project_relative = _project_relative(relative)
    return project_relative is not None and (
        project_relative in PROJECT_FILES or MODULE_FILE_RE.fullmatch(project_relative) is not None
    )


def _allowed_directory(relative: str) -> bool:
    fixed = {
        "tools", "tests", "skills", "skills/android-tv-launcher",
        "skills/android-tv-launcher/agents", "skills/android-tv-launcher/references",
        "skills/android-tv-launcher/scripts", "skills/android-tv-launcher/assets",
        "project", "skills/android-tv-launcher/assets/project",
    }
    if relative in fixed:
        return True
    project_relative = _project_relative(relative)
    if project_relative is None:
        return False
    if project_relative in {"gradle", "tools", "tests", "tests/app", "tests/bridge"}:
        return True
    return re.fullmatch(
        rf"{MODULE_NAME}(?:/src(?:/main(?:/(?:res(?:/{RESOURCE_DIRECTORY})?|"
        rf"(?:java|kotlin)(?:/org(?:/example(?:/tvlauncher(?:/[a-z][a-z0-9_]*)*)?)?)?))?)?)?",
        project_relative,
    ) is not None


def _output_path(relative: str, deny_terms: Sequence[str]) -> str:
    # A sensitive file name is itself sensitive output. Report it at the root.
    if _content_rules(relative, "filename", deny_terms):
        return "."
    return "".join("?" if unicodedata.category(character).startswith("C") else character for character in relative)


def _marker_ok(root: Path) -> bool:
    marker = root / "kit.json"
    try:
        if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 32_768:
            return False
        value = json.loads(marker.read_text(encoding="utf-8"))
        return isinstance(value, dict) and value.get("kit_id") == KIT_ID and value.get("schema_version") == 1
    except (OSError, UnicodeError, ValueError):
        return False


def _manifest_findings(root: Path, files: dict[str, bytes]) -> set[str]:
    if "MANIFEST.sha256" not in files:
        return set()
    try:
        lines = files["MANIFEST.sha256"].decode("utf-8").splitlines()
    except UnicodeError:
        return {"manifest-invalid"}
    entries: dict[str, str] = {}
    for line in lines:
        match = MANIFEST_LINE_RE.fullmatch(line)
        if not match:
            return {"manifest-invalid"}
        digest, relative = match.groups()
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts or str(pure) != relative or relative == "MANIFEST.sha256" or relative in entries:
            return {"manifest-invalid"}
        entries[relative] = digest
    expected = set(files) - {"MANIFEST.sha256"}
    rules: set[str] = set()
    if set(entries) != expected:
        rules.add("manifest-file-set-mismatch")
    if any(relative in files and hashlib.sha256(files[relative]).hexdigest() != digest for relative, digest in entries.items()):
        rules.add("manifest-content-mismatch")
    return rules


def audit_tree(root: Path, deny_terms: Sequence[str] = ()) -> list[Finding]:
    """Audit only a marked kit directory, never follow symlinks, never modify files."""
    root = Path(root)
    if root.is_symlink():
        return [Finding(".", "root-symlink")]
    if not _marker_ok(root):
        return [Finding(".", "kit-marker-invalid")]
    findings: set[Finding] = set()
    files: dict[str, bytes] = {}
    total_bytes = 0

    def add(relative: str, rule: str) -> None:
        findings.add(Finding(_output_path(relative, deny_terms), rule))

    def walk_error(_: OSError) -> None:
        add(".", "directory-unreadable")

    for directory, subdirectories, filenames in os.walk(root, topdown=True, followlinks=False, onerror=walk_error):
        base = Path(directory)
        for name in sorted(subdirectories[:]):
            path = base / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                add(relative, "symlink")
                subdirectories.remove(name)
            elif name.casefold() in FORBIDDEN_DIRECTORIES:
                add(relative, "forbidden-directory")
                subdirectories.remove(name)
            elif not _allowed_directory(relative):
                add(relative, "unapproved-directory")
                subdirectories.remove(name)
            if _private_term(relative, deny_terms):
                add(relative, "private-term")
        for name in sorted(filenames):
            path = base / name
            relative = path.relative_to(root).as_posix()
            try:
                metadata = path.lstat()
                if stat.S_ISLNK(metadata.st_mode):
                    add(relative, "symlink")
                    continue
                if not stat.S_ISREG(metadata.st_mode):
                    add(relative, "non-regular-file")
                    continue
                if name.casefold() in FORBIDDEN_NAMES or name.casefold().startswith(".env") or path.suffix.casefold() in FORBIDDEN_SUFFIXES:
                    add(relative, "forbidden-file-type")
                    continue
                if not _allowed_file(relative):
                    add(relative, "unapproved-file")
                    continue
                if metadata.st_nlink > 1:
                    add(relative, "hard-linked-file")
                    continue
                if metadata.st_size > MAX_FILE_BYTES:
                    add(relative, "oversize-file")
                    continue
                total_bytes += metadata.st_size
                if total_bytes > MAX_TOTAL_BYTES:
                    add(".", "oversize-package")
                    return sorted(findings)
                with path.open("rb") as handle:
                    data = handle.read(MAX_FILE_BYTES + 1)
                if len(data) > MAX_FILE_BYTES:
                    add(relative, "oversize-file")
                    continue
            except OSError:
                add(relative, "file-unreadable")
                continue
            files[relative] = data
            try:
                text = data.decode("utf-8-sig")
            except UnicodeError:
                add(relative, "binary-or-non-utf8")
                continue
            if any(ord(character) < 32 and character not in "\t\r\n" for character in text):
                add(relative, "binary-or-control-data")
            for rule in _content_rules(text, relative, deny_terms):
                add(relative, rule)
            if _private_term(relative, deny_terms):
                add(relative, "private-term")
    for rule in _manifest_findings(root, files):
        add("MANIFEST.sha256", rule)
    return sorted(findings)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--denylist-file", type=Path, help="External UTF-8 file, one private term per line; never include it in the kit.")
    parser.add_argument("--json", action="store_true", help="Emit only path/rule objects.")
    args = parser.parse_args(argv)
    terms: list[str] = []
    findings: list[Finding] = []
    if args.denylist_file:
        try:
            if args.denylist_file.resolve().is_relative_to(args.root.resolve()):
                findings = [Finding(".", "denylist-inside-package")]
            else:
                terms = [line.strip() for line in args.denylist_file.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
                if not terms:
                    findings = [Finding(".", "denylist-empty")]
        except (OSError, RuntimeError, UnicodeError):
            findings = [Finding(".", "denylist-unreadable")]
    if not findings:
        findings = audit_tree(args.root, terms)
    if args.json:
        print(json.dumps([{"path": finding.path, "rule": finding.rule} for finding in findings], ensure_ascii=True))
    elif findings:
        for finding in findings:
            print(f"{finding.path}\t{finding.rule}")
    else:
        print(".\taudit-pass")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
