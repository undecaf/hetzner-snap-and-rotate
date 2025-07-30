import sys

from datetime import datetime, timezone
from syslog import LOG_DEBUG, LOG_ERR
from traceback import format_exc
from typing import Dict, Tuple, Optional

from hetzner_snap_and_rotate.config import Config
from hetzner_snap_and_rotate.logger import log
from hetzner_snap_and_rotate.periods import Period
from hetzner_snap_and_rotate.servers import Servers, ServerStatus
from hetzner_snap_and_rotate.snapshots import Snapshots, create_snapshot, Snapshot


# Associates snapshots with their Period type ('latest' if the Period is None) and number
Rotated = Dict[Snapshot, Tuple[Optional[Period], int]]


def rotate(config: Config.Defaults, not_rotated: list[Snapshot], p_end: datetime) -> Rotated:
    rotated: Rotated = {}
    latest_start = None

    for p in Period:
        p_count = getattr(config, p.config_name, 0) or 0

        if p_count > 0:
            if latest_start is None:
                latest_start = p.start_of_period(p_end)
                p_end = latest_start

            for p_num, p_start in enumerate(p.previous_periods(p_end, p_count), start=1):
                p_sn = Snapshots.oldest(p_start, p_end, not_rotated)

                if p_sn:
                    not_rotated.remove(p_sn)
                    rotated[p_sn] = (p, p_num)

                    p_end = p_start

    # Assign numbers (but no period types) to the latest snapshots,
    # or to all snapshots if no rotation period was configured
    for l_num, l_sn in enumerate(Snapshots.latest(latest_start, not_rotated), start=1):
        not_rotated.remove(l_sn)
        rotated[l_sn] = (None, l_num)

    return rotated


def main() -> int:
    return_value = 0

    try:
        snapshots = Snapshots.load_snapshots()
        servers = Servers.load_configured_servers(snapshots)

        for srv in servers.servers:
            # Create a new snapshot if so configured and preserve the server operating status
            try:
                new_snapshot = None

                if srv.config.create_snapshot:
                    caught = None
                    restart = False

                    try:
                        if (srv.config.shutdown_and_restart
                                and (srv.status in [ServerStatus.STARTING, ServerStatus.RUNNING])):
                            restart = True
                            srv.power(False)

                        new_snapshot = create_snapshot(srv, srv.config.snapshot_timeout)

                    # If an exception occurred during powering down or taking the snapshot
                    # then throw it only after having restarted the server, if necessary
                    except Exception as ex:
                        caught = ex

                    if restart:
                        srv.power(True)

                    if caught:
                        raise caught

            except Exception:
                log(format_exc(limit=-1), LOG_ERR)
                return_value = 1

            # Rotate existing snapshots of this server if so configured
            try:
                if srv.config.rotate:
                    sn_len = len(srv.snapshots)
                    log(f'Server [{srv.name}]: {sn_len} snapshot{"s"[:sn_len!=1]} before rotation', LOG_DEBUG)
                    for i, sn in enumerate(srv.snapshots, start=1):
                        log(f'{i:3}. {sn.description}', LOG_DEBUG)

                    # Find out which snapshots to preserve for the configured rotation periods,
                    # and note the new rotation period they are now associated with
                    not_rotated: list[Snapshot] = list(srv.snapshots)

                    p_end = new_snapshot.created if new_snapshot is not None else datetime.now(tz=timezone.utc)
                    rotated = rotate(config=srv.config, not_rotated=not_rotated, p_end=p_end)

                    # Rename the snapshots which are now associated with a different rotation period
                    for sn, (p, p_num) in rotated.items():
                        sn.rename(created_from=srv, period=p, period_number=p_num)

                    # Delete the snapshots which are not contained in any rotation period
                    for sn in not_rotated:
                        sn.delete(srv)

                    sn_len = len(srv.snapshots)
                    log(f'Server [{srv.name}]: {sn_len} snapshot{"s"[:sn_len!=1]} after rotation', LOG_DEBUG)
                    for i, sn in enumerate(srv.snapshots, start=1):
                        log(f'{i:3}. {sn.description}', LOG_DEBUG)

            except Exception:
                log(format_exc(limit=-1), LOG_ERR)
                return_value = 1

    except Exception as ex:
        log(format_exc(limit=-1), LOG_ERR)
        return_value = 1

    return return_value


if __name__ == '__main__':
    sys.exit(main())
