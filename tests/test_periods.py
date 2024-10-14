from datetime import datetime
from parameterized import parameterized
from unittest import TestCase

from hetzner_snap_and_rotate.periods import Period


class TestPeriod(TestCase):

    @parameterized.expand([
        [datetime.fromisoformat('2024-03-01T00:20:00'), Period.QUARTER_HOURLY, datetime.fromisoformat('2024-03-01T00:15:00')],
        [datetime.fromisoformat('2024-03-01T01:20:00'), Period.HOURLY, datetime.fromisoformat('2024-03-01T01:00:00')],
        [datetime.fromisoformat('2024-03-01T02:20:00'), Period.DAILY, datetime.fromisoformat('2024-03-01T00:00:00')],
        [datetime.fromisoformat('2024-03-01T02:20:00'), Period.WEEKLY, datetime.fromisoformat('2024-02-26T00:00:00')],
        [datetime.fromisoformat('2024-01-31T02:20:00'), Period.MONTHLY, datetime.fromisoformat('2024-01-01T00:00:00')],
        [datetime.fromisoformat('2024-01-31T02:20:00'), Period.QUARTER_YEARLY, datetime.fromisoformat('2024-01-01T00:00:00')],
        [datetime.fromisoformat('2024-02-29T02:20:00'), Period.YEARLY, datetime.fromisoformat('2024-01-01T00:00:00')],
    ])
    def test_start_of_period(self, t: datetime, period: Period, expected: datetime):
        self.assertEqual(expected, period.start_of_period(t))

    @parameterized.expand([
        [datetime.fromisoformat('2024-03-01T00:20:00'), Period.QUARTER_HOURLY, [
            datetime.fromisoformat('2024-03-01T00:05:00'),
            datetime.fromisoformat('2024-02-29T23:50:00'),
        ]],

        [datetime.fromisoformat('2024-03-01T02:20:00'), Period.HOURLY, []],

        [datetime.fromisoformat('2024-03-01T02:20:00'), Period.HOURLY, [
            datetime.fromisoformat('2024-03-01T01:20:00'),
            datetime.fromisoformat('2024-03-01T00:20:00'),
            datetime.fromisoformat('2024-02-29T23:20:00'),
        ]],

        [datetime.fromisoformat('2024-03-01T02:20:00'), Period.DAILY, [
            datetime.fromisoformat('2024-02-29T02:20:00'),
            datetime.fromisoformat('2024-02-28T02:20:00'),
            datetime.fromisoformat('2024-02-27T02:20:00'),
        ]],

        [datetime.fromisoformat('2024-03-01T02:20:00'), Period.WEEKLY, [
            datetime.fromisoformat('2024-02-23T02:20:00'),
            datetime.fromisoformat('2024-02-16T02:20:00'),
        ]],

        [datetime.fromisoformat('2024-01-31T02:20:00'), Period.MONTHLY, [
            datetime.fromisoformat('2023-12-31T02:20:00'),
            datetime.fromisoformat('2023-11-30T02:20:00'),
            datetime.fromisoformat('2023-10-30T02:20:00'),
        ]],

        [datetime.fromisoformat('2024-01-31T02:20:00'), Period.QUARTER_YEARLY, [
            datetime.fromisoformat('2023-10-31T02:20:00'),
            datetime.fromisoformat('2023-07-31T02:20:00'),
            datetime.fromisoformat('2023-04-30T02:20:00'),
            datetime.fromisoformat('2023-01-30T02:20:00'),
        ]],

        [datetime.fromisoformat('2024-02-29T02:20:00'), Period.YEARLY, [
            datetime.fromisoformat('2023-02-28T02:20:00'),
            datetime.fromisoformat('2022-02-28T02:20:00'),
        ]],
    ])
    def test_previous_periods(self, start: datetime, period: Period, periods: list[datetime]):
        expected_count = len(periods)
        actual_count = 0
        for t in period.previous_periods(start, expected_count):
            self.assertEqual(periods[actual_count], t, 'Wrong start of period')
            actual_count += 1

        self.assertEqual(actual_count, expected_count, 'Wrong count')