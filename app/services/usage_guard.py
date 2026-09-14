from collections import defaultdict, deque
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.database.db import SessionLocal
from app.database.models import NovaUsage


class UsageGuard:
    """
    Protects NOVA from excessive per-user usage.

    Limits:
    - 5 seconds between requests
    - 3 requests within 30 seconds
    - 30 requests per day
    """

    COOLDOWN_SECONDS = 5
    BURST_LIMIT = 3
    BURST_WINDOW_SECONDS = 30
    DAILY_LIMIT = 30

    def __init__(self):
        self.recent_requests = defaultdict(deque)

    def check_cooldown(self, discord_user_id):
        now = datetime.utcnow()
        requests = self.recent_requests[discord_user_id]

        while requests and (
            now - requests[0]
        ).total_seconds() > self.BURST_WINDOW_SECONDS:
            requests.popleft()

        if requests:
            elapsed = (
                now - requests[-1]
            ).total_seconds()

            if elapsed < self.COOLDOWN_SECONDS:
                remaining = self.COOLDOWN_SECONDS - elapsed

                return False, (
                    f"Please wait **{remaining:.1f} seconds** "
                    "before asking NOVA again."
                )

        if len(requests) >= self.BURST_LIMIT:
            remaining = (
                self.BURST_WINDOW_SECONDS
                - (now - requests[0]).total_seconds()
            )

            return False, (
                "You're sending requests too quickly. "
                f"Please wait about **{remaining:.0f} seconds**."
            )

        return True, None

    async def get_daily_usage(self, discord_user_id):
        start_of_day = datetime.utcnow().replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        async with SessionLocal() as session:
            result = await session.execute(
                select(
                    func.coalesce(
                        func.sum(NovaUsage.request_count),
                        0,
                    )
                )
                .where(
                    NovaUsage.discord_user_id
                    == discord_user_id,
                    NovaUsage.created_at
                    >= start_of_day,
                )
            )

            return int(result.scalar() or 0)

    async def check(self, discord_user_id):
        allowed, message = self.check_cooldown(
            discord_user_id
        )

        if not allowed:
            return False, message

        daily_usage = await self.get_daily_usage(
            discord_user_id
        )

        if daily_usage >= self.DAILY_LIMIT:
            return False, (
                "You've reached your NOVA daily limit "
                f"of **{self.DAILY_LIMIT} requests**. "
                "Please try again tomorrow."
            )

        return True, None

    def record_request(self, discord_user_id):
        self.recent_requests[discord_user_id].append(
            datetime.utcnow()
        )

    async def record_usage(
        self,
        discord_user_id,
        model,
    ):
        async with SessionLocal() as session:
            usage = NovaUsage(
                discord_user_id=discord_user_id,
                model=model,
                request_count=1,
            )

            session.add(usage)
            await session.commit()


usage_guard = UsageGuard()
