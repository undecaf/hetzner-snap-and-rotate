from dataclass_wizard import JSONWizard
from dataclasses import dataclass, field
from datetime import datetime, timezone
from random import randint
from syslog import LOG_INFO, LOG_NOTICE
from typing import Union

from hetzner_snap_and_rotate.api import Page, api_request, ActionWrapper
from hetzner_snap_and_rotate.config import config
from hetzner_snap_and_rotate.logger import log
from hetzner_snap_and_rotate.periods import Period
from hetzner_snap_and_rotate.servers import Server, ServerAction


@dataclass(kw_only=True, unsafe_hash=True)
class Snapshot(JSONWizard):

    id: int
    description: str = field(compare=False)
    created: datetime = field(compare=False)
    created_from: Server = field(compare=False)

    def rename(self, period: Period, period_number: int):

        @dataclass(kw_only=True)
        class Wrapper(JSONWizard):
            image: Snapshot

        description = self.created_from.snapshot_name(timestamp=self.created,
                                                      period=period, period_number=period_number)
        if description != self.description:
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

    def delete(self, server: Server):
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


@dataclass(kw_only=True)
class SnapshotWrapper(ActionWrapper, JSONWizard):

    image: Snapshot


# Ugly hack -- this should be a method of class servers.Sever
# but this would lead to a circular depencency
def create_snapshot(server: Server, timeout: int = 300) -> Snapshot:
    description = server.snapshot_name()
    data = {
        'description': description,
        'type': 'snapshot'
    }

    log(f'Server [{server.name}]: creating snapshot [{description}]', LOG_NOTICE)
    if not config.dry_run:
        wrapper = server.perform_action(ServerAction.CREATE_IMAGE, return_type=SnapshotWrapper,
                                        data=data, timeout=timeout)
        server.snapshots.append(wrapper.image)
        log(f'Server [{server.name}]: snapshot [{description}] has been created', LOG_INFO)
        return wrapper.image

    else:
        snapshot = Snapshot(
            id=randint(1000000, 9999999),
            description=description,
            created=datetime.now(tz=timezone.utc),
            created_from=server
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
    def most_recent(start: datetime, end: datetime, snapshots: list[Snapshot]) -> Union[Snapshot, None]:
        if start > end:
            start, end = end, start

        matching = sorted(
            filter(lambda s: start < s.created <= end, snapshots),
            key=lambda s: s.created,
            reverse=True
        )

        return matching[0] if len(matching) else None
