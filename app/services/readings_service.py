from typing import Dict, Any, List
from app.models.readings import DailyReadings
from app.services.storage import FileStorage


class ReadingsService:
    def __init__(self, storage: FileStorage):
        self.storage = storage

    def get_latest(self) -> DailyReadings:
        data = self.storage.read_json("latest.json")
        return DailyReadings.model_validate(data)

    def get_month(self, yyyy_mm: str) -> Dict[str, Any]:
        filename = f"month-{yyyy_mm}.json"
        return self.storage.read_json(filename)

    def get_by_date(self, yyyy_mm_dd: str) -> DailyReadings:
        yyyy_mm = yyyy_mm_dd[:7]
        month = self.get_month(yyyy_mm)
        days = month.get("days", {})
        if yyyy_mm_dd not in days:
            raise KeyError(yyyy_mm_dd)
        return DailyReadings.model_validate(days[yyyy_mm_dd])

    def list_months(self) -> List[str]:
        months = []
        for p in self.storage.data_dir.glob("month-????-??.json"):
            months.append(p.stem.replace("month-", ""))
        months.sort(reverse=True)
        return months