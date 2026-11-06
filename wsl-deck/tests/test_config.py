"""配置與命令模板測試。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.config import COMMAND_KEYS, Config, ConfigError, split_command


class ConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "config.json"
        self.config = Config(self.path)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_default_config_created(self) -> None:
        self.assertTrue(self.path.exists())
        self.assertEqual(set(self.config.data["commands"]), set(COMMAND_KEYS))

    def test_workspace_skeleton_defaults(self) -> None:
        workspace = Path(self.config.data["workspace_root"])
        self.assertEqual(Path(self.config.data["distro_root"]), workspace / "instances")
        self.assertEqual(Path(self.config.data["backup_root"]), workspace / "backups")
        self.assertEqual(Path(self.config.data["snapshot_root"]), workspace / "snapshots")
        self.assertEqual(
            self.config.data["snapshot_keep"],
            {"last": 10, "daily": 7, "weekly": 4, "monthly": 6},
        )

    def test_legacy_config_derives_workspace_but_keeps_instance_dir(self) -> None:
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        legacy["distro_root"] = r"D:\VirtualMachiles\wsl"
        legacy["backup_root"] = r"D:\VirtualMachiles\wsl\backups"
        legacy.pop("workspace_root", None)
        legacy.pop("snapshot_root", None)
        legacy.pop("snapshot_keep", None)
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = Config(self.path)
        self.assertEqual(migrated.data["workspace_root"], r"D:\VirtualMachiles\wsl")
        self.assertEqual(migrated.data["distro_root"], r"D:\VirtualMachiles\wsl")
        self.assertEqual(migrated.data["snapshot_root"], r"D:\VirtualMachiles\wsl\snapshots")
        self.assertEqual(
            migrated.data["snapshot_keep"],
            {"last": 10, "daily": 7, "weekly": 4, "monthly": 6},
        )
        self.assertEqual(
            migrated.instance_root(), Path(r"D:\VirtualMachiles\wsl\instances")
        )

    def test_instance_root_defaults_to_instances(self) -> None:
        self.assertEqual(self.config.instance_root(), self.config.workspace().instances)

    def test_instance_root_legacy_layout_uses_instances(self) -> None:
        self.config.data["workspace_root"] = r"D:\VirtualMachiles\wsl"
        self.config.data["distro_root"] = r"D:\VirtualMachiles\wsl"
        self.assertEqual(
            self.config.instance_root(), Path(r"D:\VirtualMachiles\wsl\instances")
        )

    def test_instance_root_keeps_custom_path(self) -> None:
        self.config.data["workspace_root"] = r"D:\VirtualMachiles\wsl"
        self.config.data["distro_root"] = r"E:\WSL\instances"
        self.assertEqual(self.config.instance_root(), Path(r"E:\WSL\instances"))

    def test_workspace_resolves_relative_paths(self) -> None:
        self.config.data["workspace_root"] = "ws"
        self.config.data["snapshot_root"] = "ws/snapshots"
        paths = self.config.workspace()
        self.assertEqual(paths.root, self.path.parent / "ws")
        self.assertEqual(paths.snapshots, self.path.parent / "ws" / "snapshots")

    def test_invalid_snapshot_keep_rejected(self) -> None:
        for value in ("keep", {"last": -1}, {"last": "10"}, {"last": True}):
            with self.subTest(value=value):
                self.config.data["snapshot_keep"] = value
                with self.assertRaises(ConfigError):
                    self.config.save()

    def test_empty_workspace_rejected(self) -> None:
        self.config.data["workspace_root"] = " "
        with self.assertRaises(ConfigError):
            self.config.save()

    def test_command_substitution_with_spaces(self) -> None:
        command = self.config.command(
            "import_vhd",
            name="node22",
            install_dir=r"D:\some where\node22",
            file=r"D:\backups\ubuntu.vhdx",
            version=2,
        )
        self.assertEqual(command[0], "wsl.exe")
        self.assertIn("node22", command)
        self.assertIn(r"D:\some where\node22", command)
        self.assertIn(r"D:\backups\ubuntu.vhdx", command)
        self.assertEqual(command[-1], "--vhd")

    def test_missing_placeholder_raises(self) -> None:
        with self.assertRaises(ConfigError):
            self.config.command("import_vhd", name="node22")

    def test_unknown_command_raises(self) -> None:
        with self.assertRaises(ConfigError):
            self.config.command("move")

    def test_split_command_keeps_backslashes(self) -> None:
        self.assertEqual(
            split_command(r'wsl.exe --import "x" "D:\a\b" "D:\c.vhdx"'),
            ["wsl.exe", "--import", "x", r"D:\a\b", r"D:\c.vhdx"],
        )

    def test_get_with_default(self) -> None:
        self.assertEqual(self.config.get("poll_interval", 10), 10)
        self.assertEqual(self.config.get("missing_key", "fallback"), "fallback")

    def test_remove_port_forwards(self) -> None:
        self.config.data["port_forwards"] = [
            {"label": "web", "distro": "node22", "windows_port": 8080, "distro_port": 80},
            {"label": "api", "distro": "node22", "windows_port": 8081, "distro_port": 81},
            {"label": "ssh", "distro": "ubuntu", "windows_port": 2222, "distro_port": 22},
        ]
        self.config.save()
        self.assertEqual(self.config.remove_port_forwards("node22"), 2)
        self.assertEqual(len(self.config.data["port_forwards"]), 1)
        self.assertEqual(self.config.data["port_forwards"][0]["distro"], "ubuntu")

    def test_port_rule_defaults(self) -> None:
        self.config.data["port_forwards"] = [
            {"label": "web", "distro": "node22", "windows_port": 8080, "distro_port": 80}
        ]
        self.config.save()
        self.assertTrue(self.config.data["port_forwards"][0]["allow_lan"])
        self.assertTrue(self.config.data["port_forwards"][0]["enabled"])
        self.assertEqual(len(self.config.port_forwards_for("node22")), 1)

    def test_duplicate_windows_port_rejected(self) -> None:
        self.config.data["port_forwards"] = [
            {"label": "a", "distro": "node22", "windows_port": 8080, "distro_port": 80},
            {"label": "b", "distro": "ubuntu", "windows_port": 8080, "distro_port": 81},
        ]
        with self.assertRaises(ConfigError):
            self.config.save()

    def test_set_port_forwards_for(self) -> None:
        self.config.set_port_forwards_for("node22", [
            {"label": "web", "distro": "node22", "windows_port": 8080,
             "distro_port": 80, "allow_lan": True, "enabled": True},
        ])
        self.assertEqual(len(self.config.port_forwards_for("node22")), 1)
        self.assertEqual(len(self.config.data["port_forwards"]), 1)

    def test_instance_network_round_trip(self) -> None:
        network = {
            "enabled": True,
            "scope": "temporary",
            "ip": "192.168.163.241",
            "services": ["mysql"],
        }
        self.config.set_instance_network("wsl-mysql", network)
        self.assertEqual(self.config.instance_network("wsl-mysql"), network)
        self.config.remove_instance_network("wsl-mysql")
        self.assertEqual(self.config.instance_network("wsl-mysql"), {})

    def test_disabled_instance_network_is_removed(self) -> None:
        self.config.set_instance_network(
            "wsl-mysql",
            {"enabled": False, "scope": "temporary", "ip": "", "services": []},
        )
        self.assertEqual(self.config.data["instance_networks"], {})

    def test_instance_network_validation(self) -> None:
        cases = [
            {"enabled": True, "scope": "forever", "ip": "192.168.1.5", "services": ["mysql"]},
            {"enabled": True, "scope": "temporary", "ip": "bad", "services": ["mysql"]},
            {"enabled": True, "scope": "temporary", "ip": "127.0.0.1", "services": ["mysql"]},
            {"enabled": True, "scope": "temporary", "ip": "192.168.163.241", "services": []},
            {"enabled": True, "scope": "temporary", "ip": "192.168.163.241", "services": ["bad name"]},
        ]
        for network in cases:
            with self.subTest(network=network):
                self.config.data["instance_networks"] = {"wsl-mysql": network}
                with self.assertRaises(ConfigError):
                    self.config.save()

    def test_duplicate_isolated_ip_rejected(self) -> None:
        self.config.data["instance_networks"] = {
            "wsl-mysql": {
                "enabled": True,
                "scope": "temporary",
                "ip": "192.168.163.241",
                "services": ["mysql"],
            },
            "wsl-tomcat9": {
                "enabled": True,
                "scope": "permanent",
                "ip": "192.168.163.241",
                "services": ["tomcat"],
            },
        }
        with self.assertRaises(ConfigError):
            self.config.save()

    def test_migrate_legacy_keys(self) -> None:
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        legacy.pop("advanced_mode", None)
        legacy.pop("close_to_tray", None)
        legacy["preview_commands"] = True
        legacy["minimize_to_tray"] = False
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        migrated = Config(self.path)
        self.assertTrue(migrated.data["advanced_mode"])
        self.assertFalse(migrated.data["close_to_tray"])
        self.assertNotIn("preview_commands", migrated.data)
        self.assertNotIn("minimize_to_tray", migrated.data)
        self.assertTrue(
            self.path.with_name("config.json.pre-m5.bak").exists()
        )

    def test_missing_keys_filled_on_load(self) -> None:
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        for key in ("theme", "poll_interval", "system_instances"):
            legacy.pop(key, None)
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        reloaded = Config(self.path)
        self.assertEqual(reloaded.data["theme"], "system")
        self.assertEqual(reloaded.data["poll_interval"], 10)
        self.assertEqual(
            reloaded.data["system_instances"],
            ["docker-desktop", "docker-desktop-data"],
        )

    def test_view_mode_defaults_to_card(self) -> None:
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        legacy.pop("view_mode", None)
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        reloaded = Config(self.path)
        self.assertEqual(reloaded.data["view_mode"], "card")

    def test_view_mode_accepts_list(self) -> None:
        self.config.data["view_mode"] = "list"
        self.config.save()
        self.assertEqual(Config(self.path).data["view_mode"], "list")

    def test_invalid_view_mode_rejected(self) -> None:
        for value in ("table", "", 1, None):
            with self.subTest(value=value):
                self.config.data["view_mode"] = value
                with self.assertRaises(ConfigError):
                    self.config.save()

    def test_proxy_defaults(self) -> None:
        self.assertEqual(
            self.config.data["proxy"],
            {"enabled": False, "host": "127.0.0.1", "port": 7890},
        )

    def test_missing_proxy_filled_on_load(self) -> None:
        legacy = json.loads(self.path.read_text(encoding="utf-8"))
        legacy.pop("proxy", None)
        self.path.write_text(json.dumps(legacy), encoding="utf-8")

        reloaded = Config(self.path)
        self.assertFalse(reloaded.data["proxy"]["enabled"])
        self.assertEqual(reloaded.data["proxy"]["host"], "127.0.0.1")
        self.assertEqual(reloaded.data["proxy"]["port"], 7890)

    def test_invalid_proxy_rejected(self) -> None:
        for value in ("127.0.0.1:7890", {}, {"enabled": "yes", "host": "x", "port": 1}):
            with self.subTest(value=value):
                self.config.data["proxy"] = value
                with self.assertRaises(ConfigError):
                    self.config.save()

    def test_invalid_proxy_port_rejected(self) -> None:
        for port in (0, 65536, "7890", True):
            with self.subTest(port=port):
                self.config.data["proxy"] = {
                    "enabled": False, "host": "127.0.0.1", "port": port,
                }
                with self.assertRaises(ConfigError):
                    self.config.save()

    def test_invalid_theme_rejected(self) -> None:
        self.config.data["theme"] = "blue"
        with self.assertRaises(ConfigError):
            self.config.save()

    def test_invalid_poll_interval_rejected(self) -> None:
        for value in (1, 601, "10", True):
            with self.subTest(value=value):
                self.config.data["poll_interval"] = value
                with self.assertRaises(ConfigError):
                    self.config.save()

    def test_invalid_system_instances_rejected(self) -> None:
        for value in ("docker-desktop", ["docker-desktop", ""], [1]):
            with self.subTest(value=value):
                self.config.data["system_instances"] = value
                with self.assertRaises(ConfigError):
                    self.config.save()


if __name__ == "__main__":
    unittest.main()
