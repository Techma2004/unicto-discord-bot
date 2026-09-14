from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.db import SessionLocal
from app.database.models import (
    NovaConversation,
    NovaMessage,
    NovaUser,
)


class MemoryService:

    async def get_or_create_user(self, discord_user):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaUser).where(
                    NovaUser.discord_user_id
                    == discord_user.id
                )
            )

            user = result.scalar_one_or_none()

            if user:
                user.username = discord_user.name
                user.display_name = (
                    discord_user.display_name
                )

                await session.commit()

                return user.id

            user = NovaUser(
                discord_user_id=discord_user.id,
                username=discord_user.name,
                display_name=discord_user.display_name,
            )

            session.add(user)

            await session.commit()
            await session.refresh(user)

            return user.id

    async def get_or_create_conversation(
        self,
        user_id,
        channel_id,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaConversation)
                .where(
                    NovaConversation.user_id
                    == user_id,
                    NovaConversation.discord_channel_id
                    == channel_id,
                )
                .order_by(
                    NovaConversation.updated_at.desc()
                )
                .limit(1)
            )

            conversation = result.scalar_one_or_none()

            if conversation:
                return conversation.id

            conversation = NovaConversation(
                user_id=user_id,
                discord_channel_id=channel_id,
            )

            session.add(conversation)

            await session.commit()
            await session.refresh(conversation)

            return conversation.id

    async def save_message(
        self,
        conversation_id,
        role,
        content,
        model=None,
    ):
        async with SessionLocal() as session:

            message = NovaMessage(
                conversation_id=conversation_id,
                role=role,
                content=content,
                model=model,
            )

            session.add(message)

            conversation = await session.get(
                NovaConversation,
                conversation_id,
            )

            if conversation:
                from datetime import datetime

                conversation.updated_at = (
                    datetime.utcnow()
                )

            await session.commit()

    async def get_recent_messages(
        self,
        conversation_id,
        limit=12,
    ):
        async with SessionLocal() as session:

            result = await session.execute(
                select(NovaMessage)
                .where(
                    NovaMessage.conversation_id
                    == conversation_id
                )
                .order_by(
                    NovaMessage.created_at.desc()
                )
                .limit(limit)
            )

            messages = list(
                reversed(
                    result.scalars().all()
                )
            )

            return [
                {
                    "role": message.role,
                    "content": message.content,
                    "model": message.model,
                }
                for message in messages
            ]


memory = MemoryService()
