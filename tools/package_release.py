#!/usr/bin/env python3
"""Audit, hash and package a source-only kit, then audit its extracted archive."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import zipfile

from audit_share import audit_tree


class ReleaseError(Exception):
    pass


def audit(root: Path, terms: list[str], *, regenerating_manifest: bool = False) -> None:
    findings = audit_tree(root, terms)
    # The contents are re-audited; an old integrity list is safe to regenerate.
    integrity_only = {"manifest-invalid", "manifest-file-set-mismatch", "manifest-content-mismatch"}
    if regenerating_manifest:
        findings = [finding for finding in findings if finding.rule not in integrity_only]
    if findings:
        for finding in findings:
            print(f"{finding.path}\t{finding.rule}", file=sys.stderr)
        raise ReleaseError("privacy_audit_failed")


def files_under(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file()}


def verify_skill_mirrors(root: Path) -> None:
    skill = root / "skills/android-tv-launcher"
    if not (skill / "assets/project/README.md").is_file():
        raise ReleaseError("standalone_skill_project_missing")
    if files_under(root / "project") != files_under(skill / "assets/project"):
        raise ReleaseError("standalone_skill_project_differs")
    if (root / "tools/tvctl.py").read_bytes() != (skill / "scripts/tvctl.py").read_bytes():
        raise ReleaseError("standalone_skill_script_differs")


def manifest(root: Path) -> None:
    entries = files_under(root)
    entries.pop("MANIFEST.sha256", None)
    text = "".join(hashlib.sha256(content).hexdigest() + "  " + relative + "\n"
                   for relative, content in sorted(entries.items()))
    temporary = root / "MANIFEST.sha256.new"
    with temporary.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    temporary.replace(root / "MANIFEST.sha256")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--denylist-file", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    try:
        output = args.output.expanduser().resolve()
        if root == output or root in output.parents:
            raise ReleaseError("archive_must_be_outside_kit")
        if output.exists():
            raise ReleaseError("archive_exists_choose_a_new_name")
        if not output.parent.is_dir():
            raise ReleaseError("archive_parent_missing")
        terms: list[str] = []
        if args.denylist_file:
            denylist = args.denylist_file.expanduser().resolve()
            if denylist == root or root in denylist.parents:
                raise ReleaseError("denylist_must_be_outside_kit")
            terms = [line.strip() for line in denylist.read_text(encoding="utf-8").splitlines()
                     if line.strip() and not line.lstrip().startswith("#")]
            if not terms:
                raise ReleaseError("denylist_empty")
        audit(root, terms, regenerating_manifest=True)
        verify_skill_mirrors(root)
        manifest(root)
        audit(root, terms)
        entries = files_under(root)
        prefix = "android-tv-launcher-kit/"
        with tempfile.TemporaryDirectory(prefix="tv-kit-release-") as temporary:
            staging = Path(temporary)
            archive = staging / "release.zip"
            with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
                for relative, content in sorted(entries.items()):
                    info = zipfile.ZipInfo(prefix + relative, date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    info.compress_type = zipfile.ZIP_DEFLATED
                    z.writestr(info, content)
            with zipfile.ZipFile(archive) as z:
                if set(z.namelist()) != {prefix + relative for relative in entries}:
                    raise ReleaseError("archive_member_mismatch")
                if any(Path(name).is_absolute() or ".." in Path(name).parts for name in z.namelist()):
                    raise ReleaseError("archive_path_invalid")
                if z.testzip() is not None:
                    raise ReleaseError("archive_crc_failed")
                z.extractall(staging / "extracted")
            unpacked = staging / "extracted/android-tv-launcher-kit"
            audit(unpacked, terms)
            verify_skill_mirrors(unpacked)
            if files_under(unpacked) != entries:
                raise ReleaseError("archive_content_mismatch")
            # Exclusive creation also prevents a concurrent output from being overwritten.
            with output.open("xb") as handle, archive.open("rb") as source:
                shutil.copyfileobj(source, handle)
        print(json.dumps({"status": "audited-and-packaged", "archive": output.name,
                          "files": len(entries), "bytes": output.stat().st_size,
                          "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                          "source_and_extracted_archive_audited": True}, indent=2))
        return 0
    except (OSError, ValueError, ReleaseError, zipfile.BadZipFile):
        print("Release stopped; inspect the audit findings or command arguments. No existing archive was overwritten.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
