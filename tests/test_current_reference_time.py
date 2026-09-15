from __future__ import annotations

import importlib.util
import subprocess
import sys
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

    def test_omitted_timezone_uses_os_local_timezone_for_the_same_instant(self) -> None:
        instant = datetime(2026, 9, 13, 12, 48, 44, 987654, tzinfo=UTC)
        value = CLOCK.current_reference_time(now=instant)
        parsed = datetime.fromisoformat(value)
        self.assertIsNotNone(parsed.utcoffset())
        self.assertEqual(parsed, instant.replace(microsecond=0))
        self.assertEqual(parsed.utcoffset(), instant.astimezone().utcoffset())
        self.assertEqual(CLOCK.current_reference_time(None, now=instant), value)

    def test_omitted_timezone_still_rejects_naive_clock(self) -> None:
        with self.assertRaises(ValueError):
            CLOCK.current_reference_time(now=datetime(2026, 9, 13, 21, 48, 44))

    def test_cli_timezone_flag_is_optional(self) -> None:
        for argv in ([], ["--timezone", "UTC"]):
            with self.subTest(argv=argv):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPT), *argv],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                parsed = datetime.fromisoformat(completed.stdout.strip())
                self.assertIsNotNone(parsed.utcoffset())

    def test_rejects_unverified_clock_or_timezone(self) -> None:
        with self.assertRaises(ValueError):
            CLOCK.current_reference_time("Asia/Tokyo", now=datetime(2026, 9, 13, 21, 48, 44))
        with self.assertRaises(ValueError):
            CLOCK.current_reference_time("Not/A-Timezone", now=datetime.now(UTC))


if __name__ == "__main__":
    unittest.main()
