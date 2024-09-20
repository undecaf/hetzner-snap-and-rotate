import os
import sys

from argparse import ArgumentParser
from datetime import datetime, timezone
from typing import Union

from dataclass_wizard import JSONWizard
from dataclasses import dataclass, field
from syslog import (
    LOG_EMERG, LOG_ERR, LOG_WARNING, LOG_NOTICE, LOG_INFO, LOG_DEBUG, LOG_KERN, LOG_USER, LOG_MAIL,
    LOG_DAEMON, LOG_AUTH, LOG_LPR, LOG_NEWS, LOG_UUCP, LOG_CRON, LOG_SYSLOG, LOG_LOCAL0,
    LOG_LOCAL1, LOG_LOCAL2, LOG_LOCAL3, LOG_LOCAL4, LOG_LOCAL5, LOG_LOCAL6, LOG_LOCAL7
)

from hetzner_snap_and_rotate.__version__ import __version__


OptionalBool = Union[bool, None]
OptionalStr = Union[str, None]
OptionalInt = Union[int, None]


@dataclass(kw_only=True)
class Config(JSONWizard):
    @dataclass(kw_only=True)
    class Defaults:

        create_snapshot: OptionalBool = None
        snapshot_timeout: OptionalInt = None
        snapshot_name: OptionalStr = None
        shutdown_and_restart: OptionalBool = None
        shutdown_timeout: OptionalInt = None
        allow_poweroff: OptionalBool = None

        rotate: OptionalBool = None
        sliding_periods: OptionalBool = None
        quarter_hourly: OptionalInt = None
        hourly: OptionalInt = None
        daily: OptionalInt = None
        weekly: OptionalInt = None
        monthly: OptionalInt = None
        yearly: OptionalInt = None

    @dataclass(kw_only=True)
    class Server(Defaults):

        name: str = ""

        def apply_default(self, default):
            for attr in self.__dict__.keys():
                if getattr(self, attr) is None:
                    setattr(self, attr, getattr(default, attr, None))

            if self.create_snapshot and not self.snapshot_name:
                raise ValueError(f'No snapshot name specified for server [{self.name}]')

    api_token: str = field(default=None)
    defaults: Defaults = field(default=None)
    servers: dict[str, Server] = field(default_factory=lambda: {})

    dry_run: bool = field(init=False)
    facility: int = field(init=False)
    priority: int = field(init=False)

    local_tz: timezone = field(init=False, default=datetime.now(timezone.utc).astimezone().tzinfo)

    def __post_init__(self):
        for name, server in self.servers.items():
            server.name = name
            server.apply_default(self.defaults)

    @staticmethod
    def read_config(sys_argv: list[str]):
        parser = ArgumentParser(
            prog=sys.modules[__name__].__package__.replace('src.', ''),
            description='Creates and rotates snapshots of Hetzner cloud servers'
        )

        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {__version__}',
            help='display the version of this script and exit'
        )

        parser.add_argument(
            '-c',
            '--config',
            action='store',
            default='config.json',
            help='read the configuration from this file, default: ./config.json'
        )

        parser.add_argument(
            '-t',
            '--api-token-from',
            action='store',
            default='',
            help='Environment variable holding API token, '
                 'or \'-\' to read it from stdin, default: API token from config file'
        )

        facilities = {
            'KERN': LOG_KERN,
            'USER': LOG_USER,
            'MAIL': LOG_MAIL,
            'DAEMON': LOG_DAEMON,
            'AUTH': LOG_AUTH,
            'LPR': LOG_LPR,
            'NEWS': LOG_NEWS,
            'UUCP': LOG_UUCP,
            'CRON': LOG_CRON,
            'SYSLOG': LOG_SYSLOG,
            'LOCAL0': LOG_LOCAL0,
            'LOCAL1': LOG_LOCAL1,
            'LOCAL2': LOG_LOCAL2,
            'LOCAL3': LOG_LOCAL3,
            'LOCAL4': LOG_LOCAL4,
            'LOCAL5': LOG_LOCAL5,
            'LOCAL6': LOG_LOCAL6,
            'LOCAL7': LOG_LOCAL7
        }

        parser.add_argument(
            '-f',
            '--facility',
            choices=facilities.keys(),
            action='store',
            default="",
            help='send log messages to this syslog facility, default: log to stdout'
        )

        priorities = {
            'OFF': LOG_EMERG,
            'ERR': LOG_ERR,
            'WARNING': LOG_WARNING,
            'NOTICE': LOG_NOTICE,
            'INFO': LOG_INFO,
            'DEBUG': LOG_DEBUG
        }

        parser.add_argument(
            '-p',
            '--priority',
            choices=priorities.keys(),
            action='store',
            default='NOTICE',
            help='log only messages up to this syslog priority, default: NOTICE'
        )

        parser.add_argument(
            '-n',
            '--dry-run',
            action='store_true',
            default=False,
            help='perform a trial run with no changes made'
        )

        try:
            options = vars(parser.parse_args(sys_argv[1:]))

            config_file = open(options['config'], 'r')

            try:
                c = Config.from_json(config_file.read())

                if options['api_token_from'] == '-':
                    c.api_token = input()
                elif options['api_token_from']:
                    c.api_token = os.getenv(options['api_token_from'])

                if not c.api_token:
                    raise ValueError('No API token specified')

                c.dry_run = options['dry_run']
                c.priority = priorities[options['priority']]

                try:
                    c.facility = facilities[options['facility']]
                except KeyError:
                    c.facility = None

                return c
            finally:
                config_file.close()

        except Exception as ex:
            print(f'Invalid configuration: {repr(ex)}', file=sys.stderr)
            exit(1)

    def of_server(self, name: str):
        try:
            return self.servers[name]
        except KeyError:
            return None


if 'unittest' in sys.modules:
    config = Config(api_token='123456')
else:
    config: Config = Config.read_config(sys.argv)
