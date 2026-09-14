from sqlalchemy import select

from app.database.db import SessionLocal
from app.database.models import (
    NovaProject,
    NovaProjectMember,
)


class ProjectService:
    """
    Manages UNICTO projects stored in NOVA's database.
    """

    async def create_project(
        self,
        name,
        description,
        owner_discord_user_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProject).where(
                    NovaProject.name == name
                )
            )

            existing = result.scalar_one_or_none()

            if existing:
                return None, False

            project = NovaProject(
                name=name,
                description=description,
                owner_discord_user_id=owner_discord_user_id,
            )

            session.add(project)

            await session.flush()

            owner_member = NovaProjectMember(
                project_id=project.id,
                discord_user_id=owner_discord_user_id,
                role="owner",
            )

            session.add(owner_member)

            await session.commit()
            await session.refresh(project)

            return project, True

    async def get_project(self, name):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProject).where(
                    NovaProject.name == name
                )
            )

            return result.scalar_one_or_none()

    async def get_all_projects(self):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProject)
                .order_by(NovaProject.created_at.asc())
            )

            return list(result.scalars().all())

    async def delete_project(self, name):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProject).where(
                    NovaProject.name == name
                )
            )

            project = result.scalar_one_or_none()

            if not project:
                return False

            await session.delete(project)
            await session.commit()

            return True


project_service = ProjectService()
