from __future__ import annotations

import unittest

from romwiki.engines.gen3.shared.pointers import resolve_gba_pointer
from romwiki.util.errors import InvalidRomError


class ResolveGbaPointerTests(unittest.TestCase):
    def test_resolves_a_valid_pointer(self) -> None:
        self.assertEqual(resolve_gba_pointer(0x0823C610), 0x23C610)

    def test_rejects_a_pointer_outside_rom_address_space(self) -> None:
        with self.assertRaises(InvalidRomError):
            resolve_gba_pointer(0x02000000)


if __name__ == "__main__":
    unittest.main()
