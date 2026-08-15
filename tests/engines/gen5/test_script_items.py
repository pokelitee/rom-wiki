from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen5.script_items import find_script_awarded_items


class Gen5ScriptItemTests(unittest.TestCase):
    def test_decodes_only_reachable_literal_item_awards(self) -> None:
        code = (
            struct.pack("<H3H", 0xB5, 17, 2, 0x8000)
            + struct.pack("<H3H", 0xB5, 0x8001, 1, 0x8000)
            + struct.pack("<H3H", 0xB5, 18, 0x8002, 0x8000)
            + struct.pack("<H", 0x2)
            + struct.pack("<H3H", 0xB5, 19, 1, 0x8000)
        )
        script = struct.pack("<iH", 2, 0xFD13) + code

        awards = find_script_awarded_items(script, item_count=639)

        self.assertEqual(len(awards), 1)
        self.assertEqual((awards[0].item_id, awards[0].quantity), (17, 2))
        self.assertEqual(awards[0].command_offset, 6)


if __name__ == "__main__":
    unittest.main()
