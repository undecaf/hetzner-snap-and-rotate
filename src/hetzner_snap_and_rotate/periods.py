from calendar import monthrange
from datetime import datetime, timedelta
from enum import Enum


class Period(Enum):

    @staticmethod
    def previous_quarter_hour(t: datetime):
        return t - timedelta(minutes=15)

    @staticmethod
    def previous_hour(t: datetime):
        return t - timedelta(hours=1)

    @staticmethod
    def previous_day(t: datetime):
        return t - timedelta(days=1)

    @staticmethod
    def previous_week(t: datetime):
        return t - timedelta(weeks=1)

    @staticmethod
    def previous_month(t: datetime):
        year = t.year if t.month > 1 else t.year-1
        month = t.month-1 if t.month > 1 else 12
        day = min(t.day, monthrange(year, month)[1])
        return datetime(year, month, day, t.hour, t.minute, t.second, t.microsecond, t.tzinfo)

    @staticmethod
    def previous_quarter_year(t: datetime):
        year = t.year if t.month > 3 else t.year-1
        month = t.month-3 if t.month > 3 else 10
        day = min(t.day, monthrange(year, month)[1])
        return datetime(year, month, day, t.hour, t.minute, t.second, t.microsecond, t.tzinfo)

    @staticmethod
    def previous_year(t: datetime):
        year = t.year-1
        day = t.day if (t.month != 2 and t.day != 29) else 28
        return datetime(year, t.month, day, t.hour, t.minute, t.second, t.microsecond, t.tzinfo)

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
