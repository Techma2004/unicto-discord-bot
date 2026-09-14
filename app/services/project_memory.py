from sqlalchemy import select

from app.database.db import SessionLocal
from app.database.models import NovaProjectNote


class ProjectMemoryService:
    """
    Manages shared knowledge stored inside NOVA projects.
    """

    async def create_note(
        self,
        project_id,
        title,
        content,
        created_by_discord_user_id,
    ):
        async with SessionLocal() as session:

            note = NovaProjectNote(
                project_id=project_id,
                title=title,
                content=content,
                created_by_discord_user_id=(
                    created_by_discord_user_id
                ),
            )

            session.add(note)

            await session.commit()
            await session.refresh(note)

            return note

    async def get_note(
        self,
        project_id,
        note_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProjectNote).where(
                    NovaProjectNote.id == note_id,
                    NovaProjectNote.project_id == project_id,
                )
            )

            return result.scalar_one_or_none()

    async def get_notes(
        self,
        project_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProjectNote)
                .where(
                    NovaProjectNote.project_id
                    == project_id
                )
                .order_by(
                    NovaProjectNote.created_at.asc()
                )
            )

            return list(
                result.scalars().all()
            )

    async def update_note(
        self,
        project_id,
        note_id,
        title=None,
        content=None,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProjectNote).where(
                    NovaProjectNote.id == note_id,
                    NovaProjectNote.project_id == project_id,
                )
            )

            note = result.scalar_one_or_none()

            if not note:
                return None, False

            if title is not None:
                note.title = title

            if content is not None:
                note.content = content

            await session.commit()
            await session.refresh(note)

            return note, True

    async def delete_note(
        self,
        project_id,
        note_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaProjectNote).where(
                    NovaProjectNote.id == note_id,
                    NovaProjectNote.project_id == project_id,
                )
            )

            note = result.scalar_one_or_none()

            if not note:
                return False

            await session.delete(note)
            await session.commit()

            return True


project_memory = ProjectMemoryService()
