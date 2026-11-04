"""wsl.exe 輸出解析測試。"""

from __future__ import annotations

import unittest

from app.wsl import first_ipv4, is_system_distro, parse_list_output


class ParseListTest(unittest.TestCase):
    def test_english_output(self) -> None:
        text = (
            "  NAME      STATE           VERSION\n"
            "* Ubuntu    Running         2\n"
            "  node22    Stopped         2\n"
        )
        self.assertEqual(
            parse_list_output(text),
            [("Ubuntu", "Running", 2, True), ("node22", "Stopped", 2, False)],
        )

    def test_chinese_state_output(self) -> None:
        text = (
            "  NAME      STATE           VERSION\n"
            "* Ubuntu    运行中          2\n"
            "  node22    已停止          2\n"
        )
        self.assertEqual(
            parse_list_output(text),
            [("Ubuntu", "运行中", 2, True), ("node22", "已停止", 2, False)],
        )

    def test_null_bytes_and_blank_lines(self) -> None:
        text = "\x00  NAME  STATE  VERSION\x00\n\n  alms  Stopped  2\x00\n"
        self.assertEqual(parse_list_output(text), [("alms", "Stopped", 2, False)])


class SystemDistroTest(unittest.TestCase):
    def test_docker_prefix_is_system(self) -> None:
        self.assertTrue(is_system_distro("docker-desktop"))
        self.assertTrue(is_system_distro("docker-desktop-data"))
        self.assertFalse(is_system_distro("node22"))

    def test_extra_prefix(self) -> None:
        self.assertTrue(is_system_distro("podman-machine", ["podman-machine"]))


class IpParseTest(unittest.TestCase):
    def test_first_ipv4_skips_loopback(self) -> None:
        self.assertEqual(first_ipv4("127.0.0.1 172.20.10.2 10.0.0.1"), "172.20.10.2")

    def test_no_ipv4(self) -> None:
        self.assertEqual(first_ipv4(""), "")
        self.assertEqual(first_ipv4("not-an-ip"), "")


if __name__ == "__main__":
    unittest.main()
