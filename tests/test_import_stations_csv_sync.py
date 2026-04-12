"""Keep scripts/import_stations_csv._KNOWN_STATES aligned with form_filler.STATE_VALUES."""
from __future__ import annotations

import unittest

from features.submission.form_filler import STATE_VALUES
from scripts.import_stations_csv import _KNOWN_STATES


class TestImportStationsCsvSync(unittest.TestCase):
    def test_known_states_match_state_values(self) -> None:
        self.assertEqual(
            _KNOWN_STATES,
            frozenset(STATE_VALUES.keys()),
            msg="Update _KNOWN_STATES and STATE_VALUES together when the portal changes.",
        )


if __name__ == "__main__":
    unittest.main()
