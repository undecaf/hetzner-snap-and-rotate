import io
import os
import sys

from io import StringIO
from parameterized import parameterized
from random import random
from unittest import TestCase
from unittest.mock import patch

from hetzner_snap_and_rotate.__version__ import __version__
from hetzner_snap_and_rotate.config import Config


class TestConfig(TestCase):
    builtin_default = Config.Defaults()

    configured_default = Config.Defaults(
        create_snapshot=True,
        snapshot_timeout=123,
        snapshot_name='default-name',
        shutdown_and_restart=True,
        shutdown_timeout=42,
        allow_poweroff=True,
        rotate=True,
        sliding_periods=True,
        quarter_hourly=6,
        hourly=5,
        daily=4,
        weekly=3,
        monthly=2,
        yearly=1
    )

    server2_default_override: dict = {
        'name': 'server-2',
        'create_snapshot': False,
        'snapshot_timeout': 456,
        'snapshot_name': 'other-name',
        'shutdown_and_restart': False,
        'shutdown_timeout': 99,
        'allow_poweroff': False,
        'rotate': False,
        'sliding_periods': False,
        'quarter_hourly': 1,
        'hourly': 2,
        'daily': 3,
        'weekly': 4,
        'monthly': 5,
        'yearly': 6
    }

    @staticmethod
    def read_config(file_name: str, options=None) -> Config:
        if options is None:
            options = []
        return Config.read_config([sys.argv[0], '-c', f'config/{file_name}.json'] + options)

    def assert_default(self, actual: Config.Defaults, expected: Config.Defaults = None):
        self.assertEqual(actual, expected)

    def assert_server(self, actual: Config.Server, default: Config.Defaults, default_override: dict):
        self.assertEqual(actual.name, default_override['name'])
        self.assertEqual(actual, Config.Server(**(vars(default) | default_override)))

    @parameterized.expand([
        ('missing', '[Errno 2] No such file or directory'),
        ('blank', 'Expecting value'),
        ('empty', 'No API token specified'),
        ('no-snapshot-name', 'No snapshot name specified for server [server-1]'),
    ])
    def test_read_invalid_config(self, file_name: str, expected_err: str):
        with patch('sys.stderr', new=StringIO()) as mocked_stderr:
            with self.assertRaises(SystemExit):
                TestConfig.read_config(file_name)

        expected = 'Invalid configuration: ' + expected_err
        actual = mocked_stderr.getvalue()
        self.assertTrue(actual.startswith(expected), f'\nexpected: {expected},\nactual:   {actual}')

    def test_read_regular_config(self):
        config = TestConfig.read_config('regular')
        self.assertEqual(config.api_token, '123456')
        self.assert_default(config.defaults, self.configured_default)

        srv = config.servers['server-1']
        self.assert_server(srv, self.configured_default, {'name': 'server-1'})

        srv = config.servers['server-2']
        self.assert_server(srv, self.configured_default, self.server2_default_override)

    def test_read_without_default_config(self):
        config = TestConfig.read_config('without-default')
        self.assertEqual(config.api_token, '123456')
        self.assert_default(config.defaults, None)

        srv = config.servers['server-1']
        self.assert_server(srv, self.builtin_default, {'name': 'server-1'})

        srv = config.servers['server-2']
        self.assert_server(srv, self.builtin_default, self.server2_default_override)

    def test_api_token_env(self):
        expected_api_token = str(random())
        os.environ['API_TOKEN'] = expected_api_token
        config = TestConfig.read_config('empty', ['--api-token-from', 'API_TOKEN'])
        self.assertEqual(config.api_token, expected_api_token)

    def test_api_token_input(self):
        expected_api_token = str(random())
        with patch('sys.stdin', StringIO(expected_api_token)):
            config = TestConfig.read_config('empty', ['--api-token-from', '-'])
            self.assertEqual(config.api_token, expected_api_token)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_display_version(self, mock_stdout):
        with self.assertRaises(SystemExit):
            TestConfig.read_config('regular', ['--version'])
        self.assertRegex(mock_stdout.getvalue(), f'.*{__version__}.*')
