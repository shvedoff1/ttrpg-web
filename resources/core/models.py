from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Integer, String, Text, DateTime, ForeignKey, JSON, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owned_games: Mapped[list["Game"]] = relationship("Game", back_populates="owner")
    memberships: Mapped[list["GameMember"]] = relationship("GameMember", back_populates="user")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    settings: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    owner: Mapped["User"] = relationship("User", back_populates="owned_games")
    members: Mapped[list["GameMember"]] = relationship("GameMember", back_populates="game")
    engines: Mapped[list["GameEngine"]] = relationship("GameEngine", back_populates="game")
    invites: Mapped[list["GameInvite"]] = relationship("GameInvite", back_populates="game")


class GameEngine(Base):
    __tablename__ = "game_engines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    engine_id: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped["Game"] = relationship("Game", back_populates="engines")


class GameMember(Base):
    __tablename__ = "game_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="player")
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    game: Mapped["Game"] = relationship("Game", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="memberships")


class GameInvite(Base):
    __tablename__ = "game_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="player")
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    game: Mapped["Game"] = relationship("Game", back_populates="invites")
