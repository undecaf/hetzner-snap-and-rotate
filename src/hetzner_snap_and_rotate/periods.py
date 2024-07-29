from calendar import monthrange
from datetime import datetime, timedelta
from enum import Enum


class Period(Enum):

    @staticmethod
    def previous_quarter_hour(t: datetime, sliding_periods: bool):
        if sliding_periods:
            return t - timedelta(minutes=15)
        else:
            prev = t - timedelta(seconds=1)
            return prev.replace(minute=(prev.minute // 15) * 15, second=0, microsecond=0)

    @staticmethod
    def previous_hour(t: datetime, sliding_periods: bool):
        if sliding_periods:
            return t - timedelta(hours=1)
        else:
            prev = t - timedelta(seconds=1)
            return prev.replace(minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_day(t: datetime, sliding_periods: bool):
        if sliding_periods:
            return t - timedelta(days=1)
        else:
            prev = t - timedelta(seconds=1)
            return prev.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_week(t: datetime, sliding_periods: bool):
        if sliding_periods:
            return t - timedelta(weeks=1)
        else:
            prev = t - timedelta(seconds=1)
            prev = prev - timedelta(days=prev.weekday())
            return prev.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_month(t: datetime, sliding_periods: bool):
        if sliding_periods:
            year = t.year if t.month > 1 else t.year-1
            month = t.month-1 if t.month > 1 else 12
            day = min(t.day, monthrange(year, month)[1])
            return datetime(year, month, day, t.hour, t.minute, t.second, t.microsecond, t.tzinfo)
        else:
            prev = t - timedelta(seconds=1)
            return prev.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_quarter_year(t: datetime, sliding_periods: bool):
        if sliding_periods:
            year = t.year if t.month > 3 else t.year-1
            month = t.month-3 if t.month > 3 else 10
            day = min(t.day, monthrange(year, month)[1])
            return datetime(year, month, day, t.hour, t.minute, t.second, t.microsecond, t.tzinfo)
        else:
            prev = t - timedelta(seconds=1)
            return prev.replace(month=((prev.month-1) // 3) * 3 + 1, day=1, hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def previous_year(t: datetime, sliding_periods: bool):
        if sliding_periods:
            year = t.year-1
            day = t.day if (t.month != 2 and t.day != 29) else 28
            return datetime(year, t.month, day, t.hour, t.minute, t.second, t.microsecond, t.tzinfo)
        else:
            prev = t - timedelta(seconds=1)
            return prev.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    QUARTER_HOURLY = 'quarter_hourly', previous_quarter_hour
    HOURLY = 'hourly', previous_hour
    DAILY = 'daily', previous_day
    WEEKLY = 'weekly', previous_week
    MONTHLY = 'monthly', previous_month
    QUARTER_YEARLY = 'quarterly', previous_quarter_year
    YEARLY = 'yearly', previous_year

    config_name: str

    def previous_period(self, t):
        pass

    def previous_periods(self, start: datetime, count: int, sliding_periods: bool = False):
        for i in range(0, count):
            start = self.previous_period(start, sliding_periods)
            yield start

    def __new__(cls, value: str, previous_period):
        member = object.__new__(cls)
        member._value_ = value
        member.config_name = value
        member.previous_period = previous_period

        return member
