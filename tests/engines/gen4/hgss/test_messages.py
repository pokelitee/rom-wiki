from __future__ import annotations

import unittest

from romwiki.engines.gen4.hgss import parse_english_message_archive
from tests.engines.gen4.dppt.test_map_headers import _make_message_archive


class HgssMessageTests(unittest.TestCase):
    def test_decodes_the_shared_generation_four_message_format(self) -> None:
        data = _make_message_archive(("Overgrow", "Compoundeyes"))

        self.assertEqual(
            parse_english_message_archive(data),
            ("Overgrow", "Compoundeyes"),
        )


if __name__ == "__main__":
    unittest.main()

