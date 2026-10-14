import uuid
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Postgres auto-names constraints when we don't, and Alembic autogenerate then
# emits downgrades that reference names which do not exist — discovered the
# first time a rollback is attempted, which is the worst possible moment.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for every model.

    Never instantiated — models subclass it, and SQLAlchemy reads `metadata`
    off the class. `__tablename__` is declared explicitly per model rather
    than generated: `order` is a reserved SQL word needing quoting, and
    several tables (order_item, variant_price) do not match their class name
    under any simple rule, so a generator would need exceptions anyway.
    """

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    # Fetch server-side defaults (gen_random_uuid, now()) in the same
    # statement via RETURNING, instead of a second SELECT per insert.
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012


class UUIDMixin:
    """Surrogate UUID primary key.

    UUIDs over bigserial: ids can be generated client-side before insert,
    they don't leak row counts in public URLs, and merging data across
    environments doesn't collide.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


class TimestampMixin:
    """Audit timestamps, always timezone-aware.

    `DateTime(timezone=True)` maps to timestamptz. A naive timestamp here
    silently records the server's local wall clock, which breaks the moment
    one server runs in a different zone — ruff's DTZ rules enforce the
    Python half of the same discipline.

    Defaults are server-side so a row written by a migration, a seed script,
    or psql gets the same treatment as one written by the ORM.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
