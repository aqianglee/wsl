"""network 純函式測試。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.network import (
    PortProxyEntry,
    apply_rules,
    build_admin_job,
    firewall_rule_name,
    parse_listen_ports,
    parse_portproxy,
    rule_status,
    validate_rule,
)

PORT_PROXY_TEXT = """
Listen on ipv4:             Connect to ipv4:

Address         Port        Address         Port

--------------- ----------  --------------- ----------

*               8080        172.20.10.2     80
0.0.0.0         8081        172.20.10.2     81
"""


class PortProxyParseTest(unittest.TestCase):
    def test_parse(self) -> None:
        self.assertEqual(
            parse_portproxy(PORT_PROXY_TEXT),
            [
                PortProxyEntry(8080, "172.20.10.2", 80),
                PortProxyEntry(8081, "172.20.10.2", 81),
            ],
        )

    def test_empty(self) -> None:
        self.assertEqual(parse_portproxy(""), [])


class ScanParseTest(unittest.TestCase):
    def test_ss_output(self) -> None:
        text = (
            "State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process\n"
            "LISTEN 0      4096   0.0.0.0:80         0.0.0.0:*\n"
            "LISTEN 0      128    [::]:22            [::]:*\n"
            "LISTEN 0      128    127.0.0.1:3000     0.0.0.0:*\n"
        )
        self.assertEqual(parse_listen_ports(text), [22, 80, 3000])

    def test_netstat_output(self) -> None:
        text = (
            "tcp        0      0 0.0.0.0:8080        0.0.0.0:*               LISTEN\n"
            "tcp6       0      0 :::22               :::*                    LISTEN\n"
            "udp        0      0 0.0.0.0:53          0.0.0.0:*\n"
        )
        self.assertEqual(parse_listen_ports(text), [22, 8080])


class RuleValidationTest(unittest.TestCase):
    def test_valid(self) -> None:
        rule = {"label": "web", "distro": "node22", "windows_port": 8080,
                "distro_port": 80, "allow_lan": True, "enabled": True}
        validate_rule(rule, [])

    def test_duplicate_windows_port(self) -> None:
        existing = [{"label": "a", "distro": "ubuntu", "windows_port": 8080,
                     "distro_port": 80, "allow_lan": True, "enabled": True}]
        rule = {"label": "b", "distro": "node22", "windows_port": 8080,
                "distro_port": 81, "allow_lan": True, "enabled": True}
        with self.assertRaises(ValueError):
            validate_rule(rule, existing)

    def test_port_range(self) -> None:
        rule = {"label": "x", "distro": "node22", "windows_port": 70000,
                "distro_port": 0, "allow_lan": True, "enabled": True}
        with self.assertRaises(ValueError):
            validate_rule(rule, [])


class StatusTest(unittest.TestCase):
    def test_statuses(self) -> None:
        rule = {"windows_port": 8080, "distro_port": 80, "enabled": True}
        self.assertEqual(rule_status(rule, False, "", []), "待啟動")
        self.assertEqual(rule_status(rule, True, "172.20.10.2", []), "待套用")
        entries = [PortProxyEntry(8080, "172.20.10.2", 80)]
        self.assertEqual(rule_status(rule, True, "172.20.10.2", entries), "已套用")
        rule["enabled"] = False
        self.assertEqual(
            rule_status(rule, True, "172.20.10.2", entries), "待套用"
        )
        self.assertEqual(rule_status(rule, True, "172.20.10.2", []), "已停用")


class JobTest(unittest.TestCase):
    def test_build_job(self) -> None:
        rules = [
            {"label": "web", "distro": "node22", "windows_port": 8080,
             "distro_port": 80, "allow_lan": True, "enabled": True},
            {"label": "off", "distro": "node22", "windows_port": 8081,
             "distro_port": 81, "allow_lan": True, "enabled": False},
        ]
        job = build_admin_job(
            [("node22", "172.20.10.2", rules)], [("node22", 8090)]
        )
        self.assertEqual(job["portproxy_delete"], [8080, 8081, 8090])
        self.assertEqual(len(job["portproxy_add"]), 1)
        self.assertEqual(job["portproxy_add"][0]["windows_port"], 8080)
        self.assertEqual(len(job["firewall_add"]), 1)
        self.assertEqual(job["firewall_add"][0]["windows_port"], 8080)
        self.assertEqual(job["firewall_add"][0]["name"], "WSL Deck node22 8080")
        self.assertIn(8090, [item["windows_port"] for item in job["firewall_delete"]])

    def test_firewall_name(self) -> None:
        self.assertEqual(firewall_rule_name("node22", 8080), "WSL Deck node22 8080")


class ApplyRulesTest(unittest.TestCase):
    def test_skip_occupied_port(self) -> None:
        rules = [{"label": "web", "distro": "node22", "windows_port": 8080,
                  "distro_port": 80, "allow_lan": True, "enabled": True}]
        with patch("app.network.show_portproxy", return_value=[]), \
             patch("app.network.get_distro_ip", return_value="172.20.10.2"), \
             patch("app.network.port_occupied", return_value=True), \
             patch("app.admin.run_admin_job") as admin:
            result = apply_rules([("node22", rules)])
        self.assertEqual(
            result.warnings, ["Windows 端口 8080 已被其他程式佔用，已略過"]
        )
        admin.assert_not_called()


if __name__ == "__main__":
    unittest.main()
