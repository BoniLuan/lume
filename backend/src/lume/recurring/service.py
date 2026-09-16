import calendar
from datetime import date, timedelta

from lume.recurring.models import RecurringTemplate


def advance_due(template: RecurringTemplate) -> date:
    current = template.next_due_on
    interval = template.interval_count
    if template.frequency == "weekly":
        return current + timedelta(weeks=interval)
    if template.frequency == "monthly":
        month_index = current.year * 12 + current.month - 1 + interval
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        day = min(template.anchor_day, calendar.monthrange(year, month)[1])
        return date(year, month, day)
    year = current.year + interval
    day = min(template.anchor_day, calendar.monthrange(year, template.anchor_month)[1])
    return date(year, template.anchor_month, day)


def advance_template(template: RecurringTemplate) -> None:
    following = advance_due(template)
    template.next_due_on = following
    if template.end_on is not None and following > template.end_on:
        template.active = False
