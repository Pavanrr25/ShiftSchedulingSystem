"""Business rules for shift-time validation and interval checks."""
from datetime import date, datetime, time, timedelta


def parse_shift_times(shift_date, start_time, end_time, overnight):
    """Validate form values and return start/end datetimes as ISO strings."""
    try:
        day = date.fromisoformat(shift_date)
        start = time.fromisoformat(start_time)
        end = time.fromisoformat(end_time)
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid date and time.")

    if overnight:
        if end >= start:
            raise ValueError("For an overnight shift, the end time must be earlier than the start time.")
        end_day = day + timedelta(days=1)
    else:
        if end <= start:
            raise ValueError("End time must be later than start time. For an overnight shift, select the overnight option.")
        end_day = day

    starts_at = datetime.combine(day, start)
    ends_at = datetime.combine(end_day, end)
    return starts_at.isoformat(sep=" ", timespec="minutes"), ends_at.isoformat(sep=" ", timespec="minutes")


def intervals_overlap(existing_start, existing_end, new_start, new_end):
    """Return True when two intervals overlap; touching endpoints are allowed."""
    return existing_start < new_end and new_start < existing_end
