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
                if srv.config.create_snapshot:
                    if (srv.config.shutdown_and_restart
                            and (srv.status in [ServerStatus.STARTING, ServerStatus.RUNNING])):
                        srv.power(False)
                        restart = True
                    else:
                        restart = False

                    new_snapshot = create_snapshot(srv, srv.config.snapshot_timeout)

                    if restart:
                        srv.power(True)
                else:
                    new_snapshot = None

                if srv.config.rotate:
                    sn_len = len(srv.snapshots)
                    log(f'Server [{srv.name}]: {sn_len} snapshot{"s"[:sn_len!=1]} before rotation', LOG_DEBUG)
                    for i, sn in enumerate(srv.snapshots, start=1):
                        log(f'{i:3}. {sn.description}', LOG_DEBUG)

                    # Find out which snapshots to preserve for the configured rotation periods,
                    # and note the new rotation period they are now associated with
                    to_delete: set[Snapshot] = set(srv.snapshots)
                    to_rename: dict[Snapshot, tuple[Period, int]] = {}

                    for p in Period:
                        p_count = getattr(srv.config, p.config_name, 0) or 0
                        now = new_snapshot.created if new_snapshot is not None else datetime.now(tz=timezone.utc)
                        p_end = now

                        for p_num, p_start in enumerate(p.previous_periods(now, p_count, srv.config.sliding_periods),
                                                        start=1):
                            p_sn = Snapshots.most_recent(p_start, p_end, srv.snapshots)
                            if p_sn:
                                to_delete.discard(p_sn)
                                to_rename[p_sn] = (p, p_num)

                            p_end = p_start

                    # Rename the snapshots which are now associated with a different rotation period
                    for sn, (p, p_num) in to_rename.items():
                        sn.rename(period=p, period_number=p_num)

                    # Delete the snapshots which are not contained in any rotation period
                    for sn in to_delete:
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
