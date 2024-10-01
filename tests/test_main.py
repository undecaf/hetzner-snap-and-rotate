from datetime import datetime

from parameterized import parameterized
from unittest import TestCase

from hetzner_snap_and_rotate.config import Config
from hetzner_snap_and_rotate.periods import Period


class MainTest(TestCase):
    
    @parameterized.expand([
        [
            datetime(2024, 3, 15, 0, 31),
            Config.Defaults(),
            []
        ],
        [
            datetime(2024, 3, 15, 0, 31),
            Config.Defaults(quarter_hourly=2, hourly=2, daily=2),
            [
                datetime(2024, 3, 15, 0, 30),
                datetime(2024, 3, 15, 0, 15),
                datetime(2024, 3, 15, 0, 0),
                datetime(2024, 3, 14, 23, 0),
                datetime(2024, 3, 14, 0, 0),
                datetime(2024, 3, 13, 0, 0),
            ]
        ],
        [
            datetime(2024, 3, 15, 0, 31),
            Config.Defaults(hourly=2, weekly=2, quarter_yearly=2),
            [
                datetime(2024, 3, 15, 0, 0),
                datetime(2024, 3, 14, 23, 0),
                datetime(2024, 3, 11, 0, 0),
                datetime(2024, 3, 4, 0, 0),
                datetime(2024, 1, 1, 0, 0),
                datetime(2023, 10, 1, 0, 0),
            ]
        ],
    ])
    def test_sequence_of_periods(self, start: datetime, config: Config.Defaults, sequence: list[datetime]):
        p_end = start
        i = 0

        for p in Period:
            p_count = getattr(config, p.config_name, 0) or 0

            for p_num, p_start in enumerate(p.previous_periods(p_end, p_count),
                                            start=1):
                self.assertTrue(i < len(sequence), 'The sequence has too many periods')
                self.assertEqual(p_start, sequence[i], 'The period starts a the wrong instant')

                p_end = p_start
                i = i + 1

        self.assertTrue(i == len(sequence), 'The sequence has too few periods')
