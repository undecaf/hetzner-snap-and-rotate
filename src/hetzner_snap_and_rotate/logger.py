import os

from sys import argv
from syslog import openlog, setlogmask, syslog, LOG_UPTO, LOG_INFO

from hetzner_snap_and_rotate.config import config


priorities = ['EMERG:  ', 'ALERT:  ', 'CRIT:   ', 'ERR:    ', 'WARNING:', 'NOTICE: ', 'INFO:   ', 'DEBUG:  ']
syslog_open: bool = False


def log(message: str, priority: int = LOG_INFO):
    if config.facility is None:
        if priority <= config.priority:
            print(f'{priorities[priority]} {message}')

    else:
        global syslog_open
        if not syslog_open:
            openlog(os.path.basename(argv[0]), 0, config.facility)
            setlogmask(LOG_UPTO(config.priority))
            syslog_open = True

        syslog(priority, message)
