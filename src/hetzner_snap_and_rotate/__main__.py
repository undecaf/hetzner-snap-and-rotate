import sys

from datetime import datetime, timezone
from syslog import LOG_DEBUG, LOG_ERR

from hetzner_snap_and_rotate.logger import log
from hetzner_snap_and_rotate.periods import Period
from hetzner_snap_and_rotate.servers import Servers, ServerStatus
from hetzner_snap_and_rotate.snapshots import Snapshots, create_snapshot, Snapshot


def main() -> int:
    try:
        snapshots = Snapshots.load_snapshots()
        servers = Servers.load_configured_servers(snapshots)

        for srv in servers.servers:
            try:
                # Create a new snapshot if so configured and preserve the server operating status
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

                    # If an exception occurred during powering down or snapshotting
                    # then throw it only after having restarted the server, if necessary
                    except Exception as ex:
                        caught = ex

                    if restart:
                        srv.power(True)

                    if caught:
                        raise caught

                # Rotate existing snapshots of this server if so configured
                if srv.config.rotate:
                    sn_len = len(srv.snapshots)
                    log(f'Server [{srv.name}]: {sn_len} snapshot{"s"[:sn_len!=1]} before rotation', LOG_DEBUG)
                    for i, sn in enumerate(srv.snapshots, start=1):
                        log(f'{i:3}. {sn.description}', LOG_DEBUG)

                    # Find out which snapshots to preserve for the configured rotation periods,
                    # and note the new rotation period they are now associated with
                    not_rotated: list[Snapshot] = list(srv.snapshots)
                    rotated: dict[Snapshot, tuple[Period, int]] = {}

                    # Always keep the snapshot that has just been created
                    not_rotated.remove(new_snapshot)

                    p_end = new_snapshot.created if new_snapshot is not None else datetime.now(tz=timezone.utc)

                    for p in Period:
                        p_count = getattr(srv.config, p.config_name, 0) or 0
                        p_num = 1

                        if p_count > 0:
                            # Depending on the snapshot instant, the first rotation period
                            # may never contain a snapshot, so allow for an extra period
                            for p_start in p.previous_periods(p_end, p_count + 1):
                                if p_num > p_count:
                                    break

                                p_sn = Snapshots.most_recent(p_start, p_end, not_rotated)

                                if p_sn:
                                    not_rotated.remove(p_sn)
                                    rotated[p_sn] = (p, p_num)

                                    p_end = p_start
                                    p_num += 1

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

            except Exception as ex:
                log(repr(ex), LOG_ERR)

    except Exception as ex:
        log(repr(ex), LOG_ERR)

    return 0


if __name__ == '__main__':
    sys.exit(main())
