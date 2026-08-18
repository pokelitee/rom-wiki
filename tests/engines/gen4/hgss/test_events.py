from __future__ import annotations

import unittest

from romwiki.engines.gen4.hgss import (
    DYNAMIC_WARP_HEADER_ID,
    DYNAMIC_WARP_ID,
    parse_map_events,
    resolve_hidden_item_id,
)

_HEARTGOLD_EVENT_MEMBER_4 = bytes.fromhex(
    "05000000bd1f0200210000000a0000000000000004000000"
    "be1f020027000000140000000000000004000000c01f0200"
    "0e000000070000000000000004000000bf1f020017000000"
    "070000000000000004000000c11f02001100000007000000"
    "0000000004000000010000000000630100000000ca020200"
    "0200000000000000000000001e000b000000000003000000"
    "09000900d80001000000000009000a00d800010000000000"
    "250010006f0000000000000000000000"
)


class HGSSEventTests(unittest.TestCase):
    def test_decodes_real_heartgold_event_member(self) -> None:
        events = parse_map_events(_HEARTGOLD_EVENT_MEMBER_4, event_file_id=4)

        self.assertEqual((len(events.backgrounds), len(events.objects)), (5, 1))
        self.assertEqual(len(events.warps), 3)
        # script_id 8125 -> hidden-item table index 125, which real HeartGold
        # data resolves to item 86 (TinyMushroom) through `sHiddenItemParam`,
        # not the flat `script_id - 8000 = 125` a naive shortcut would give.
        item_ids = (None,) * 125 + (86,)
        self.assertEqual(
            resolve_hidden_item_id(
                events.backgrounds[0], item_count=537, item_ids=item_ids
            ),
            86,
        )
        self.assertEqual(
            (
                events.warps[0].destination_header_id,
                events.warps[0].destination_warp_id,
            ),
            (216, 1),
        )

    def test_declares_verified_dynamic_warp_sentinel(self) -> None:
        self.assertEqual((DYNAMIC_WARP_HEADER_ID, DYNAMIC_WARP_ID), (0xFFF, 0x100))


if __name__ == "__main__":
    unittest.main()
