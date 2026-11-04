"""Instance 設定純函式測試（不實際呼叫 wsl.exe）。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.distro_settings import (
    build_proxy_script,
    conf_bool,
    conf_value,
    is_sparse,
    parse_conf,
    parse_proxy_script,
    set_conf_values,
)

BASE_CONF = """# 既有註解
[automount]
enabled = true
options = "metadata"

[interop]
appendWindowsPath = true

[user]
default = ubuntu
"""


class ParseConfTest(unittest.TestCase):
    def test_parse_sections(self) -> None:
        conf = parse_conf(BASE_CONF)
        self.assertEqual(conf["automount"]["enabled"], "true")
        self.assertEqual(conf["interop"]["appendwindowspath"], "true")
        self.assertEqual(conf["user"]["default"], "ubuntu")

    def test_parse_ignores_invalid_lines(self) -> None:
        conf = parse_conf("[network]\nhostname = demo\nbroken line\n")
        self.assertEqual(conf["network"]["hostname"], "demo")

    def test_defaults(self) -> None:
        conf = parse_conf("")
        self.assertFalse(conf_bool(conf, "boot", "systemd", False))
        self.assertTrue(conf_bool(conf, "interop", "appendwindowspath", True))
        self.assertTrue(conf_bool(conf, "automount", "enabled", True))
        self.assertEqual(conf_value(conf, "user", "default", "root"), "root")


class SetConfValuesTest(unittest.TestCase):
    def test_update_existing_keys(self) -> None:
        text = set_conf_values(
            BASE_CONF,
            {
                ("user", "default"): "root",
                ("interop", "appendWindowsPath"): "false",
            },
        )
        conf = parse_conf(text)
        self.assertEqual(conf["user"]["default"], "root")
        self.assertEqual(conf["interop"]["appendwindowspath"], "false")
        self.assertEqual(conf["automount"]["options"], '"metadata"')
        self.assertIn("# 既有註解", text)

    def test_insert_missing_key_and_section(self) -> None:
        text = set_conf_values(
            BASE_CONF,
            {
                ("automount", "mountFsTab"): "false",
                ("boot", "systemd"): "true",
            },
        )
        conf = parse_conf(text)
        self.assertEqual(conf["automount"]["mountfstab"], "false")
        self.assertEqual(conf["boot"]["systemd"], "true")
        self.assertIn("[boot]", text)

    def test_idempotent(self) -> None:
        once = set_conf_values(BASE_CONF, {("boot", "systemd"): "true"})
        twice = set_conf_values(once, {("boot", "systemd"): "true"})
        self.assertEqual(once, twice)

    def test_preserves_crlf(self) -> None:
        text = BASE_CONF.replace("\n", "\r\n")
        result = set_conf_values(text, {("user", "default"): "root"})
        self.assertIn("\r\n", result)
        self.assertNotIn("\n", result.replace("\r\n", ""))

    def test_create_from_empty_text(self) -> None:
        text = set_conf_values("", {("boot", "systemd"): "true"})
        self.assertEqual(parse_conf(text)["boot"]["systemd"], "true")
        self.assertTrue(text.startswith("[boot]"))


class ProxyScriptTest(unittest.TestCase):
    def test_build_script(self) -> None:
        script = build_proxy_script("192.168.160.1", 7890)
        self.assertIn("# Managed by WSL Deck", script)
        self.assertIn('ALL_PROXY="socks5h://192.168.160.1:7890"', script)
        self.assertIn('HTTPS_PROXY="$ALL_PROXY"', script)
        self.assertIn('NO_PROXY="localhost,127.0.0.1,::1"', script)

    def test_parse_script(self) -> None:
        script = build_proxy_script("192.168.160.1", 7890)
        self.assertEqual(
            parse_proxy_script(script), (True, "192.168.160.1", 7890)
        )

    def test_parse_missing_script(self) -> None:
        self.assertEqual(parse_proxy_script(""), (False, "", 0))
        self.assertEqual(parse_proxy_script("# no proxy here"), (False, "", 0))


class _FakeProc:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode


class SparseTest(unittest.TestCase):
    def test_not_sparse(self) -> None:
        proc = _FakeProc("This file is NOT set as sparse\n")
        with patch("app.distro_settings.subprocess.run", return_value=proc):
            self.assertFalse(is_sparse(r"D:\test.vhdx"))

    def test_sparse(self) -> None:
        proc = _FakeProc("This file is set as sparse\n")
        with patch("app.distro_settings.subprocess.run", return_value=proc):
            self.assertTrue(is_sparse(r"D:\test.vhdx"))

    def test_unknown_output(self) -> None:
        proc = _FakeProc("unexpected\n")
        with patch("app.distro_settings.subprocess.run", return_value=proc):
            self.assertIsNone(is_sparse(r"D:\test.vhdx"))

    def test_empty_path(self) -> None:
        self.assertIsNone(is_sparse(""))


if __name__ == "__main__":
    unittest.main()
