import time

from dataclass_wizard import JSONWizard
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from syslog import LOG_NOTICE, LOG_INFO, LOG_WARNING
from typing import Type

from hetzner_snap_and_rotate.api import api_request, ApiError, Page, ActionWrapper, RecoverableError
from hetzner_snap_and_rotate.config import Config, config as global_config
from hetzner_snap_and_rotate.logger import log


class ServerStatus(Enum):

    INITIALIZING = 'initializing'
    STARTING = 'starting'
    RUNNING = 'running'
    STOPPING = 'stopping'
    OFF = 'off'
    DELETING = 'deleting'
    REBUILDING = 'rebuilding'
    MIGRATING = 'migrating'
    UNKNOWN = 'unknown'


class ServerAction(Enum):

    POWER_ON = 'poweron'
    POWER_OFF = 'poweroff'
    SHUTDOWN = 'shutdown'
    CREATE_IMAGE = 'create_image'


@dataclass(kw_only=True)
class Server(JSONWizard):

    id: int
    name: str
    status: ServerStatus = None
    labels: dict = field(default_factory=dict)
    config: Config.Server = field(init=False)
    snapshots: list = field(default_factory=list)

    def __post_init__(self):
        self.config = global_config.of_server(self.name)

    def load_status(self) -> ServerStatus:

        @dataclass(kw_only=True)
        class Wrapper(JSONWizard):
            server: Server

        wrapper = api_request(
            return_type=Wrapper,
            api_path=f'servers/{self.id}',
            api_token=global_config.api_token
        )

        return wrapper.server.status

    def perform_action(self, action: ServerAction, return_type: Type[ActionWrapper] = ActionWrapper,
                       data: dict = None, timeout: int = 30, retry_interval: int = 5):

        end = datetime.now() + timedelta(seconds=timeout)

        while True:
            try:
                wrapper = api_request(
                    method='POST',
                    return_type=return_type,
                    api_path=f'servers/{self.id}/actions/{action.value}',
                    api_token=global_config.api_token,
                    data=data
                )
                break

            except RecoverableError as ex:
                if datetime.now() <= end:
                    time.sleep(retry_interval)
                else:
                    raise ex

        if wrapper.action.error:
            raise ApiError(f'Server [{self.name}]: {action.name} failed, details: {wrapper.action.error}')

        wrapper.action.wait_until_completed(timeout)

        return wrapper

    def power(self, turn_on: bool):
        if turn_on:
            log(f'Server [{self.name}]: powering on', LOG_NOTICE)
            if not global_config.dry_run:
                self.perform_action(ServerAction.POWER_ON)
                log(f'Server [{self.name}]: starting or running', LOG_INFO)

        else:
            try:
                log(f'Server [{self.name}]: shutting down', LOG_NOTICE)
                if not global_config.dry_run:
                    self.perform_action(ServerAction.SHUTDOWN, timeout = self.config.shutdown_timeout)
                    log(f'Server [{self.name}]: has been shut down', LOG_INFO)

            except TimeoutError:
                log(f'Server [{self.name}]: unable to shut down, powering off', LOG_WARNING)
                if not global_config.dry_run:
                    self.perform_action(ServerAction.POWER_OFF, timeout = self.config.shutdown_timeout)
                    log(f'Server [{self.name}]: has been powered off', LOG_INFO)


@dataclass(kw_only=True)
class Servers(Page, JSONWizard):

    servers: list[Server]

    @staticmethod
    def load_servers():
        servers: Servers = Page.load_page(
            return_type=Servers,
            api_path='servers',
            api_token=global_config.api_token
        )

        return servers

    @staticmethod
    def load_configured_servers(snapshots):
        servers: Servers = Servers.load_servers()
        servers_by_id: dict[int, Server] = {}

        for i in range(len(servers.servers)-1, -1, -1):
            srv = servers.servers[i]
            cfg: Config.Server = global_config.of_server(srv.name)

            if cfg:
                srv.config = cfg
                srv.snapshots = []
                servers_by_id[srv.id] = srv
            else:
                servers.servers.pop(i)

        for sn in snapshots.images:
            if sn.created_from.id in servers_by_id:
                servers_by_id[sn.created_from.id].snapshots.append(sn)

        return servers
