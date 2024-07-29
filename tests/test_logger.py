import importlib
import io
import os
import re

from parameterized import parameterized
from sys import argv
from syslog import (
    LOG_EMERG, LOG_ERR, LOG_WARNING, LOG_NOTICE, LOG_INFO, LOG_DEBUG, LOG_USER, LOG_DAEMON, LOG_CRON, LOG_UPTO
)
from unittest import TestCase
from unittest.mock import patch

from hetzner_snap_and_rotate import config, logger


class TestLogger(TestCase):

    @parameterized.expand([
        (LOG_USER, LOG_EMERG),
        (LOG_USER, LOG_DEBUG),
        (LOG_DAEMON, LOG_ERR),
        (LOG_CRON, LOG_NOTICE),
    ])
    @patch('syslog.openlog')
    @patch('syslog.setlogmask')
    @patch('syslog.syslog')
    def test_syslog(self, facility, priority, mock_syslog, mock_setlogmask, mock_openlog):
        with patch('hetzner_snap_and_rotate.config.config', new=config.Config(api_token='xyz')) as mock_config:
            mock_config.facility = facility
            mock_config.priority = priority

            # Simulate initial module import
            importlib.reload(logger)

            logger.log('Test message', priority)

            # Just assert that the correct syslog calls were made
            mock_openlog.assert_called_once_with(os.path.basename(argv[0]), 0, facility)
            mock_setlogmask.assert_called_once_with(LOG_UPTO(priority))
            mock_syslog.assert_called_once_with(priority, 'Test message')

    @parameterized.expand([
        (LOG_EMERG,),
        (LOG_ERR,),
        (LOG_WARNING,),
        (LOG_NOTICE,),
        (LOG_INFO,),
        (LOG_DEBUG,),
    ])
    def test_stdout(self, priority):
        with patch('hetzner_snap_and_rotate.config.config', new=config.Config(api_token='xyz')) as mock_config:
            mock_config.facility = None
            mock_config.priority = priority

            # Simulate initial module import
            importlib.reload(logger)

            # Assert that messages with a certain priority are logged/suppressed
            for p in [LOG_ERR, LOG_WARNING, LOG_NOTICE, LOG_INFO, LOG_DEBUG]:
                with patch('sys.stdout', new=io.StringIO()) as mock_stdout:
                    logger.log('Test message', p)

                    if p <= priority:
                        self.assertRegex(mock_stdout.getvalue(), '.*Test message.*')
                    else:
                        self.assertEqual(mock_stdout.getvalue(), '')

