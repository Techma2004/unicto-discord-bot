from datetime import datetime
from sqlalchemy.orm import relationship

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class NovaUser(Base):
    __tablename__ = "nova_users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    discord_user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    display_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    conversations = relationship(
        "NovaConversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class NovaConversation(Base):
    __tablename__ = "nova_conversations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("nova_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    discord_channel_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    title: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship(
        "NovaUser",
        back_populates="conversations",
    )

    messages = relationship(
        "NovaMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="NovaMessage.created_at",
    )


class NovaMessage(Base):
    __tablename__ = "nova_messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey(
            "nova_conversations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    conversation = relationship(
        "NovaConversation",
        back_populates="messages",
    )


class NovaProject(Base):
    __tablename__ = "nova_projects"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    owner_discord_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    members = relationship(
        "NovaProjectMember",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    tasks = relationship(
        "NovaTask",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    notes = relationship(
        "NovaProjectNote",
        back_populates="project",
        cascade="all, delete-orphan",
    )

class NovaProjectMember(Base):
    __tablename__ = "nova_project_members"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    project_id: Mapped[int] = mapped_column(
        ForeignKey(
            "nova_projects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    discord_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        default="member",
        nullable=False,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    project = relationship(
        "NovaProject",
        back_populates="members",
    )

    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "discord_user_id",
            name="uq_nova_project_member",
        ),
    )


class NovaUsage(Base):
    __tablename__ = "nova_usage"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    discord_user_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )

    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    request_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class NovaTask(Base):
    """
    Represents a task belonging to a NOVA project.
    """

    __tablename__ = "nova_tasks"

    id = Column(Integer, primary_key=True)

    project_id = Column(
        Integer,
        ForeignKey("nova_projects.id"),
        nullable=False,
        index=True,
    )

    title = Column(
        String(255),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    status = Column(
        String(30),
        nullable=False,
        default="todo",
    )

    priority = Column(
        String(20),
        nullable=False,
        default="normal",
    )

    assigned_discord_user_id = Column(
        BigInteger,
        nullable=True,
        index=True,
    )

    created_by_discord_user_id = Column(
        BigInteger,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    project = relationship(
        "NovaProject",
        back_populates="tasks",
    )


class NovaProjectNote(Base):
    """
    Represents shared knowledge stored inside a NOVA project.
    """

    __tablename__ = "nova_project_notes"

    id = Column(Integer, primary_key=True)

    project_id = Column(
        Integer,
        ForeignKey("nova_projects.id"),
        nullable=False,
        index=True,
    )

    title = Column(
        String(255),
        nullable=False,
    )

    content = Column(
        Text,
        nullable=False,
    )

    created_by_discord_user_id = Column(
        BigInteger,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    project = relationship(
        "NovaProject",
        back_populates="notes",
    )
