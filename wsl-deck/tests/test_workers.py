"""背景工作 stage 注入測試（不建立 QApplication）。"""

from __future__ import annotations

import unittest
from functools import partial

from app.ui.workers import TaskWorker, _accepts_stage


def plain(value: int) -> int:
    return value


def with_stage(value: int, stage=None) -> int:
    return value


def with_kwargs(value: int, **kwargs) -> int:
    return value


class AcceptsStageTest(unittest.TestCase):
    def test_plain_function(self) -> None:
        self.assertFalse(_accepts_stage(plain))

    def test_stage_parameter(self) -> None:
        self.assertTrue(_accepts_stage(with_stage))

    def test_partial_detects_remaining_parameters(self) -> None:
        self.assertFalse(_accepts_stage(partial(plain, 1)))
        self.assertTrue(_accepts_stage(partial(with_stage, 1)))

    def test_kwargs(self) -> None:
        self.assertTrue(_accepts_stage(with_kwargs))


class RunInjectionTest(unittest.TestCase):
    def test_stage_not_injected(self) -> None:
        calls: list[dict] = []

        def task(value: int) -> int:
            calls.append({"value": value})
            return value

        TaskWorker(task, 7, with_stage=True).run()
        self.assertEqual(calls, [{"value": 7}])

    def test_stage_injected(self) -> None:
        calls: list[dict] = []

        def task(value: int, stage=None) -> int:
            calls.append({"value": value, "stage": stage})
            return value

        TaskWorker(task, 7, with_stage=True).run()
        self.assertEqual(len(calls), 1)
        self.assertTrue(callable(calls[0]["stage"]))


if __name__ == "__main__":
    unittest.main()
