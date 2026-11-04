"""全域代理設定純函式測試。"""

from __future__ import annotations

import os
import unittest

from app.proxy import (
    PROXY_ENV_KEYS,
    ProxyConfig,
    apply_runtime,
    current_proxy,
    parse_config,
    proxy_url,
)


class ParseConfigTest(unittest.TestCase):
    def test_defaults_on_invalid(self) -> None:
        self.assertEqual(parse_config(None), ProxyConfig(False, "127.0.0.1", 7890))
        self.assertEqual(
            parse_config({"port": "7890"}), ProxyConfig(False, "127.0.0.1", 0)
        )

    def test_parse_values(self) -> None:
        config = parse_config(
            {"enabled": True, "host": " 192.168.160.1 ", "port": 7890}
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.host, "192.168.160.1")
        self.assertEqual(config.port, 7890)

    def test_proxy_url(self) -> None:
        self.assertEqual(
            proxy_url(ProxyConfig(True, "192.168.160.1", 7890)),
            "socks5h://192.168.160.1:7890",
        )


class ApplyRuntimeTest(unittest.TestCase):
    def setUp(self) -> None:
        self._original = {key: os.environ.get(key) for key in PROXY_ENV_KEYS}
        for key in PROXY_ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        apply_runtime(ProxyConfig(False, "", 0))
        for key, value in self._original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_enable_sets_environment(self) -> None:
        apply_runtime(ProxyConfig(True, "192.168.160.1", 7890))
        self.assertEqual(
            os.environ["ALL_PROXY"], "socks5h://192.168.160.1:7890"
        )
        self.assertEqual(os.environ["HTTPS_PROXY"], os.environ["ALL_PROXY"])
        self.assertEqual(os.environ["NO_PROXY"], "localhost,127.0.0.1,::1")
        self.assertIsNotNone(current_proxy())

    def test_disable_restores_previous_values(self) -> None:
        os.environ["NO_PROXY"] = "custom"
        apply_runtime(ProxyConfig(True, "192.168.160.1", 7890))
        apply_runtime(ProxyConfig(False, "", 0))
        self.assertEqual(os.environ.get("NO_PROXY"), "custom")
        self.assertNotIn("ALL_PROXY", os.environ)
        self.assertIsNone(current_proxy())

    def test_invalid_config_is_ignored(self) -> None:
        apply_runtime(ProxyConfig(True, "", 7890))
        self.assertNotIn("ALL_PROXY", os.environ)


if __name__ == "__main__":
    unittest.main()
