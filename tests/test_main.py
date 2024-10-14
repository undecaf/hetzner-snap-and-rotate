from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from parameterized import parameterized
from unittest import TestCase

from setuptools.command.rotate import rotate

from hetzner_snap_and_rotate.__main__ import rotate, Rotated
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
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:30:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:20:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:15:00'), period=Period.QUARTER_HOURLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:05:00'), period=Period.QUARTER_HOURLY, p_num=2),
            ]
        ],

        # No snapshot in the first quarter-hourly period
        [
            Config.Defaults(quarter_hourly=2, hourly=4),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:29:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:20:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:15:00'), period=Period.QUARTER_HOURLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:05:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:00:00'), period=Period.QUARTER_HOURLY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T23:59:59'), period=Period.HOURLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T22:00:00'), period=Period.HOURLY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T20:00:00'), period=Period.HOURLY, p_num=4),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T19:00:00')),
            ]
        ],

        # No snapshot in the first hourly period
        [
            Config.Defaults(hourly=2),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T23:59:59'), period=Period.HOURLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T22:00:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T20:00:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-14T19:00:00')),
            ]
        ],
    ])
    def test_single_rotation(self, config: Config.Defaults, p_end: datetime, snapshots: list[SnapshotMock]):
        rotated = rotate(config, list(snapshots), p_end)

        for s in rotated.keys():
            s.period, s.p_num = rotated[s]

        expected_rotated: set[SnapshotMock] = set([s for s in snapshots if s.period is not None])
        self.assertEqual(expected_rotated, rotated.keys(), 'Snapshots not rotated as expected')


    @parameterized.expand([
        # Keep only the latest snapshot
        [
            Config.Defaults(),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            timedelta(hours=24),
            5,
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-19T00:35:00')),
            ]
        ],

        # Single period type
        [
            Config.Defaults(daily=3),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            timedelta(hours=24),
            5,
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-19T00:35:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-18T00:35:00'), period=Period.DAILY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-17T00:35:00'), period=Period.DAILY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-16T00:35:00'), period=Period.DAILY, p_num=3),
            ]
        ],

        # Multiple period types
        [
            Config.Defaults(daily=4, weekly=3),
            datetime.fromisoformat('2024-03-01T00:35:00'),
            timedelta(hours=24),
            30,
            [
                SnapshotMock(created=datetime.fromisoformat('2024-03-30T00:35:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-03-29T00:35:00'), period=Period.DAILY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-28T00:35:00'), period=Period.DAILY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-27T00:35:00'), period=Period.DAILY, p_num=3),
                SnapshotMock(created=datetime.fromisoformat('2024-03-26T00:35:00'), period=Period.DAILY, p_num=4),
                SnapshotMock(created=datetime.fromisoformat('2024-03-22T00:35:00'), period=Period.WEEKLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-15T00:35:00'), period=Period.WEEKLY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-03-08T00:35:00'), period=Period.WEEKLY, p_num=3),
            ]
        ],

        # Multiple non-contiguous period types
        [
            Config.Defaults(daily=4, monthly=2),
            datetime.fromisoformat('2024-03-01T00:35:00'),
            timedelta(hours=24),
            61,
            [
                SnapshotMock(created=datetime.fromisoformat('2024-04-30T00:35:00')),
                SnapshotMock(created=datetime.fromisoformat('2024-04-29T00:35:00'), period=Period.DAILY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-04-28T00:35:00'), period=Period.DAILY, p_num=2),
                SnapshotMock(created=datetime.fromisoformat('2024-04-27T00:35:00'), period=Period.DAILY, p_num=3),
                SnapshotMock(created=datetime.fromisoformat('2024-04-26T00:35:00'), period=Period.DAILY, p_num=4),
                SnapshotMock(created=datetime.fromisoformat('2024-04-01T00:35:00'), period=Period.MONTHLY, p_num=1),
                SnapshotMock(created=datetime.fromisoformat('2024-03-01T00:35:00'), period=Period.MONTHLY, p_num=2),
            ]
        ],
    ])
    def test_multiple_rotations(self, config: Config.Defaults, p_end: datetime,
                                interval: timedelta, rotations: int, expected: list[SnapshotMock]):

        snapshots: list[SnapshotMock] = []

        for r in range(0, rotations):
            rotated = rotate(config=config, not_rotated=snapshots, p_end=p_end)

            for s in rotated.keys():
                s.period, s.p_num = rotated[s]

            snapshots = list(rotated.keys()) + [SnapshotMock(created=p_end)]

            p_end = p_end + interval

        self.assertEqual(sorted(expected, key=lambda s: s.created, reverse=True),
                         sorted(snapshots, key=lambda s: s.created, reverse=True),
                         'Snapshots not rotated as expected')
