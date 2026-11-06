#!/usr/bin/env python3
"""Offline resource, Java and DEX compilation with explicitly supplied local tools.

This does not sign, install, deploy or fetch anything. It is a useful independent
check when Gradle/AGP caches are absent, not a substitute for Gradle validation.
"""
from pathlib import Path
import argparse
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--android-jar", required=True, type=Path, help="Android API 34 compile jar")
parser.add_argument("--framework", type=Path, help="Resource framework; defaults to android.jar")
parser.add_argument("--aapt2", required=True, type=Path, help="Existing local aapt2 executable")
parser.add_argument("--d8-jar", required=True, type=Path, help="Local jar containing com.android.tools.r8.D8")
parser.add_argument("--jdk", required=True, type=Path, help="Existing JDK 17+ home")
args = parser.parse_args()
for path in [args.android_jar, args.framework or args.android_jar, args.aapt2,
             args.d8_jar, args.jdk / "bin/javac", args.jdk / "bin/java"]:
    if not path.is_file():
        raise SystemExit("A supplied local tool or platform file is missing.")


def run(*command):
    # Tools may print local diagnostics; none are saved into the shareable project.
    subprocess.run([str(argument) for argument in command], check=True)


with tempfile.TemporaryDirectory(prefix="quiet-tv-android-") as temporary:
    for module, package in [("app", "org.example.tvlauncher"),
                            ("boot-bridge", "org.example.tvlauncher.bridge")]:
        main = ROOT / module / "src/main"
        work = Path(temporary) / module
        for directory in [work, work / "gen", work / "classes", work / "dex"]:
            directory.mkdir(parents=True, exist_ok=True)
        manifest = ET.parse(main / "AndroidManifest.xml")
        manifest.getroot().set("package", package)
        # AGP normally fills these from the module's defaultConfig.
        manifest_path = work / "AndroidManifest.xml"
        manifest.write(manifest_path, encoding="utf-8", xml_declaration=True)
        run(args.aapt2, "compile", "--dir", main / "res", "-o", work / "res.zip")
        run(args.aapt2, "link", "-o", work / "resources.apk", "-I",
            args.framework or args.android_jar, "--manifest", manifest_path,
            "--java", work / "gen", "--min-sdk-version", "26", "--target-sdk-version", "34",
            "--version-code", "1", "--version-name", "1.0.0", work / "res.zip")
        sources = sorted((main / "java").rglob("*.java")) + sorted((work / "gen").rglob("*.java"))
        run(args.jdk / "bin/javac", "-encoding", "UTF-8", "-source", "8", "-target", "8",
            "-implicit:none", "-sourcepath", "", "-classpath", args.android_jar,
            "-d", work / "classes", *sources)
        classes_jar = work / "classes.jar"
        with zipfile.ZipFile(classes_jar, "w", zipfile.ZIP_DEFLATED) as archive:
            for compiled in sorted((work / "classes").rglob("*.class")):
                relative = compiled.relative_to(work / "classes")
                if not relative.as_posix().startswith(package.replace(".", "/") + "/"):
                    raise SystemExit("Unexpected compiled class outside the application package.")
                archive.write(compiled, relative.as_posix())
        run(args.jdk / "bin/java", "-cp", args.d8_jar, "com.android.tools.r8.D8",
            "--lib", args.android_jar, "--lib", args.jdk, "--min-api", "26",
            "--output", work / "dex", classes_jar)
        if not (work / "dex/classes.dex").is_file():
            raise SystemExit("DEX output is missing.")
        print(module + ": resources, Java and DEX compiled.", flush=True)
print("Offline compilation passed; temporary outputs removed. No signing or device testing performed.")
