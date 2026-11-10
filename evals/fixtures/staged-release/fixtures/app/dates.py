from datetime import date, datetime


def fmt_date(d):
    return d.strftime("%Y-%m-%d")


def parse(s):
    return datetime.strptime(s, "%Y-%m-%d").date()
