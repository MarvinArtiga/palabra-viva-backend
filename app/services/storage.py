import json
from pathlib import Path
from typing import Any


class FileStorage:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)

    def read_json(self, filename: str) -> Any:
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(str(path))
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def stat(self, filename: str):
        path = self.data_dir / filename
        if not path.exists():
            raise FileNotFoundError(str(path))
        return path.stat()

    def path(self, filename: str) -> Path:
        return self.data_dir / filename