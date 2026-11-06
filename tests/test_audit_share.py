"""Synthetic privacy failures only; no original devices, organizations or secrets."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


_SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_share.py"
_SPEC = importlib.util.spec_from_file_location("audit_share", _SOURCE)
audit = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = audit
_SPEC.loader.exec_module(audit)


class ShareAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="share-audit-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "kit"
        self.root.mkdir()
        self.write("kit.json", json.dumps({"kit_id": audit.KIT_ID, "schema_version": 1}))
        self.write("README.md", "# Android TV Launcher Kit\nReusable source and neutral examples.\n")

    def write(self, relative: str, value: str | bytes) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        else:
            path.write_text(value, encoding="utf-8")
        return path

    def rules(self, terms: tuple[str, ...] = ()) -> set[str]:
        return {finding.rule for finding in audit.audit_tree(self.root, terms)}

    def test_neutral_source_and_documentation_addresses_pass(self) -> None:
        self.write("project/app/src/main/java/org/example/tvlauncher/MainActivity.kt", "package org.example.tvlauncher\n")
        self.write("project/app/src/main/res/values/strings.xml", '<resources><string name="app_name">TV Home</string></resources>\n')
        self.write("README.md", '\n'.join([
            "https://developer.android.com/guide/topics/ui/declaring-layout",
            "http://schemas.android.com/apk/res/android", "https://example.org/reference",
            "192.0.2.10", "198.51.100.20", "203.0.113.30", "127.0.0.1", "2001:db8::1", "::1",
            "contact@example.org", "serial: <DEVICE_SERIAL>", "api_key: ${API_KEY}",
            r"The regex punctuation (?::| type) is not a device address.",
            "sha256 test value: " + "0" * 64, "com.android.tv.settings", "com.vendor.android.settings",
        ]))
        self.assertEqual([], audit.audit_tree(self.root))

    def test_application_namespaces_must_remain_neutral(self) -> None:
        self.write("project/app/build.gradle.kts", 'namespace = "com.synthetic.privateapp"\n')
        self.assertIn("non-neutral-app-namespace", self.rules())

    def test_marker_is_required_before_any_walk(self) -> None:
        (self.root / "kit.json").unlink()
        self.write("outside-scope/should-not-be-read.txt", "not part of a kit")
        self.assertEqual([audit.Finding(".", "kit-marker-invalid")], audit.audit_tree(self.root))

    def test_marker_cannot_be_a_symlink(self) -> None:
        marker = self.root / "kit.json"
        other = Path(self.temporary.name) / "marker.json"
        marker.rename(other)
        marker.symlink_to(other)
        self.assertEqual({"kit-marker-invalid"}, self.rules())

    def test_private_words_are_external_and_unicode_normalized(self) -> None:
        private_word = "Synthetic" + "PrivateOrganization"
        self.write("README.md", private_word.swapcase())
        self.assertIn("private-term", self.rules((private_word,)))
        self.write("README.md", "Ａｃｍｅ")
        self.assertIn("private-term", self.rules(("Ac" + "me",)))

    def test_private_file_names_are_not_echoed(self) -> None:
        private_word = "Synthetic" + "PrivateOrganization"
        self.write(private_word + ".txt", "text")
        findings = audit.audit_tree(self.root, (private_word,))
        self.assertTrue(findings)
        self.assertTrue(all(private_word not in item.path for item in findings))

    def test_distributed_auditor_and_synthetic_tests_pass_their_own_content_rules(self) -> None:
        for source in (_SOURCE, Path(__file__).resolve()):
            with self.subTest(source=source.name):
                self.assertEqual(set(), audit._content_rules(source.read_text(encoding="utf-8"), source.name, ()))

    def test_local_paths_are_rejected(self) -> None:
        paths = [
            "/".join(["", "Users", "synthetic-person", "project"]),
            "/".join(["", "home", "synthetic-person", "project"]),
            "C:" + chr(92) + chr(92).join(["Users", "synthetic-person", "project"]),
            '"' + "/".join(["", "custom-workstation", "project"]) + '"',
        ]
        for value in paths:
            with self.subTest(style=paths.index(value)):
                self.write("README.md", value)
                self.assertIn("local-absolute-path", self.rules())

    def test_live_network_addresses_and_mac_are_rejected(self) -> None:
        cases = [
            (".".join(map(str, (10, 23, 45, 67))), "network-address"),
            (":".join(["fd12", "3456", "789a", "", "7"]), "network-address"),
            (":".join(["a1", "b2", "c3", "d4", "e5", "f6"]), "mac-address"),
        ]
        for value, rule in cases:
            with self.subTest(rule=rule):
                self.write("README.md", value)
                self.assertIn(rule, self.rules())

    def test_threads_and_device_identity_are_rejected(self) -> None:
        thread = "-".join(["12345678", "1234", "4123", "8123", "123456789abc"])
        for value, rule in [
            (thread, "conversation-or-identity-uuid"),
            ("codex" + "://threads/" + thread, "private-conversation-link"),
            (json.dumps({"ser" + "ial": "SYNTHETIC" + "DEVICE1234"}), "device-identity"),
            (json.dumps({"ss" + "id": "Synthetic Network"}), "device-identity"),
            ("a" * 64, "unapproved-identity-digest"),
            (":".join(["ab"] * 32), "unapproved-identity-digest"),
        ]:
            with self.subTest(rule=rule):
                self.write("README.md", value)
                self.assertIn(rule, self.rules())

    def test_credentials_are_rejected_without_echoing(self) -> None:
        fixtures = [
            ("sk" + "-" + "a" * 32, "credential-token"),
            ("-----BEGIN " + "PRIVATE KEY-----", "private-key"),
            (json.dumps({"api" + "_key": "synthetic-secret-value"}), "credential-literal"),
            ("https://" + "user:synthetic-password@" + "example.org", "url-credentials"),
            ("https://" + "developer.android.com/?" + "tok" + "en=" + "synthetic-secret-value", "url-credentials"),
        ]
        for value, rule in fixtures:
            with self.subTest(rule=rule):
                self.write("README.md", value)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    result = audit.main([str(self.root)])
                self.assertEqual(1, result)
                self.assertIn(rule, output.getvalue())
                self.assertNotIn(value, output.getvalue())

    def test_personal_contacts_and_unknown_links_are_rejected(self) -> None:
        fixtures = [
            ("person" + "@" + ".".join(["private-company", "com"]), "personal-email"),
            ("+" + "861" + "3812345678", "personal-phone"),
            ("https://" + ".".join(["private-company", "com"]) + chr(47) + "internal", "unapproved-external-link"),
        ]
        for value, rule in fixtures:
            with self.subTest(rule=rule):
                self.write("README.md", value)
                self.assertIn(rule, self.rules())

    def test_binary_files_caches_assets_and_unknown_files_are_rejected(self) -> None:
        fixtures = [
            ("project/app/build/output.txt", "text", "forbidden-directory"),
            ("project/app/src/main/res/drawable/brand.png", bytes([137, 80, 78, 71]), "forbidden-file-type"),
            ("project/app/local.properties", "sdk.dir=example", "forbidden-file-type"),
            ("tools/unreviewed.py", "print('hello')", "unapproved-file"),
            ("vendor/source.txt", "text", "forbidden-directory"),
            ("README.md", bytes([0, 1, 2, 3]), "binary-or-control-data"),
            ("README.md", bytes([255, 254, 253]), "binary-or-non-utf8"),
        ]
        for relative, data, rule in fixtures:
            with self.subTest(rule=rule):
                path = self.write(relative, data)
                self.assertIn(rule, self.rules())
                if path.exists():
                    path.unlink()

    def test_symlinks_and_hardlinks_do_not_import_external_content(self) -> None:
        external = Path(self.temporary.name) / "external.txt"
        external.write_text("external data", encoding="utf-8")
        link = self.root / "NOTICE.md"
        link.symlink_to(external)
        self.assertIn("symlink", self.rules())
        link.unlink()
        os.link(external, link)
        self.assertIn("hard-linked-file", self.rules())

    def test_empty_unknown_directory_is_rejected(self) -> None:
        (self.root / "unreviewed").mkdir()
        self.assertIn("unapproved-directory", self.rules())

    def test_manifest_hashes_are_allowed_only_as_verified_file_integrity(self) -> None:
        entries = []
        for path in sorted(self.root.iterdir()):
            entries.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.name)
        self.write("MANIFEST.sha256", "\n".join(entries) + "\n")
        self.assertEqual(set(), self.rules())
        self.write("README.md", "Changed content\n")
        self.assertIn("manifest-content-mismatch", self.rules())

    def test_manifest_traversal_missing_files_and_fake_digests_are_rejected(self) -> None:
        self.write("MANIFEST.sha256", "0" * 64 + "  ../outside.txt\n")
        self.assertIn("manifest-invalid", self.rules())
        self.write("MANIFEST.sha256", "0" * 64 + "  README.md\n")
        self.assertIn("manifest-file-set-mismatch", self.rules())
        self.assertIn("manifest-content-mismatch", self.rules())

    def test_denylist_must_remain_outside_package(self) -> None:
        denylist = self.write("denylist.txt", "SyntheticPrivateTerm\n")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = audit.main([str(self.root), "--denylist-file", str(denylist)])
        self.assertEqual(1, result)
        self.assertEqual(".\tdenylist-inside-package\n", output.getvalue())

    def test_external_denylist_cli_never_prints_private_term(self) -> None:
        term = "Synthetic" + "PrivateTerm"
        self.write("README.md", term)
        denylist = Path(self.temporary.name) / "external-denylist.txt"
        denylist.write_text(term + "\n", encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = audit.main([str(self.root), "--denylist-file", str(denylist), "--json"])
        self.assertEqual(1, result)
        parsed = json.loads(output.getvalue())
        self.assertEqual([{"path": "README.md", "rule": "private-term"}], parsed)
        self.assertNotIn(term, output.getvalue())
        self.assertNotIn(str(self.root), output.getvalue())


if __name__ == "__main__":
    unittest.main()
