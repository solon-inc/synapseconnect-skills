from __future__ import annotations

import importlib.util
import unittest
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/sc-skills/scripts/current_reference_time.py"


def load_module():
    spec = importlib.util.spec_from_file_location("current_reference_time", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CLOCK = load_module()


class CurrentReferenceTimeTest(unittest.TestCase):
    def test_converts_one_aware_host_instant_to_configured_timezone(self) -> None:
        instant = datetime(2026, 9, 13, 12, 48, 44, 987654, tzinfo=UTC)
        self.assertEqual(
            CLOCK.current_reference_time("Asia/Tokyo", now=instant),
            "2026-09-13T21:48:44+09:00",
        )

    def test_rejects_unverified_clock_or_timezone(self) -> None:
        with self.assertRaises(ValueError):
            CLOCK.current_reference_time("Asia/Tokyo", now=datetime(2026, 9, 13, 21, 48, 44))
        with self.assertRaises(ValueError):
            CLOCK.current_reference_time("Not/A-Timezone", now=datetime.now(UTC))


if __name__ == "__main__":
    unittest.main()
