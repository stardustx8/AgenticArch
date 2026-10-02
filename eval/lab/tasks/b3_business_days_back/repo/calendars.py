class BusinessCalendar:
    # Monday-Friday working week minus explicit holidays.
    def __init__(self, holidays=()):
        self._holidays = set(holidays)

    def add_holiday(self, day):
        self._holidays.add(day)

    def is_business_day(self, day):
        return day.weekday() < 5 and day not in self._holidays
