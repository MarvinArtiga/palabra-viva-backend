import hashlib
from pathlib import Path
from datetime import datetime, timezone


def etag_for_file(path: Path) -> str:
    data = path.read_bytes()
    h = hashlib.sha256(data).hexdigest()
    return f"\"{h}\""


def last_modified_http(stat_result) -> str:
    dt = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")