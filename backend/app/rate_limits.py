"""Database-backed rolling API quotas, shared by all workers using the store."""
from dataclasses import dataclass
import hashlib
import math
import time

from .domain import AppError


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: int
    scope: str

    @property
    def headers(self):
        headers = {
            'X-RateLimit-Limit': str(self.limit),
            'X-RateLimit-Remaining': str(self.remaining),
            'X-RateLimit-Reset': str(self.reset_at),
            'X-RateLimit-Window': '3600',
            'X-RateLimit-Scope': self.scope,
        }
        if not self.allowed:
            headers['Retry-After'] = str(self.retry_after)
        return headers


class RateLimitExceeded(AppError):
    def __init__(self, decision):
        super().__init__('RATE_LIMIT',
            f'The {decision.limit} requests per hour allowance is used. '
            f'Try again in {decision.retry_after} seconds.', 429)
        self.decision = decision


class ApiRateLimiter:
    window_seconds = 3600

    def __init__(self, store, limit=400, clock=None):
        if limit < 1:
            raise ValueError('API request allowance must be positive')
        self.store = store
        self.limit = limit
        self.clock = clock or time.time

    def take(self, scope, identity):
        key = hashlib.sha256((scope + ':' + identity).encode('utf8')).hexdigest()
        self.store.put_new('_system', 'api_rate', key, {'requests': []})

        def consume(record, conn):
            # Compute time inside the transaction so concurrent callers cannot
            # race the last slot. Expired timestamps are pruned without deleting
            # any database records or user data.
            current = self.clock()
            recent = sorted(t for t in record['requests'] if t > current - self.window_seconds)
            allowed = len(recent) < self.limit
            if allowed:
                recent.append(current)
                recent.sort()
            record['requests'] = recent
            # If the configured limit was lowered, wait until enough older
            # requests expire to make a slot available under the new allowance.
            next_slot = recent[max(0, len(recent) - self.limit)] + self.window_seconds
            return RateDecision(allowed, self.limit, max(0, self.limit - len(recent)),
                math.ceil(next_slot), max(1, math.ceil(next_slot - current)), scope)

        return self.store.mutate('_system', 'api_rate', key, consume)
