from dataclasses import dataclass
import datetime


@dataclass
class PSIEntry:
    """Store info from a PSI elog entry"""

    id: int
    date: datetime.datetime
    attrs: dict[str, str | list]
    in_reply_to: list[int]
    replies: list[int]
    encoding: str
    attachments: list[str]
    locked_by: str
    text: str
