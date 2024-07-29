from datetime import datetime
from parameterized import parameterized
from unittest import TestCase

from hetzner_snap_and_rotate.periods import Period


class TestPeriod(TestCase):

    @parameterized.expand([
        [datetime(2024, 3, 1, 0, 20), Period.QUARTER_HOURLY, [
            datetime(2024, 3, 1, 0, 15),
            datetime(2024, 3, 1, 0, 0),
            datetime(2024, 2, 29, 23, 45),
        ], False],
        [datetime(2024, 3, 1, 1, 20), Period.HOURLY, [], False],
        [datetime(2024, 3, 1, 1, 20), Period.HOURLY, [
            datetime(2024, 3, 1, 1, 0),
            datetime(2024, 3, 1, 0, 0),
            datetime(2024, 2, 29, 23, 0),
        ], False],
        [datetime(2024, 3, 1, 2, 20), Period.DAILY, [
            datetime(2024, 3, 1, 0, 0),
            datetime(2024, 2, 29, 0, 0),
            datetime(2024, 2, 28, 0, 0),
        ], False],
        [datetime(2024, 3, 1, 2, 20), Period.WEEKLY, [
            datetime(2024, 2, 26, 0, 0),
            datetime(2024, 2, 19, 0, 0),
        ], False],
        [datetime(2024, 1, 31, 2, 20), Period.MONTHLY, [
            datetime(2024, 1, 1, 0, 0),
            datetime(2023, 12, 1, 0, 0),
            datetime(2023, 11, 1, 0, 0),
        ], False],
        [datetime(2024, 1, 31, 2, 20), Period.QUARTER_YEARLY, [
            datetime(2024, 1, 1, 0, 0),
            datetime(2023, 10, 1, 0, 0),
            datetime(2023, 7, 1, 0, 0),
            datetime(2023, 4, 1, 0, 0),
            datetime(2023, 1, 1, 0, 0),
        ], False],
        [datetime(2024, 2, 29, 2, 20), Period.YEARLY, [
            datetime(2024, 1, 1, 0, 0),
            datetime(2023, 1, 1, 0, 0),
            datetime(2022, 1, 1, 0, 0),
        ], False],
        [datetime(2024, 3, 1, 0, 20), Period.QUARTER_HOURLY, [
            datetime(2024, 3, 1, 0, 5),
            datetime(2024, 2, 29, 23, 50),
        ], True],
        [datetime(2024, 3, 1, 2, 20), Period.HOURLY, [], True],
        [datetime(2024, 3, 1, 2, 20), Period.HOURLY, [
            datetime(2024, 3, 1, 1, 20),
            datetime(2024, 3, 1, 0, 20),
            datetime(2024, 2, 29, 23, 20),
        ], True],
        [datetime(2024, 3, 1, 2, 20), Period.DAILY, [
            datetime(2024, 2, 29, 2, 20),
            datetime(2024, 2, 28, 2, 20),
            datetime(2024, 2, 27, 2, 20),
        ], True],
        [datetime(2024, 3, 1, 2, 20), Period.WEEKLY, [
            datetime(2024, 2, 23, 2, 20),
            datetime(2024, 2, 16, 2, 20),
        ], True],
        [datetime(2024, 1, 31, 2, 20), Period.MONTHLY, [
            datetime(2023, 12, 31, 2, 20),
            datetime(2023, 11, 30, 2, 20),
            datetime(2023, 10, 30, 2, 20),
        ], True],
        [datetime(2024, 1, 31, 2, 20), Period.QUARTER_YEARLY, [
            datetime(2023, 10, 31, 2, 20),
            datetime(2023, 7, 31, 2, 20),
            datetime(2023, 4, 30, 2, 20),
            datetime(2023, 1, 30, 2, 20),
        ], True],
        [datetime(2024, 2, 29, 2, 20), Period.YEARLY, [
            datetime(2023, 2, 28, 2, 20),
            datetime(2022, 2, 28, 2, 20),
        ], True],
    ])
    def test_previous_periods(self, start: datetime, period: Period, periods: list[datetime], sliding_periods: bool):
        expected_count = len(periods)
        actual_count = 0
        for t in period.previous_periods(start, expected_count, sliding_periods):
            self.assertEqual(periods[actual_count], t, 'Wrong start of period')
            actual_count += 1

        self.assertEqual(actual_count, expected_count, 'Wrong count')