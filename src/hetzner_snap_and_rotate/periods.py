from calendar import monthrange
from datetime import datetime, timedelta
from enum import Enum


class Period(Enum):

    @staticmethod
    def previous_quarter_hour(t: datetime):
        prev = t - timedelta(seconds=1)
        return prev.replace(minute=(prev.minute // 15) * 15, second=0, microsecond=0)

    @staticmethod
    def previous_hour(t: datetime):
        prev = t - timedelta(seconds=1)
        return prev.replace(minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_day(t: datetime):
        prev = t - timedelta(seconds=1)
        return prev.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_week(t: datetime):
        prev = t - timedelta(seconds=1)
        prev = prev - timedelta(days=prev.weekday())
        return prev.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_month(t: datetime):
        prev = t - timedelta(seconds=1)
        return prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_quarter_year(t: datetime):
        prev = t - timedelta(seconds=1)
        return prev.replace(month=((prev.month-1) // 3) * 3 + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_year(t: datetime):
        prev = t - timedelta(seconds=1)
        return prev.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    QUARTER_HOURLY = 'quarter_hourly', previous_quarter_hour
    HOURLY = 'hourly', previous_hour
    DAILY = 'daily', previous_day
    WEEKLY = 'weekly', previous_week
    MONTHLY = 'monthly', previous_month
    QUARTER_YEARLY = 'quarter_yearly', previous_quarter_year
    YEARLY = 'yearly', previous_year

    config_name: str

    def previous_period(self, t: datetime):
        pass

    def previous_periods(self, start: datetime, count: int):
        for i in range(0, count):
            start = self.previous_period(start)
            yield start

    def __new__(cls, value: str, previous_period):
        member = object.__new__(cls)
        member._value_ = value
        member.config_name = value
        member.previous_period = previous_period

        return member
