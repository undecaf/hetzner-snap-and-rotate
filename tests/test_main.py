from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from parameterized import parameterized
from unittest import TestCase

from setuptools.command.rotate import rotate

from hetzner_snap_and_rotate.__main__ import rotate, Rotated
from hetzner_snap_and_rotate.config import Config
from hetzner_snap_and_rotate.periods import Period
from hetzner_snap_and_rotate.servers import Server
from hetzner_snap_and_rotate.snapshots import Snapshot, Protection


@dataclass(kw_only=True, unsafe_hash=True)
class SnapshotMock(Snapshot):

    period: Optional[Period] = None
    p_num: Optional[int] = None

    def __post_init__(self):
        if (self.period is not None) and (self.p_num is None):
            raise ValueError('p_num must be specified for each period')


def mocked_snapshot(created: datetime, period: Optional[Period] = None, p_num: Optional[int] = None):
    return SnapshotMock(
        id=int(created.timestamp()),
        description='',
        protection=Protection(delete=False),
        created_from=Server(id=0, name=''),
        created=created,
        period=period,
        p_num=p_num
    )


class MainTest(TestCase):

    @parameterized.expand([
        # No snapshots to rotate
        [
            Config.Defaults(),
            datetime.fromisoformat('2024-03-15T00:31:00'),
            [
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:30:00'), p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:29:00'), p_num=2),
            ]
        ],

        # A snapshot in the first quarter-hourly period
        [
            Config.Defaults(quarter_hourly=2),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            [
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:30:00'), p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:20:00')),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:15:00'), period=Period.QUARTER_HOURLY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:05:00'), period=Period.QUARTER_HOURLY, p_num=2),
            ]
        ],

        # No snapshot in the first quarter-hourly period
        [
            Config.Defaults(quarter_hourly=2, hourly=4),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            [
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:30:00'), p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:29:00')),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:20:00')),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:15:00'), period=Period.QUARTER_HOURLY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:05:00')),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:00:00'), period=Period.QUARTER_HOURLY, p_num=2),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-14T23:59:59'), period=Period.HOURLY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-14T22:00:00'), period=Period.HOURLY, p_num=2),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-14T20:00:00'), period=Period.HOURLY, p_num=4),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-14T19:00:00')),
            ]
        ],

        # No snapshot in the first hourly period
        [
            Config.Defaults(hourly=2),
            datetime.fromisoformat('2024-03-15T00:35:00'),
            [
                mocked_snapshot(created=datetime.fromisoformat('2024-03-14T23:59:59'), period=Period.HOURLY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-14T22:00:00')),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-14T20:00:00')),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-14T19:00:00')),
            ]
        ],
    ])
    def test_rotation(self, config: Config.Defaults, p_end: datetime, snapshots: list[SnapshotMock]):
        rotated = rotate(config, list(snapshots), p_end)

        for s in rotated.keys():
            s.period, s.p_num = rotated[s]

        expected_rotated: set[SnapshotMock] = set([s for s in snapshots if s.p_num is not None])
        self.assertEqual(expected_rotated, rotated.keys(), 'Snapshots not rotated as expected')


    @parameterized.expand([
        # No periods, keep all snapshots as 'latest'
        [
            Config.Defaults(),
            datetime.fromisoformat('2024-03-17T00:35:00'),
            timedelta(hours=24),
            3,
            [
                mocked_snapshot(created=datetime.fromisoformat('2024-03-19T00:35:00'), p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-18T00:35:00'), p_num=2),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-17T00:35:00'), p_num=3),
            ]
        ],

        # Single period type
        [
            Config.Defaults(daily=3),
            datetime.fromisoformat('2024-03-16T00:35:00'),
            timedelta(hours=24),
            4,
            [
                mocked_snapshot(created=datetime.fromisoformat('2024-03-19T00:35:00'), p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-18T00:35:00'), period=Period.DAILY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-17T00:35:00'), period=Period.DAILY, p_num=2),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-16T00:35:00'), period=Period.DAILY, p_num=3),
            ]
        ],

        # Multiple period types
        [
            Config.Defaults(daily=4, weekly=3),
            datetime.fromisoformat('2024-03-01T00:35:00'),
            timedelta(hours=24),
            30,
            [
                mocked_snapshot(created=datetime.fromisoformat('2024-03-30T00:35:00'), p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-29T00:35:00'), period=Period.DAILY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-28T00:35:00'), period=Period.DAILY, p_num=2),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-27T00:35:00'), period=Period.DAILY, p_num=3),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-26T00:35:00'), period=Period.DAILY, p_num=4),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-22T00:35:00'), period=Period.WEEKLY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-15T00:35:00'), period=Period.WEEKLY, p_num=2),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-08T00:35:00'), period=Period.WEEKLY, p_num=3),
            ]
        ],

        # Multiple non-contiguous period types
        [
            Config.Defaults(daily=4, monthly=2),
            datetime.fromisoformat('2024-03-01T00:35:00'),
            timedelta(hours=24),
            61,
            [
                mocked_snapshot(created=datetime.fromisoformat('2024-04-30T00:35:00'), p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-04-29T00:35:00'), period=Period.DAILY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-04-28T00:35:00'), period=Period.DAILY, p_num=2),
                mocked_snapshot(created=datetime.fromisoformat('2024-04-27T00:35:00'), period=Period.DAILY, p_num=3),
                mocked_snapshot(created=datetime.fromisoformat('2024-04-26T00:35:00'), period=Period.DAILY, p_num=4),
                mocked_snapshot(created=datetime.fromisoformat('2024-04-01T00:35:00'), period=Period.MONTHLY, p_num=1),
                mocked_snapshot(created=datetime.fromisoformat('2024-03-01T00:35:00'), period=Period.MONTHLY, p_num=2),
            ]
        ],
    ])
    def test_snapshots_with_rotations(self, config: Config.Defaults, p_end: datetime,
                                      interval: timedelta, rotations: int, expected: list[SnapshotMock]):
        snapshots: list[Snapshot] = []
        rotated: Rotated = {}

        for r in range(0, rotations):
            snapshots = list(rotated.keys()) + [mocked_snapshot(created=p_end)]

            rotated = rotate(config=config, not_rotated=snapshots, p_end=p_end)

            for s in rotated.keys():
                s.period, s.p_num = rotated[s]

            p_end = p_end + interval

        expected = sorted(expected, key=lambda s: s.created, reverse=True)
        snapshots = sorted(rotated, key=lambda s: s.created, reverse=True)

        self.assertEqual(expected, snapshots, 'Snapshots not rotated as expected')
