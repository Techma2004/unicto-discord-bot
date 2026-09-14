from sqlalchemy import select

from app.database.db import SessionLocal
from app.database.models import (
    NovaProject,
    NovaProjectMember,
)


class ProjectMemberService:
    """
    Manages project membership and project roles.
    """

    VALID_ROLES = {
        "owner",
        "developer",
        "designer",
        "tester",
        "manager",
        "member",
    }

    async def add_member(
        self,
        project_id,
        discord_user_id,
        role="member",
    ):
        role = role.lower()

        if role not in self.VALID_ROLES:
            return None, False, "invalid_role"

        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProjectMember).where(
                    NovaProjectMember.project_id
                    == project_id,
                    NovaProjectMember.discord_user_id
                    == discord_user_id,
                )
            )

            existing = result.scalar_one_or_none()

            if existing:
                return existing, False, "already_member"

            member = NovaProjectMember(
                project_id=project_id,
                discord_user_id=discord_user_id,
                role=role,
            )

            session.add(member)

            await session.commit()
            await session.refresh(member)

            return member, True, "created"

    async def get_members(self, project_id):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProjectMember)
                .where(
                    NovaProjectMember.project_id
                    == project_id
                )
                .order_by(
                    NovaProjectMember.joined_at.asc()
                )
            )

            return list(result.scalars().all())

    async def get_member(
        self,
        project_id,
        discord_user_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProjectMember).where(
                    NovaProjectMember.project_id
                    == project_id,
                    NovaProjectMember.discord_user_id
                    == discord_user_id,
                )
            )

            return result.scalar_one_or_none()

    async def remove_member(
        self,
        project_id,
        discord_user_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProjectMember).where(
                    NovaProjectMember.project_id
                    == project_id,
                    NovaProjectMember.discord_user_id
                    == discord_user_id,
                )
            )

            member = result.scalar_one_or_none()

            if not member:
                return False

            await session.delete(member)
            await session.commit()

            return True


project_member_service = ProjectMemberService()
