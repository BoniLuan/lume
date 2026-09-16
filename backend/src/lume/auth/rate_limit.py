from collections import defaultdict, deque
from hashlib import sha256
from threading import Lock
from time import monotonic

from lume.auth.service import normalize_email


class LoginRateLimiter:
    def __init__(self, max_failures: int, window_seconds: int) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    @staticmethod
    def key(email: str, client_ip: str) -> str:
        email_hash = sha256(normalize_email(email).encode()).hexdigest()
        return f"{client_ip}:{email_hash}"

    def retry_after(self, key: str) -> int | None:
        now = monotonic()
        with self._lock:
            failures = self._failures[key]
            while failures and now - failures[0] >= self.window_seconds:
                failures.popleft()
            if len(failures) < self.max_failures:
                return None
            return max(1, int(self.window_seconds - (now - failures[0])))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures[key].append(monotonic())

    def clear(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._failures.clear()


login_rate_limiter = LoginRateLimiter(max_failures=5, window_seconds=15 * 60)
