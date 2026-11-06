"""C 方案（netns）命令產生與設定測試。"""

from __future__ import annotations

import unittest

from app import netns


class IdentifierTest(unittest.TestCase):
    def test_interface_names_fit_linux_limit(self) -> None:
        for distro in ("wsl-mysql", "wsl-tomcat9", "a-very-long-instance-name"):
            self.assertLessEqual(len(netns.host_if(distro)), 15)
            self.assertLessEqual(len(netns.peer_if(distro)), 15)

    def test_names_are_stable_and_distinct(self) -> None:
        self.assertEqual(netns.netns_name("wsl-mysql"), netns.netns_name("wsl-mysql"))
        self.assertNotEqual(netns.netns_name("wsl-mysql"), netns.netns_name("wsl-tomcat9"))

    def test_uplink_address_is_link_local(self) -> None:
        address = netns.uplink_ip("wsl-mysql")
        self.assertTrue(address.startswith("169.254."))


class ScriptTest(unittest.TestCase):
    def test_up_script_binds_requested_ip(self) -> None:
        script = netns.build_up_script("wsl-mysql", "192.168.163.241", idempotent=False)
        self.assertIn("192.168.163.241", script)
        self.assertIn("proxy_arp", script)
        self.assertIn("ip netns add", script)
        self.assertIn(netns.netns_name("wsl-mysql"), script)

    def test_permanent_script_is_idempotent(self) -> None:
        script = netns.build_up_script("wsl-mysql", "192.168.163.241", idempotent=True)
        self.assertIn("grep -qx", script)

    def test_down_script_removes_namespace(self) -> None:
        script = netns.build_down_script("wsl-mysql", "192.168.163.241")
        self.assertIn("ip netns del", script)
        self.assertIn(netns.host_if("wsl-mysql"), script)


class UnitTest(unittest.TestCase):
    def test_unit_orders_before_services(self) -> None:
        text = netns.build_unit(["mysql", "tomcat"])
        self.assertIn("Before=mysql.service tomcat.service", text)
        self.assertIn("RemainAfterExit=yes", text)
        self.assertIn("ExecStop=-", text)

    def test_dropin_sets_namespace_path(self) -> None:
        text = netns.build_dropin("wsl-mysql")
        self.assertIn("NetworkNamespacePath=/run/netns/wsl-deck-", text)
        self.assertIn("After=wsl-deck-netns.service", text)


class ParseExecStartTest(unittest.TestCase):
    def test_parses_argv(self) -> None:
        output = (
            "{ path=/usr/sbin/mysqld ; argv[]=/usr/sbin/mysqld --user=mysql ; "
            "ignore_errors=no }"
        )
        self.assertEqual(
            netns.parse_exec_start(output),
            ["/usr/sbin/mysqld", "--user=mysql"],
        )

    def test_empty(self) -> None:
        self.assertEqual(netns.parse_exec_start(""), [])
        self.assertEqual(netns.parse_exec_start("{ path= ; argv[]= ; }"), [])


class NetworkConfigTest(unittest.TestCase):
    def test_disabled_returns_none(self) -> None:
        self.assertIsNone(netns.NetworkConfig.from_raw({"enabled": False}))

    def test_incomplete_returns_none(self) -> None:
        self.assertIsNone(
            netns.NetworkConfig.from_raw({"enabled": True, "ip": "", "services": ["mysql"]})
        )
        self.assertIsNone(
            netns.NetworkConfig.from_raw(
                {"enabled": True, "ip": "192.168.1.5", "scope": "forever", "services": ["mysql"]}
            )
        )
        self.assertIsNone(
            netns.NetworkConfig.from_raw(
                {"enabled": True, "ip": "192.168.1.5", "services": []}
            )
        )

    def test_valid(self) -> None:
        config = netns.NetworkConfig.from_raw(
            {
                "enabled": True,
                "scope": "permanent",
                "ip": "192.168.163.241",
                "services": ["mysql"],
            }
        )
        self.assertIsNotNone(config)
        assert config is not None
        self.assertTrue(config.permanent)
        self.assertIn("192.168.163.241", config.state_text())

    def test_service_normalization(self) -> None:
        self.assertEqual(netns.normalize_service("mysql"), "mysql.service")
        self.assertEqual(netns.normalize_service("mysql.service"), "mysql.service")

    def test_transient_unit_round_trip(self) -> None:
        transient = netns.transient_unit("wsl-mysql", "mysql.service")
        self.assertTrue(transient.startswith(netns.transient_prefix("wsl-mysql")))
        self.assertEqual(
            netns.service_from_transient("wsl-mysql", transient), "mysql.service"
        )
        self.assertEqual(netns.service_from_transient("wsl-mysql", "other.service"), "")
        self.assertEqual(
            netns.service_from_transient("wsl-mysql", netns.transient_prefix("wsl-mysql")),
            "",
        )


if __name__ == "__main__":
    unittest.main()
