import logging
import re

_SECRET_RE = re.compile(r"(gsk_[A-Za-z0-9]{10,}|Bearer\s+[A-Za-z0-9._\-]{10,})")


class RedactSecrets(logging.Filter):
    """Masks anything that looks like an API key before it reaches a log handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()  # format first so %d / %s arguments keep their types
        redacted = _SECRET_RE.sub("[REDACTED]", message)
        if redacted != message or record.args:
            record.msg, record.args = redacted, ()
        return True


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for handler in logging.getLogger().handlers:
        handler.addFilter(RedactSecrets())
    logging.getLogger("httpx").setLevel(logging.WARNING)  # httpx logs full URLs
    logging.getLogger("chromadb").setLevel(logging.WARNING)
