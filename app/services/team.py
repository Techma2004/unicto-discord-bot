from sqlalchemy import select

from app.database.db import SessionLocal
from app.database.models import NovaUser


class TeamService:
    """
    Manages UNICTO team members stored in NOVA's database.
    """

    async def register_member(self, discord_user):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaUser).where(
                    NovaUser.discord_user_id
                    == discord_user.id
                )
            )

            member = result.scalar_one_or_none()

            if member:
                member.username = discord_user.name
                member.display_name = (
                    discord_user.display_name
                )

                await session.commit()
                await session.refresh(member)

                return member, False

            member = NovaUser(
                discord_user_id=discord_user.id,
                username=discord_user.name,
                display_name=discord_user.display_name,
            )

            session.add(member)

            await session.commit()
            await session.refresh(member)

            return member, True

    async def get_member(self, discord_user_id):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaUser).where(
                    NovaUser.discord_user_id
                    == discord_user_id
                )
            )

            return result.scalar_one_or_none()

    async def get_all_members(self):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaUser)
                .order_by(NovaUser.created_at.asc())
            )

            return list(result.scalars().all())


team_service = TeamService()
