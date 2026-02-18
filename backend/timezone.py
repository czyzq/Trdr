from zoneinfo import ZoneInfo
from datetime import datetime

WARSAW_TZ = ZoneInfo('Europe/Warsaw')

def now_warsaw() -> datetime:
    """Current time in Europe/Warsaw timezone."""
    return datetime.now(WARSAW_TZ)

def strftime_warsaw(fmt: str = "%H:%M:%S") -> str:
    """Current Warsaw time formatted."""
    return now_warsaw().strftime(fmt)

if __name__ == '__main__':
    print(f"Warsaw time: {now_warsaw()}")
    print(f"Formatted: {strftime_warsaw()}")
