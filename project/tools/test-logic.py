#!/usr/bin/env python3
"""Run pure Java regressions using an existing JDK; no SDK or downloads needed."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def jdk_tool(name):
    java_home = os.environ.get("JAVA_HOME")
    candidate = Path(java_home) / "bin" / name if java_home else None
    if candidate and candidate.is_file():
        return str(candidate)
    executable = shutil.which(name)
    if not executable:
        raise SystemExit("An existing JDK 17 or newer is required.")
    return executable


def run_suite(module, package, classes, tests, build):
    source = ROOT / module / "src/main/java" / package.replace(".", "/")
    sources = [source / (name + ".java") for name in classes]
    test_sources = sorted((ROOT / "tests" / tests).glob("*Test.java"))
    destination = build / tests
    destination.mkdir()
    subprocess.run([jdk_tool("javac"), "--release", "8", "-encoding", "UTF-8",
                    "-d", str(destination), *map(str, sources + test_sources)], check=True)
    for test in test_sources:
        subprocess.run([jdk_tool("java"), "-cp", str(destination), package + "." + test.stem], check=True)


with tempfile.TemporaryDirectory(prefix="quiet-tv-logic-") as temporary:
    build = Path(temporary)
    run_suite("app", "org.example.tvlauncher",
              ["OwnedKeyPress", "IntroPlayback", "DrawerNavigation"], "app", build)
    run_suite("boot-bridge", "org.example.tvlauncher.bridge",
              ["OwnedKeyPress", "ForegroundHandoff", "ColdBootPolicy", "BootDecision"], "bridge", build)
print("All 7 pure Java suites passed. Temporary class files removed.")
