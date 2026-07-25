from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Event:
    type: str
    at: datetime
    note: Optional[str] = None