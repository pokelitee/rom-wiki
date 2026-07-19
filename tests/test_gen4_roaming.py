from __future__ import annotations

import struct
import unittest

from romwiki.engines.gen4_dppt import parse_roaming_activation_commands


def make_script(body: bytes) -> bytes:
    return struct.pack("<iH", 2, 0xFD13) + body


class Gen4RoamingActivationTests(unittest.TestCase):
    def test_extracts_literal_roaming_slots(self) -> None:
        body = b"".join(
            (
                struct.pack("<HBHB", 0x021C, 0, 0x002C, 1),
                struct.pack("<HBH", 0x021C, 4, 0x0002),
            )
        )

        commands = parse_roaming_activation_commands(make_script(body))

        self.assertEqual(
            [(command.offset, command.slot) for command in commands],
            [(6, 0), (12, 4)],
        )

    def test_ignores_invalid_slot_or_following_opcode(self) -> None:
        body = b"".join(
            (
                struct.pack("<HBH", 0x021C, 5, 0x0002),
                struct.pack("<HBH", 0x021C, 0, 0x5F00),
            )
        )

        self.assertEqual(parse_roaming_activation_commands(make_script(body)), ())


if __name__ == "__main__":
    unittest.main()
