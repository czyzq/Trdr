from zoneinfo import ZoneInfo
from datetime import datetime

WARSAW_TZ = ZoneInfo('Europe/Warsaw')

def now_warsaw() -> datetime:
    &quot;&quot;&quot;Current time in Europe/Warsaw timezone.&quot;&quot;&quot;
    return datetime.now(WARSAW_TZ)

def strftime_warsaw(fmt: str = &quot;%H:%M:%S&quot;) -> str:
    &quot;&quot;&quot;Current Warsaw time formatted.&quot;&quot;&quot;
    return now_warsaw().strftime(fmt)