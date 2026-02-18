import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

from tiger_etf.config import settings

console = Console()


class JSONFileHandler(logging.FileHandler):
    def emit(self, record: logging.LogRecord) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            entry["exception"] = str(record.exc_info[1])
        record.msg = json.dumps(entry, ensure_ascii=False)
        record.args = None
        super().emit(record)


def setup_logging() -> logging.Logger:
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root = logging.getLogger("tiger_etf")
    root.setLevel(log_level)

    if root.handlers:
        return root

    # Console handler via rich
    rich_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=True,
    )
    rich_handler.setLevel(log_level)
    root.addHandler(rich_handler)

    # JSON file handler
    log_file = settings.logs_dir / f"pipeline_{datetime.now():%Y%m%d}.jsonl"
    file_handler = JSONFileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    root.addHandler(file_handler)

    return root


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"tiger_etf.{name}")
