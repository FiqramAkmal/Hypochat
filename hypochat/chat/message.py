from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class ChatMessage:
    sender: str      # "you" atau nickname
    text: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

    def formatted_time(self) -> str:
        return self.timestamp.strftime("%H:%M:%S")