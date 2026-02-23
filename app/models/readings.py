from pydantic import BaseModel
from typing import Optional


class ReadingItem(BaseModel):
    reference: str
    title: Optional[str] = None
    excerpt: Optional[str] = None
    text: str


class DailyReadings(BaseModel):
    date: str  # YYYY-MM-DD
    liturgicalName: Optional[str] = None
    liturgicalTitle: Optional[str] = None
    liturgicalColor: Optional[str] = None

    gospel: ReadingItem
    firstReading: ReadingItem
    psalm: ReadingItem
    secondReading: Optional[ReadingItem] = None