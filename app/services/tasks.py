from sqlalchemy import select

from app.database.db import SessionLocal
from app.database.models import NovaTask


class TaskService:
    """
    Manages tasks belonging to NOVA projects.
    """

    VALID_STATUSES = {
        "todo",
        "in_progress",
        "done",
    }

    VALID_PRIORITIES = {
        "low",
        "normal",
        "high",
        "urgent",
    }

    async def create_task(
        self,
        project_id,
        title,
        description,
        created_by_discord_user_id,
        priority="normal",
    ):
        priority = priority.lower()

        if priority not in self.VALID_PRIORITIES:
            return None, False, "invalid_priority"

        async with SessionLocal() as session:

            task = NovaTask(
                project_id=project_id,
                title=title,
                description=description,
                status="todo",
                priority=priority,
                created_by_discord_user_id=(
                    created_by_discord_user_id
                ),
            )

            session.add(task)

            await session.commit()
            await session.refresh(task)

            return task, True, "created"

    async def get_task(
        self,
        project_id,
        task_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaTask).where(
                    NovaTask.id == task_id,
                    NovaTask.project_id == project_id,
                )
            )

            return result.scalar_one_or_none()

    async def get_tasks(
        self,
        project_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaTask)
                .where(
                    NovaTask.project_id == project_id
                )
                .order_by(
                    NovaTask.created_at.asc()
                )
            )

            return list(
                result.scalars().all()
            )

    async def assign_task(
        self,
        project_id,
        task_id,
        discord_user_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaTask).where(
                    NovaTask.id == task_id,
                    NovaTask.project_id == project_id,
                )
            )

            task = result.scalar_one_or_none()

            if not task:
                return None, False

            task.assigned_discord_user_id = (
                discord_user_id
            )

            await session.commit()
            await session.refresh(task)

            return task, True

    async def update_status(
        self,
        project_id,
        task_id,
        status,
    ):
        status = status.lower()

        if status not in self.VALID_STATUSES:
            return None, False, "invalid_status"

        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaTask).where(
                    NovaTask.id == task_id,
                    NovaTask.project_id == project_id,
                )
            )

            task = result.scalar_one_or_none()

            if not task:
                return None, False, "not_found"

            task.status = status

            await session.commit()
            await session.refresh(task)

            return task, True, "updated"

    async def delete_task(
        self,
        project_id,
        task_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaTask).where(
                    NovaTask.id == task_id,
                    NovaTask.project_id == project_id,
                )
            )

            task = result.scalar_one_or_none()

            if not task:
                return False

            await session.delete(task)
            await session.commit()

            return True


task_service = TaskService()
