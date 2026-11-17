from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import backend


class BackendParsingTests(unittest.TestCase):
    def test_pacman_inventory_marks_foreign_packages(self):
        output = """Name            : example-app
Version         : 2.4-1
Description     : Example desktop app
Installed Size  : 4.20 MiB
Depends On      : qt6-base
Install Date    : Mon 01 Jan 2024 10:00:00 AM WIB

Name            : base
Version         : 1.0-1
Description     : Base system
Installed Size  : 12.00 MiB
Depends On      : None
Install Date    : Mon 01 Jan 2024 10:00:00 AM WIB
"""
        packages = backend._parse_pacman_qi_output(output, {"example-app"})
        self.assertEqual([item.source for item in packages], ["AUR", "Pacman"])
        self.assertEqual(packages[0].version, "2.4-1")
        self.assertEqual(packages[0].dependencies, "qt6-base")

    def test_upgrade_parser_ignores_non_upgrade_lines(self):
        parsed = backend._parse_upgrade_lines(
            "example-app 1.0-1 -> 1.1-1\nthere is nothing to do\nfoo 3 -> 4\n"
        )
        self.assertEqual(parsed, {"example-app": "1.1-1", "foo": "4"})


class BackendOperationTests(unittest.TestCase):
    def test_flatpak_update_scan_checks_each_installation(self):
        system = backend.Package("Editor", "1", "1 GiB", "Flatpak", app_id="org.example.Editor", installation="system")
        user = backend.Package("Chat", "2", "2 GiB", "Flatpak", app_id="org.example.Chat", installation="user")

        def fake_run(command, **kwargs):
            args = list(command)
            if args[:2] == ["pacman", "-Qu"]:
                return backend.CommandResult(tuple(args), 0, "", "", 0.01)
            if args[-1:] == ["-Qua"]:
                return backend.CommandResult(tuple(args), 0, "", "", 0.01)
            if args[:2] == ["flatpak", "list"]:
                output = "Editor\torg.example.Editor\t1\t1 GiB\tflathub\tsystem\tEditor app\n"
                output += "Chat\torg.example.Chat\t2\t2 GiB\tflathub\tuser\tChat app\n"
                return backend.CommandResult(tuple(args), 0, output, "", 0.01)
            if "remote-ls" in args and "--system" in args:
                return backend.CommandResult(tuple(args), 0, "org.example.Editor\t3\n", "", 0.01)
            if "remote-ls" in args and "--user" in args:
                return backend.CommandResult(tuple(args), 0, "org.example.Chat\t4\n", "", 0.01)
            raise AssertionError(args)

        with (
            patch.object(backend, "is_flatpak_available", return_value=True),
            patch.object(backend, "get_aur_helper", return_value="/usr/bin/paru"),
            patch.object(backend, "_run_command", side_effect=fake_run),
        ):
            result = backend.get_outdated_packages(force=True)

        self.assertEqual(result.updates[system.key], "3")
        self.assertEqual(result.updates[user.key], "4")
        self.assertEqual(result.warnings, [])

    def test_flatpak_uninstall_preserves_user_data(self):
        package = backend.Package("Chat", "2", "2 GiB", "Flatpak", app_id="org.example.Chat", installation="user")
        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = list(command)
            return backend.CommandResult(tuple(command), 0, "removed\n", "", 0.01)

        with (
            patch.object(backend, "is_flatpak_available", return_value=True),
            patch.object(backend, "_run_command", side_effect=fake_run),
        ):
            success, _message = backend._run_flatpak_uninstall([package], None)

        self.assertTrue(success)
        self.assertNotIn("--delete-data", captured["command"])
        self.assertIn("--user", captured["command"])

    def test_selected_pacman_update_uses_full_system_upgrade(self):
        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = list(command)
            return backend.CommandResult(tuple(command), 0, "updated\n", "", 0.01)

        with (
            patch.object(backend, "_check_pacman_lock", return_value=None),
            patch.object(backend, "is_pkexec_available", return_value=True),
            patch.object(backend, "_run_command", side_effect=fake_run),
        ):
            success, _message = backend._run_pacman_update(["example-app"], None)

        self.assertTrue(success)
        self.assertEqual(
            captured["command"],
            ["pkexec", "/usr/bin/pacman", "-Syu", "--needed", "--noconfirm", "example-app"],
        )

    def test_pacman_uninstall_keeps_remove_scope_and_config_files_conservative(self):
        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = list(command)
            return backend.CommandResult(tuple(command), 0, "removed\n", "", 0.01)

        with (
            patch.object(backend, "_check_pacman_lock", return_value=None),
            patch.object(backend, "is_pkexec_available", return_value=True),
            patch.object(backend, "_run_command", side_effect=fake_run),
        ):
            success, _message = backend._run_pacman_uninstall(["example-app"], None)

        self.assertTrue(success)
        self.assertEqual(
            captured["command"],
            ["pkexec", "/usr/bin/pacman", "--noconfirm", "-Rs", "example-app"],
        )

    def test_pacman_uninstall_stops_when_database_is_locked(self):
        with (
            patch.object(backend, "_check_pacman_lock", return_value="lock active"),
            patch.object(backend, "_run_command") as run_command,
        ):
            success, message = backend._run_pacman_uninstall(["example-app"], None)

        self.assertFalse(success)
        self.assertIn("lock active", message)
        run_command.assert_not_called()

    def test_aur_uses_a_sudo_askpass_wrapper(self):
        with tempfile.TemporaryDirectory() as temporary:
            log_path = Path(temporary) / "app.log"
            captured = {}

            def fake_run(command, **kwargs):
                captured["command"] = list(command)
                return backend.CommandResult(tuple(command), 0, "updated\n", "", 0.01)

            with (
                patch.object(backend, "get_log_path", return_value=log_path),
                patch.object(backend.shutil, "which", side_effect=lambda name: f"/usr/bin/{name}"),
                patch.object(backend, "_run_command", side_effect=fake_run),
            ):
                success, _message = backend._run_aur_update(["example-app"], "paru", None)

            self.assertTrue(success)
            self.assertIn("--sudo", captured["command"])
            wrapper = Path(captured["command"][captured["command"].index("--sudo") + 1])
            self.assertIn("sudo -A", wrapper.read_text(encoding="utf-8"))
            self.assertTrue((wrapper.parent / "sudo-askpass.py").exists())


if __name__ == "__main__":
    unittest.main()
