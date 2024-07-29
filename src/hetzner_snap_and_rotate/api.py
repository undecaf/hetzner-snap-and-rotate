import json
import requests
import time

from dataclass_wizard import JSONWizard
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Union

from hetzner_snap_and_rotate.config import config


class ApiError(Exception):
    pass


class RecoverableError(Exception):
    pass


def api_request(return_type, api_path: str, api_token: str,
                method: str = 'GET', params: dict = None, data: dict = None, timeout: int = 30):

    url = 'https://api.hetzner.cloud/v1/' + api_path
    headers = {
        'Authorization': 'Bearer ' + api_token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    if (method == 'GET') or (method == 'DELETE'):
        response = requests.request(method=method, url=url, headers=headers, params=params, timeout=timeout)

    elif (method == 'POST') or (method == 'PUT'):
        response = requests.request(method=method, url=url, headers=headers, params=params, timeout=timeout,
                                    data=json.dumps(data, default=vars) if data is not None else None)
    else:
        raise ApiError(f'Unsupported method: {method}')

    if not response.ok:
        message = (
            f'{method} from {url} failed: '
            f'{response.reason} ({response.status_code}), {response.json()["error"]["message"]}'
        )

        if response.status_code in [423]:
            raise RecoverableError(message)
        else:
            raise ApiError(message)

    return return_type.from_json(response.text) if return_type is not None else None


@dataclass(kw_only=True)
class Page(JSONWizard):

    @dataclass(kw_only=True)
    class Metadata:

        @dataclass(kw_only=True)
        class Pagination:
            page: int
            next_page: Union[int, None]

        pagination: Pagination

    meta: Metadata

    @staticmethod
    def load_page(return_type, api_path: str, api_token: str, params: dict = None):
        if params is None:
            params = {}
        page = None
        next_page = 1

        while next_page is not None:
            params['page'] = next_page
            p = api_request(return_type=return_type, api_path=api_path, api_token=api_token, params=params)
            next_page = p.meta.pagination.next_page

            if not page:
                page = p

            else:
                # For all practical purposes, `api_path` also represents the name
                # of the property that contains a list of the requested entities.
                # Accumulate all entities in the list of the result `Page`
                setattr(page, api_path, getattr(page, api_path) + getattr(p, api_path))

                # Return the metadata of the last page
                page.meta = p.meta

        return page


class ActionStatus(Enum):
    RUNNING = 'running'
    SUCCESS = 'success'
    ERROR = 'error'


@dataclass(kw_only=True)
class Action(JSONWizard):

    id: int
    command: str
    status: ActionStatus
    error: Union[dict, None]

    def load_status(self) -> ActionStatus:

        @dataclass(kw_only=True)
        class Wrapper(JSONWizard):
            action: Action

        wrapper = api_request(
            return_type=Wrapper,
            api_path=f'actions/{self.id}',
            api_token=config.api_token
        )

        return wrapper.action.status

    def wait_until_completed(self, timeout: int = 30, interval: int = 5):

        if self.status in [ActionStatus.SUCCESS, ActionStatus.ERROR]:
            return

        end = datetime.now() + timedelta(seconds=timeout)

        while self.load_status() not in [ActionStatus.SUCCESS, ActionStatus.ERROR]:
            if datetime.now() <= end:
                time.sleep(interval)
            else:
                raise TimeoutError(f'Action {self.command} timed out after {timeout}s')


@dataclass(kw_only=True)
class ActionWrapper(JSONWizard):

    action: Action
