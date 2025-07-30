import os

from dataclass_wizard import JSONWizard
from dataclasses import dataclass, field
from datetime import datetime, timezone
from random import randint
from syslog import LOG_INFO, LOG_NOTICE
from typing import Optional

from hetzner_snap_and_rotate.api import Page, api_request, ActionWrapper
from hetzner_snap_and_rotate.config import config
from hetzner_snap_and_rotate.logger import log
from hetzner_snap_and_rotate.periods import Period
from hetzner_snap_and_rotate.servers import Server, ServerAction


@dataclass(kw_only=True)
class Protection(JSONWizard):

    delete: bool = field(default=False)


@dataclass(kw_only=True, unsafe_hash=True)
class Snapshot(JSONWizard):

    id: int
    description: str = field(compare=False)
    protection: Protection = field(compare=False)
    created: datetime = field(compare=False)
    created_from: Server = field(compare=False)
    labels: dict = field(default_factory=dict, compare=False)

    @staticmethod
    def snapshot_name(server: Server,
                      snapshot=None,
                      period: Optional[Period] = None,
                      period_number: int = 0):

        if snapshot is None:
            # Use the current timestamp and the server labels for formatting
            timestamp = datetime.now(tz=config.local_tz)
            labels = server.labels

        else:
            # Use the snapshot creation timestamp and labels for formatting
            timestamp = snapshot.created.astimezone(tz=config.local_tz)
            labels = snapshot.labels

        # Build the snapshot name by applying string.Formatter.format to the template,
        # see https://docs.python.org/3/library/string.html#format-string-syntax
        result = server.config.snapshot_name.format(
            server=server.name,
            period_type=period.config_name if period is not None else 'latest',
            period_number=period_number,
            timestamp=timestamp,
            env=os.environ,
            label=labels
        )

        return result

    def rename(self, created_from: Server, period: Period, period_number: int):

        @dataclass(kw_only=True)
        class Wrapper(JSONWizard):
            image: Snapshot

        description = Snapshot.snapshot_name(server=created_from, snapshot=self,
                                             period=period, period_number=period_number)

        if description != self.description:
            if self.protection is None or not self.protection.delete:
                log(f'Server [{self.created_from.name}]: renaming [{self.description}] to [{description}]', LOG_NOTICE)

                if not config.dry_run:
                    wrapper = api_request(
                        method='PUT',
                        return_type=Wrapper,
                        api_path=f'images/{self.id}',
                        api_token=config.api_token,
                        data={'description': description}
                    )
                    log(f'Server [{self.created_from.name}]: snapshot [{self.description}] '
                        f'has been renamed to [{wrapper.image.description}]',
                        LOG_INFO)
                    self.description = wrapper.image.description

                else:
                    self.description = description

            else:
                log(f'Server [{self.created_from.name}]: NOT renaming protected snapshot [{self.description}]', LOG_NOTICE)

    def delete(self, server: Server):
        if self.protection is None or not self.protection.delete:
            log(f'Server [{server.name}]: deleting snapshot [{self.description}]', LOG_NOTICE)
            if not config.dry_run:
                api_request(
                    method='DELETE',
                    return_type=None,
                    api_path=f'images/{self.id}',
                    api_token=config.api_token
                )
                log(f'Server [{server.name}]: snapshot [{self.description}] has been deleted', LOG_INFO)

            server.snapshots.remove(self)

        else:
            log(f'Server [{server.name}]: NOT deleting protected snapshot [{self.description}]', LOG_NOTICE)


@dataclass(kw_only=True)
class SnapshotWrapper(ActionWrapper, JSONWizard):

    image: Snapshot


# Ugly hack -- this should be a method of class servers.Server
# but this would lead to a circular depencency
def create_snapshot(server: Server, timeout: int = 300) -> Snapshot:
    description = Snapshot.snapshot_name(server=server)
    data = {
        'description': description,
        'labels': server.labels,
        'type': 'snapshot'
    }

    log(f'Server [{server.name}]: creating snapshot [{description}]', LOG_NOTICE)
    if not config.dry_run:
        wrapper = server.perform_action(ServerAction.CREATE_IMAGE, return_type=SnapshotWrapper,
                                        data=data, timeout=timeout)
        wrapper.image.created_from = server
        server.snapshots.append(wrapper.image)

        log(f'Server [{server.name}]: snapshot [{description}] has been created', LOG_INFO)
        return wrapper.image

    else:
        snapshot = Snapshot(
            id=randint(1000000, 9999999),
            description=description,
            protection=Protection(delete=False),
            created=datetime.now(tz=timezone.utc),
            created_from=server,
            labels=server.labels
        )
        server.snapshots.append(snapshot)
        return snapshot


@dataclass(kw_only=True)
class Snapshots(Page, JSONWizard):

    images: list[Snapshot]

    @staticmethod
    def load_snapshots():
        return Page.load_page(
            return_type=Snapshots,
            api_path='images',
            api_token=config.api_token,
            params={'type': 'snapshot'}
        )

    @staticmethod
    def oldest(start: datetime, end: datetime, snapshots: list[Snapshot]) -> Optional[Snapshot]:
        if start > end:
            start, end = end, start

        matching = sorted(
            filter(lambda s: start <= s.created < end, snapshots),
            key=lambda s: s.created
        )

        return matching[0] if len(matching) else None

    @staticmethod
    def latest(start: Optional[datetime], snapshots: list[Snapshot]) -> list[Snapshot]:
        predicate = (lambda s: s.created >= start) if start is not None else (lambda s: True)
        matching = sorted(
            filter(predicate, snapshots),
            key=lambda s: s.created,
            reverse=True
        )

        return matching
