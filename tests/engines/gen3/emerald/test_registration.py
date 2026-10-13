from __future__ import annotations

import unittest

from romwiki.engines.gen3.shared.personal import parse_personal_record
from romwiki.engines.registry import GEN3_EMERALD_ENGINE, get_engine


class Gen3EmeraldRegistrationTests(unittest.TestCase):
    def test_engine_resolves_and_reuses_shared_personal_parser(self) -> None:
        engine = get_engine(GEN3_EMERALD_ENGINE)

        self.assertIs(engine.personal.parse_personal_record, parse_personal_record)
        self.assertEqual(engine.personal.PERSONAL_RECORD_COUNT, 386)
        self.assertIn("pokemon", engine.dataset_kinds)
        self.assertIn("abilities", engine.dataset_kinds)

    def test_ability_name_count_is_emerald_specific(self) -> None:
        engine = get_engine(GEN3_EMERALD_ENGINE)

        # Verified against the real Emerald ROM: same 78-entry table as
        # FireRed/LeafGreen (index 76 "CACOPHONY" has the same PokeDB
        # numbering divergence), bounded to 76 the same way.
        self.assertEqual(engine.personal.ABILITY_NAME_COUNT, 76)


if __name__ == "__main__":
    unittest.main()
