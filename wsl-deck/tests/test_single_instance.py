"""單一實例守衛測試。"""

from __future__ import annotations

import unittest

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.single_instance import SingleInstance


class SingleInstanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.key = f"WSL Deck test {id(self)}"
        self.guard = SingleInstance(self.key)
        self.activated: list[bool] = []
        self.guard.activated.connect(lambda: self.activated.append(True))

    def tearDown(self) -> None:
        self.guard.close()

    def test_second_instance_is_rejected(self) -> None:
        self.assertTrue(self.guard.acquire())
        second = SingleInstance(self.key)
        self.assertFalse(second.acquire())

    def test_activate_existing_wakes_first_instance(self) -> None:
        self.assertTrue(self.guard.acquire())
        second = SingleInstance(self.key)
        self.assertFalse(second.acquire())
        self.assertTrue(second.activate_existing())
        QTest.qWait(200)
        self.assertEqual(self.activated, [True])

    def test_activate_without_server_fails(self) -> None:
        self.assertFalse(self.guard.activate_existing(timeout_ms=100, attempts=1))


if __name__ == "__main__":
    unittest.main()
