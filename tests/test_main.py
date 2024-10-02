from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from parameterized import parameterized
from unittest import TestCase

from hetzner_snap_and_rotate.config import Config
from hetzner_snap_and_rotate.periods import Period
from hetzner_snap_and_rotate.snapshots import Snapshot, Snapshots


@dataclass(kw_only=True, unsafe_hash=True)
class SnapshotMock:

    created: datetime
    period: Optional[Period] = None
    p_num: Optional[int] = None

    def __post_init__(self):
        if (self.period is None) != (self.p_num is None):
            raise ValueError('period and p_num must be either both specified or both omitted')


class MainTest(TestCase):

    @parameterized.expand([
        # No snapshots to rotate
        [
            Config.Defaults(),
            datetime.fromisoformat('2024-03-15T00:31:00'),
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:30:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:29:00')),
            ]
        ],

        # A snapshot in the first quarter-hourly period
        [
            Config.Defaults(quarter_hourly=2),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:30:00'), period=Period.QUARTER_HOURLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:20:00'), period=Period.QUARTER_HOURLY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:15:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:05:00')),
            ]
        ],

        # No snapshot in the first quarter-hourly period
        [
            Config.Defaults(quarter_hourly=2, hourly=2),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:29:00'), period=Period.QUARTER_HOURLY,
                             p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:20:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:15:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:05:00'), period=Period.QUARTER_HOURLY,
                             p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:00:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T23:59:59'), period=Period.HOURLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T22:00:00'), period=Period.HOURLY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T20:00:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T19:00:00')),
            ]
        ],

        # No snapshot in the first hourly period
        [
            Config.Defaults(hourly=2),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T23:59:59'), period=Period.HOURLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T22:00:00'), period=Period.HOURLY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T20:00:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T19:00:00')),
            ]
        ],
    ])
    def test_sequence_of_periods(self, config: Config.Defaults, p_end: datetime, snapshots: list[SnapshotMock]):
        not_rotated: list[Snapshot] = list(snapshots)
        rotated: dict[Snapshot, tuple[Period, int]] = {}

        for p in Period:
            p_count = getattr(config, p.config_name, 0) or 0
            p_num = 1

            if p_count > 0:
                for p_start in p.previous_periods(p_end, p_count + 1):
                    if p_num > p_count:
                        break

                    p_sn = Snapshots.most_recent(p_start, p_end, not_rotated)

                    if p_sn:
                        self.assertEqual(p, p_sn.period, f'{p_sn} not expected in period type {p}')
                        self.assertEqual(p_sn.p_num, p_num, f'{p_sn} not expected in period #{p_num} of {p}')

                        not_rotated.remove(p_sn)
                        rotated[p_sn] = (p, p_num)

                        p_end = p_start
                        p_num += 1

        expected_rotated: dict[SnapshotMock, tuple[Period, int]] = {}
        for s in snapshots:
            if s.period is not None:
                expected_rotated[s] = (s.period, s.p_num)

        self.assertEqual(expected_rotated, rotated, 'Snapshots not rotated as expected')
