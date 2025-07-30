from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from syslog import LOG_INFO
from typing import Optional

from parameterized import parameterized
from unittest import TestCase
from unittest.mock import patch

from setuptools.command.rotate import rotate

from hetzner_snap_and_rotate.__main__ import rotate, Rotated, main
from hetzner_snap_and_rotate.api import Page, ApiError
from hetzner_snap_and_rotate.config import Config
from hetzner_snap_and_rotate.periods import Period
from hetzner_snap_and_rotate.servers import Server, Servers, ServerStatus
from hetzner_snap_and_rotate.snapshots import Snapshot, Snapshots, Protection


class PowerFailure(Enum):
    NONE = 0
    POWER_ON = 1
    POWER_OFF = 2
    SHUT_DOWN = 3
    API_ERROR = 4


class CreateFailure(Enum):
    NONE = 0
    TIMEOUT = 1
    API_ERROR = 2


@dataclass(kw_only=True, unsafe_hash=True)
class ServerMock(Server):

    power_failure: PowerFailure

    def power(self, turn_on: bool):
        if self.id == 0:
            # Only the first server can fail
            if self.power_failure == PowerFailure.API_ERROR:
                raise ApiError()

            if turn_on and self.power_failure == PowerFailure.POWER_ON:
                raise TimeoutError()

            if not turn_on:
                if not self.config.allow_poweroff and self.power_failure == PowerFailure.SHUT_DOWN:
                    raise TimeoutError()

                if self.config.allow_poweroff and self.power_failure == PowerFailure.POWER_OFF:
                    raise TimeoutError()

        self.status = ServerStatus.RUNNING if turn_on else ServerStatus.OFF


def mocked_server(id: int, status: ServerStatus = ServerStatus.RUNNING,
                  shutdown_and_restart: bool = True, allow_poweroff: bool = False,
                  power_failure: PowerFailure = PowerFailure.NONE):

    server: Server = ServerMock(id=id, name=f'test-server#{id}', status=status, power_failure=power_failure)

    config: Config = Config(api_token='123456')
    config.create_snapshot = True
    config.rotate = False
    config.snapshot_timeout = 1
    config.shutdown_and_restart = shutdown_and_restart
    config.allow_poweroff = allow_poweroff
    server.config = config

    return server


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


    @parameterized.expand([
        [
            1,
            ServerStatus.RUNNING,
            True,
            False,
            PowerFailure.NONE,
            CreateFailure.NONE,
            0,
        ],
        [
            1,
            ServerStatus.RUNNING,
            True,
            False,
            PowerFailure.SHUT_DOWN,
            CreateFailure.NONE,
            1,
        ],
        [
            1,
            ServerStatus.RUNNING,
            True,
            False,
            PowerFailure.POWER_ON,
            CreateFailure.NONE,
            1,
        ],
        [
            1,
            ServerStatus.RUNNING,
            True,
            True,
            PowerFailure.SHUT_DOWN,
            CreateFailure.NONE,
            0,
        ],
        [
            1,
            ServerStatus.RUNNING,
            True,
            True,
            PowerFailure.POWER_OFF,
            CreateFailure.NONE,
            1,
        ],
        [
            1,
            ServerStatus.RUNNING,
            True,
            False,
            PowerFailure.NONE,
            CreateFailure.API_ERROR,
            1,
        ],
        [
            1,
            ServerStatus.RUNNING,
            True,
            False,
            PowerFailure.NONE,
            CreateFailure.TIMEOUT,
            1,
        ],
        [
            2,
            ServerStatus.RUNNING,
            True,
            False,
            PowerFailure.SHUT_DOWN,
            CreateFailure.NONE,
            1,
        ],
    ])
    @patch('hetzner_snap_and_rotate.snapshots.Snapshots.load_snapshots')
    @patch('hetzner_snap_and_rotate.servers.Servers.load_servers')
    @patch('hetzner_snap_and_rotate.servers.Servers.load_configured_servers')
    @patch('hetzner_snap_and_rotate.__main__.create_snapshot')
    @patch('hetzner_snap_and_rotate.__main__.log')
    # Note: @patch must come below the @parameterized.expand, and the mock objects must come last in reverse order
    def test_creating_snapshots(self,
                                server_count: int, status: ServerStatus, shutdown_and_restart: bool, allow_poweroff: bool,
                                power_failure: PowerFailure, create_failure: CreateFailure,
                                expected_return_value: int,
                                mocked_log, mocked_create_snapshot, mocked_load_configured_servers, mocked_load_servers,
                                mocked_load_snapshots):

        servers: list[Server] = [mocked_server(
            id=i,
            status=status,
            shutdown_and_restart=shutdown_and_restart,
            allow_poweroff=allow_poweroff,
            power_failure=power_failure
        ) for i in range(server_count)]

        snapshot: SnapshotMock = mocked_snapshot(created=datetime.now(tz=timezone.utc))
        meta: Page.Metadata = Page.Metadata(pagination=Page.Metadata.Pagination(page=1, next_page=None))
        snapshots_created = 0

        def load_snapshots():
            return Snapshots(images=[], meta=meta)

        def load_servers():
            return Servers(servers=servers, meta=meta)

        def load_configured_servers(snapshots: Snapshots):
            return load_servers()

        def create_snapshot(server: Server, timeout: int = 300) -> Snapshot:
            nonlocal snapshots_created

            if server.id == 0:
                # Only the first server can fail
                if create_failure == CreateFailure.TIMEOUT:
                    raise TimeoutError()

                if create_failure == CreateFailure.API_ERROR:
                    raise ApiError()

            snapshots_created += 1
            return snapshot

        def log(message: str, priority: int = LOG_INFO):
            pass


        mocked_load_snapshots.side_effect = load_snapshots
        mocked_load_servers.side_effect = load_servers
        mocked_load_configured_servers.side_effect = load_configured_servers
        mocked_create_snapshot.side_effect = create_snapshot
        mocked_log.side_effect = log

        return_value = main()

        self.assertEqual(expected_return_value, return_value,
                         f'main() return value id {return_value}, expected: {expected_return_value}')
        self.assertGreaterEqual(snapshots_created, server_count - 1,
                         f'{snapshots_created} snapshot(s) were created, expected at least: {server_count-1}')

        for srv in servers:
            expected_status = status if power_failure != PowerFailure.POWER_ON else ServerStatus.OFF
            self.assertEqual(expected_status, srv.status,
                             f'Server {srv.id} has status {srv.status}, expected: {expected_status}')
