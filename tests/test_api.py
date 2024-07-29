import json

from datetime import datetime, timedelta
from dataclass_wizard import JSONWizard
from dataclasses import dataclass
from parameterized import parameterized
from requests_mock import Mocker
from unittest import TestCase
from urllib.parse import urlencode

from hetzner_snap_and_rotate.api import api_request, ApiError, RecoverableError, Page, Action, ActionStatus

api_base = 'https://api.hetzner.cloud/v1/'
api_path = 'test'
api_url = api_base + api_path
api_token = '123456'


@dataclass(kw_only=True)
class MockResponse(JSONWizard):
    text: str
    number: int


class ApiTest(TestCase):

    url_params = {'key': 'value'}
    mock_response = MockResponse(text='abc', number=123)
    response_text = mock_response.to_json()
    error_json = {'error': {'message': 'Lorem ipsum...'}}

    def assert_params(self, method: str, params: dict, timeout: int, data: dict = None):
        def do_assert(request, context):
            self.assertEqual(request.method, method, 'Wrong request method')
            self.assertEqual(request.headers['Content-Type'], 'application/json', 'Wrong Content-Type header')
            self.assertEqual(request.headers['Accept'], 'application/json', 'Wrong Accept header')
            self.assertEqual(request.headers['Authorization'], 'Bearer ' + api_token, 'Wrong Authorization header')
            self.assertEqual(request.query, urlencode(params), 'Wrong query params')
            self.assertEqual(request.timeout, timeout, 'Wrong timeout')
            self.assertEqual(request.body, json.dumps(data) if data is not None else None, 'Wrong JSON data')

            return self.response_text

        return do_assert

    @parameterized.expand([
        ('GET', url_params, 42),
        ('DELETE', url_params, 42),
    ])
    @Mocker()
    def test_get_params(self, method: str, params: dict, timeout: int, mocker):
        mocker.request(
            method,
            api_url,
            text=self.assert_params(method=method, params=params, timeout=timeout)
        )

        api_request(
            MockResponse,
            method=method,
            api_path=api_path,
            api_token=api_token,
            params=params,
            data={'must_be_ignored': True},
            timeout=timeout
        )

    @parameterized.expand([
        ('POST', url_params, 42, response_text),
        ('PUT', url_params, 42, response_text),
    ])
    @Mocker()
    def test_post_params(self, method: str, params: dict, timeout: int, data: dict, mocker):
        mocker.request(
            method,
            api_url,
            text=self.assert_params(method=method, params=params, timeout=timeout, data=data)
        )

        api_request(
            MockResponse,
            method=method,
            api_path=api_path,
            api_token=api_token,
            params=params,
            data=data,
            timeout=timeout
        )

    @parameterized.expand([
        ('HEAD',),
        ('OPTIONS',),
        ('PATCH',),
    ])
    @Mocker()
    def test_unsupported_methods(self, method: str, mocker):
        mocker.request(method, api_url)
        self.assertRaises(ApiError, api_request, MockResponse, method=method, api_path=api_path, api_token=api_token)

    @Mocker()
    def test_response(self, mocker):
        mocker.get(api_url, text=self.response_text)
        response = api_request(MockResponse, api_path=api_path, api_token=api_token)
        self.assertIsInstance(response, MockResponse, 'Wrong response type')
        self.assertEqual(response, self.mock_response, 'Wrong response data')

    @Mocker()
    def test_recoverable_error(self, mocker):
        mocker.get(api_url, status_code=423, reason='Locked', json=self.error_json)
        self.assertRaises(RecoverableError, api_request, MockResponse, api_path=api_path, api_token=api_token)

    @parameterized.expand([
        (400, 'Bad Request'),
        (401, 'Unauthorized'),
        (403, 'Forbidden'),
        (404, 'Not Found'),
    ])
    @Mocker()
    def test_api_error(self, status_code: int, reason: str, mocker):
        mocker.get(api_url, status_code=status_code, reason=reason, json=self.error_json)
        self.assertRaises(ApiError, api_request, MockResponse, api_path=api_path, api_token=api_token)


@dataclass(kw_only=True)
class MockPage(Page, JSONWizard):
    test: list[MockResponse]


class PageTest(TestCase):

    @staticmethod
    def serve_pages(pages: int):
        page = 0

        def do_serve(request, context):
            nonlocal page
            page += 1

            return {
                'test': [vars(MockResponse(number=page*10, text=str(page*10)))],
                'meta': {
                    'pagination': {
                        'page': page,
                        'next_page': page+1 if page < pages else None
                    }
                }
            }

        return do_serve

    @parameterized.expand([
        (1,),
        (2,),
        (5,),
    ])
    @Mocker()
    def test_load_page(self, pages: int, mocker):
        mocker.get(api_url, json=PageTest.serve_pages(pages))
        test_page = Page.load_page(MockPage, api_path=api_path, api_token=api_token)
        self.assertIsInstance(test_page, MockPage, 'Wrong response type')
        self.assertEqual(len(test_page.test), pages, 'Wrong number of entities')
        for i, t in enumerate(test_page.test, start=1):
            self.assertIsInstance(t, MockResponse, 'Wrong entity type')
            self.assertEqual(t.number, i*10, 'Wrong entity content')


class ActionTest(TestCase):

    def setUp(self):
        self.running_action = Action(id=42, command='Test', status=ActionStatus.RUNNING, error=None)
        self.success_action = Action(id=42, command='Test', status=ActionStatus.SUCCESS, error=None)

    @staticmethod
    def wrapped_action_json(action: Action):
        return f'{{ "action": {action.to_json()} }}'

    @Mocker()
    def test_load_status(self, mocker):
        mocker.get(f'{api_base}actions/{self.running_action.id}',
                   text=ActionTest.wrapped_action_json(self.success_action))
        status = self.running_action.load_status()
        self.assertEqual(status, ActionStatus.SUCCESS, 'Wrong ActionStatus')

    def serve_success_action(self, delay: int):

        success_at = datetime.now() + timedelta(seconds=delay)

        def do_serve(request, context):
            if datetime.now() < success_at:
                return ActionTest.wrapped_action_json(self.running_action)
            else:
                return ActionTest.wrapped_action_json(self.success_action)

        return do_serve

    @Mocker()
    def test_action_completed(self, mocker):
        delay = 2
        mocker.get(f'{api_base}actions/{self.running_action.id}', text=self.serve_success_action(delay=delay))
        self.running_action.wait_until_completed(timeout=delay+1, interval=1)

    @Mocker()
    def test_action_timeout(self, mocker):
        delay = 3
        mocker.get(f'{api_base}actions/{self.running_action.id}', text=self.serve_success_action(delay=delay))
        self.assertRaises(TimeoutError, self.running_action.wait_until_completed, timeout=delay-1, interval=1)

