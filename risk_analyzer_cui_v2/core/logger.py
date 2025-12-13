import logging
import os
from pathlib import Path
from datetime import datetime, date

APP_LOGGER_NAME = "app"

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(exist_ok=True)


class DailyDateFileHandler(logging.FileHandler):
    """
    Create one log file per day with name:
      app_log_YYYY-MM-DD.log

    It does NOT rename files (unlike TimedRotatingFileHandler),
    so it avoids Windows rename/permission issues.
    """

    def __init__(self, log_dir: Path, prefix: str = "app_log_", encoding: str = "utf-8"):
        self.log_dir = Path(log_dir)
        self.prefix = prefix
        self.current_date: date = datetime.now().date()
        filename = self._make_filename(self.current_date)
        # delay=True => open file only on first emit
        super().__init__(filename, mode="a", encoding=encoding, delay=True)

    def _make_filename(self, d: date) -> str:
        return str(self.log_dir / f"{self.prefix}{d:%Y-%m-%d}.log")

    def _rollover_if_needed(self) -> None:
        today = datetime.now().date()
        if today != self.current_date:
            # Date changed → switch to a new file
            self.current_date = today
            new_filename = self._make_filename(today)

            # Close existing stream cleanly
            if self.stream:
                self.stream.close()
                # self.stream = None

            # Update baseFilename so FileHandler opens new file
            self.baseFilename = os.fspath(new_filename)

    def emit(self, record: logging.LogRecord) -> None:
        # Called under logging's internal lock → thread-safe
        self._rollover_if_needed()
        super().emit(record)


def setup_logging() -> None:
    """
    Configure logging once at app startup.
    """
    logger = logging.getLogger(APP_LOGGER_NAME)

    # Avoid duplicate handlers if setup_logging is called multiple times
    if getattr(logger, "_configured", False):
        return

    logger.setLevel(logging.INFO)

    # File handler: one file per day
    file_handler = DailyDateFileHandler(LOG_DIR, prefix="app_log_")
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-1s | %(filename)s:%(lineno)d | %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    # Optional: console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(file_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger._configured = True  # type: ignore[attr-defined]


# Shared global logger – just import and use
logger = logging.getLogger(APP_LOGGER_NAME)
