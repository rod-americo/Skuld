from __future__ import annotations

import io
import os
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

import skuld_observability as observability


class ObservabilityTest(unittest.TestCase):
    def test_debug_is_opt_in_and_redacts_secret_fields(self) -> None:
        with patch.dict(os.environ, {"SKULD_DEBUG": "1"}), redirect_stderr(io.StringIO()) as stderr:
            observability.debug("sample", password="secret", value="visible")

        output = stderr.getvalue()
        self.assertIn("event=sample", output)
        self.assertIn("password=<redacted>", output)
        self.assertIn("value=visible", output)
        self.assertNotIn("secret", output)

    def test_debug_is_silent_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True), redirect_stderr(io.StringIO()) as stderr:
            observability.debug("sample", value="hidden")

        self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
