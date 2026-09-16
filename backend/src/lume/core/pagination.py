import base64
from datetime import date


def encode_transaction_cursor(effective_date: date, transaction_id: str) -> str:
    raw = f"{effective_date.isoformat()}|{transaction_id}".encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_transaction_cursor(cursor: str) -> tuple[date, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        date_value, transaction_id = raw.split("|", maxsplit=1)
        return date.fromisoformat(date_value), transaction_id
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("invalid cursor") from error
