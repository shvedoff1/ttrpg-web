from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Integer, String, Text, DateTime, Boolean, Float, ForeignKey,
    JSON, func, CheckConstraint, UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    google_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owned_games: Mapped[list["Game"]] = relationship("Game", back_populates="owner")
    memberships: Mapped[list["GameMember"]] = relationship("GameMember", back_populates="user")
    user_engines: Mapped[list["UserEngine"]] = relationship("UserEngine", back_populates="owner")
    data_libraries: Mapped[list["DataLibrary"]] = relationship("DataLibrary", back_populates="owner")
    engine_categories: Mapped[list["EngineCategory"]] = relationship("EngineCategory", back_populates="owner")
    resource_items: Mapped[list["ResourceItem"]] = relationship(
        "ResourceItem", foreign_keys="ResourceItem.owner_id", back_populates="owner"
    )


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
    logs: Mapped[list["GameLog"]] = relationship("GameLog", back_populates="game", cascade="all, delete-orphan")


class UserEngine(Base):
    """User-created engine: either a composite (mechanics list) or a copy of a system engine.

    Two modes:
    - Composite: base_engine_id IS NULL, mechanics contains [{type, label, config}, ...]
    - Copy: base_engine_id IS NOT NULL, delegates to system engine with custom_config
    """

    __tablename__ = "user_engines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Composite mode: list of mechanics [{type, label, config}, ...]
    mechanics: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # Copy mode: which system engine this is based on (e.g. "treasure", "profession_roll")
    base_engine_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # Copy mode: user-customized config for the base engine
    custom_config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Tracks which system engine was originally copied from
    source_engine_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # List of disabled action ids (e.g. ["roll_steal", "roll_cache"])
    disabled_actions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="user_engines")


class EngineCategory(Base):
    """User-created category that groups atomic engines together."""

    __tablename__ = "engine_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped["User"] = relationship("User", back_populates="engine_categories")
    engines: Mapped[list["CategoryEngine"]] = relationship(
        "CategoryEngine", back_populates="category", cascade="all, delete-orphan",
        order_by="CategoryEngine.order"
    )


class CategoryEngine(Base):
    """Atomic engine inside a category. Each one wraps exactly one primitive or system engine."""

    __tablename__ = "category_engines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("engine_categories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # "primitive" or "system"
    engine_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # primitive_id (e.g. "weighted_roll") or system engine_id (e.g. "chest_game")
    type_id: Mapped[str] = mapped_column(String(100), nullable=False)
    config: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    category: Mapped["EngineCategory"] = relationship("EngineCategory", back_populates="engines")


class GameEngine(Base):
    __tablename__ = "game_engines"
    __table_args__ = (
        # Exactly one of engine_id / user_engine_id / engine_category_id must be set
        CheckConstraint(
            "(CASE WHEN engine_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN user_engine_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN engine_category_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_game_engines_one_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(Integer, ForeignKey("games.id"), nullable=False)
    engine_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_engine_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("user_engines.id"), nullable=True
    )
    engine_category_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("engine_categories.id"), nullable=True
    )
    order: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped["Game"] = relationship("Game", back_populates="engines")
    user_engine: Mapped[Optional["UserEngine"]] = relationship("UserEngine")
    category: Mapped[Optional["EngineCategory"]] = relationship("EngineCategory")


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


class DataLibrary(Base):
    """Named data collection (item catalogs, engine configs, generator properties).

    System libraries have owner_id=NULL and are seeded from JSON files.
    User-created libraries are owned by a user and can be public or private.
    """

    __tablename__ = "data_libraries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # item_catalog | engine_config | generator_props
    lib_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # which engine this config/catalog belongs to (nullable for generic catalogs)
    engine_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # NULL = system library (read-only)
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    # slug of the library this was copied from
    source_slug: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    owner: Mapped[Optional["User"]] = relationship("User", back_populates="data_libraries")


class ResourceItem(Base):
    """Единый ресурс (предмет, трава, руда, мотивация, часть генератора и т.д.).

    Все предметы живут в одной таблице. Группировка — через теги.
    owner_id=NULL → системный (read-only), иначе — пользовательский.
    """

    __tablename__ = "resource_items"
    __table_args__ = (
        UniqueConstraint("owner_id", "key", name="uq_resource_items_owner_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    probability: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    owner_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    source_item_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("resource_items.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    owner: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[owner_id], back_populates="resource_items"
    )
    source_item: Mapped[Optional["ResourceItem"]] = relationship(
        "ResourceItem", remote_side="ResourceItem.id"
    )


class EngineResourceBinding(Base):
    """Привязка набора ресурсов (по тегам) к атомарному движку.

    Движок загружает resource_items WHERE tags @> tag_filter,
    затем применяет item_overrides поверх базовых значений.
    """

    __tablename__ = "engine_resource_bindings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    engine_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("category_engines.id", ondelete="CASCADE"), nullable=False,
        index=True
    )
    tag_filter: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="source")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    item_overrides: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    category_weight: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    engine: Mapped["CategoryEngine"] = relationship("CategoryEngine", backref="resource_bindings")


class GameLog(Base):
    __tablename__ = "game_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    user_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default="public")
    data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    game: Mapped["Game"] = relationship("Game", back_populates="logs")
