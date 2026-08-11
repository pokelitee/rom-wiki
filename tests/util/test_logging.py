from __future__ import annotations

import logging
import unittest

from romwiki.util.logging import timed_operation


class LoggingTests(unittest.TestCase):
    def test_timed_operation_reports_successful_lifecycle(self) -> None:
        logger = logging.getLogger("romwiki.test")

        with (
            self.assertLogs(logger, level="INFO") as logs,
            timed_operation(logger, "Example operation"),
        ):
            pass

        messages = "\n".join(logs.output)
        self.assertIn("Example operation started", messages)
        self.assertIn("Example operation completed in", messages)

    def test_timed_operation_reports_failure_before_reraising(self) -> None:
        logger = logging.getLogger("romwiki.test")

        with (
            self.assertLogs(logger, level="INFO") as logs,
            self.assertRaisesRegex(RuntimeError, "broken"),
            timed_operation(logger, "Example operation"),
        ):
            raise RuntimeError("broken")

        self.assertIn("Example operation failed after", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
