from datetime import datetime, timezone as utc_timezone

from django.utils import timezone
from tzlocal import reload_localzone


class SystemTimezoneMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        with timezone.override(reload_localzone()):
            return self.get_response(request)


def format_timestamp(value, seconds=False):
    if not value:
        return "—"
    try:
        stamp = datetime.fromisoformat(value) if isinstance(value,str) else value
        if timezone.is_naive(stamp):
            stamp = stamp.replace(tzinfo=utc_timezone.utc)
        local = timezone.localtime(stamp)
    except (TypeError,ValueError,AttributeError):
        return "—"
    minutes = int(local.utcoffset().total_seconds() // 60)
    hours, remainder = divmod(abs(minutes),60)
    offset = f"UTC{'+' if minutes >= 0 else '-'}{hours}"
    if remainder:
        offset += f":{remainder:02d}"
    pattern = "%Y-%m-%d %H:%M:%S" if seconds else "%Y-%m-%d %H:%M"
    return f"{local.strftime(pattern)} ({offset})"
