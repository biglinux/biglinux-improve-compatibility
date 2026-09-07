"""Exercise legacy startup without accessing host services."""

from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "biglinux-improve-compatibility/usr/bin/biglinux-improve-compatibility"
)
UNIT_DIRS = (
    "/etc/systemd/system", "/run/systemd/system",
    "/usr/local/lib/systemd/system", "/usr/lib/systemd/system",
)


class LegacyInitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="legacy-init-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.init = self.root / "etc/init.d"
        self.init.mkdir(parents=True)
        source = SOURCE.read_text()
        # Redirect filesystem probes; production code remains unchanged.
        for path in (*UNIT_DIRS, "/etc/init.d", "/usr/lib/modules", "/usr/src/linux"):
            source = source.replace(path, str(self.root) + path)
        self.script = self.root / "launcher"
        self.script.write_text(source)

    def add_service(self, name="legacy", header="#!/bin/sh", code=0):
        script = self.init / name
        script.write_text(
            f'{header}\nprintf "%s\\n" "$1" > "{self.root / (name + ".called")}"\n'
            f'exit {code}\n'
        )
        script.chmod(0o755)
        return script

    def run_launcher(self):
        return subprocess.run(
            ["bash", str(self.script)], capture_output=True, text=True, timeout=5,
        )

    def assert_not_started(self, name):
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / (name + ".called")).exists())

    def test_empty_directory(self):
        self.assertEqual(self.run_launcher().returncode, 0)

    def test_missing_directory(self):
        self.init.rmdir()
        self.assertEqual(self.run_launcher().returncode, 0)

    def test_sysv_script_starts(self):
        self.add_service("legacy printer")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "legacy printer.called").read_text(), "start\n")

    def test_non_executable_is_ignored(self):
        self.add_service().chmod(0o644)
        self.assert_not_started("legacy")

    def test_non_files_are_ignored(self):
        (self.init / "directory").mkdir()
        (self.init / "broken").symlink_to(self.root / "absent")
        self.assertEqual(self.run_launcher().returncode, 0)

    def test_missing_interpreter_is_ignored(self):
        self.add_service(header=f'#!{self.root}/missing-interpreter')
        self.assert_not_started("legacy")

    def test_openrc_is_ignored_even_with_available_interpreter(self):
        for name in ("openrc-run", "runscript"):
            with self.subTest(name=name):
                interpreter = self.root / name
                interpreter.symlink_to("/bin/sh")
                self.add_service(name, f'#!{interpreter}')
                self.assert_not_started(name)

    def test_native_unit_is_not_started_even_if_disabled(self):
        for directory in UNIT_DIRS:
            with self.subTest(directory=directory):
                name = directory.replace("/", "-")
                self.add_service(name)
                unit = self.root / directory.lstrip("/") / (name + ".service")
                unit.parent.mkdir(parents=True, exist_ok=True)
                unit.write_text("[Service]\nExecStart=/bin/true\n")
                self.assert_not_started(name)

    def test_masked_and_aliased_native_units_are_ignored(self):
        directory = self.root / "etc/systemd/system"
        directory.mkdir(parents=True)
        for name, target in (("masked", "/dev/null"), ("alias", "missing.service")):
            with self.subTest(name=name):
                self.add_service(name)
                (directory / (name + ".service")).symlink_to(target)
                self.assert_not_started(name)

    def test_real_failure_is_reported_and_other_scripts_continue(self):
        self.add_service("a-failing", code=7)
        self.add_service("z-working")
        result = self.run_launcher()
        self.assertEqual(result.returncode, 1)
        self.assertIn("a-failing", result.stderr)
        self.assertTrue((self.root / "z-working.called").exists())


if __name__ == "__main__":
    unittest.main()
