from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4.hgss.script_items import find_script_awarded_items
from tests.conftest import make_script


class Gen4HgssScriptItemTests(unittest.TestCase):
    def test_decodes_the_real_sprout_tower_tm70_grant_shape(self) -> None:
        # The exact real byte sequence confirmed against the live Sacred
        # Gold ROM's script archive (see gen4/hgss/script_items.py's module
        # comment): SetVar(32772, 397) [item], SetVar(32773, 1) [quantity],
        # CallStd(2033) [confirmed give-item common script].
        body = (
            struct.pack("<HHH", 0x29, 32772, 397)
            + struct.pack("<HHH", 0x29, 32773, 1)
            + struct.pack("<HH", 0x14, 2033)
            + struct.pack("<H", 0x02)
        )

        awards = find_script_awarded_items(make_script(body), item_count=500)

        self.assertEqual(len(awards), 1)
        self.assertEqual((awards[0].item_id, awards[0].quantity), (397, 1))

    def test_ignores_unconfirmed_call_std_targets(self) -> None:
        body = (
            struct.pack("<HHH", 0x29, 32772, 397)
            + struct.pack("<HHH", 0x29, 32773, 1)
            + struct.pack("<HH", 0x14, 9999)
            + struct.pack("<H", 0x02)
        )

        self.assertEqual(
            find_script_awarded_items(make_script(body), item_count=500), ()
        )

    def test_ignores_variable_supplied_item_ids(self) -> None:
        body = (
            struct.pack("<HHH", 0x29, 32772, 0x8005)
            + struct.pack("<HHH", 0x29, 32773, 1)
            + struct.pack("<HH", 0x14, 2033)
            + struct.pack("<H", 0x02)
        )

        self.assertEqual(
            find_script_awarded_items(make_script(body), item_count=500), ()
        )


if __name__ == "__main__":
    unittest.main()
