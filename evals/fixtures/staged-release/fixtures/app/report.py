from datetime import date

from .dates import fmt_date


def today_line():
    return "report " + fmt_date(date.today())
