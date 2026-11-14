"""users sessions ownership

Revision ID: 83a901e20d59
Revises: 867d5d03c359
Create Date: 2026-11-15 02:54:40.691486

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "83a901e20d59"
down_revision: str | Sequence[str] | None = "867d5d03c359"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # У существующих записей нет владельца: они удаляются (решение 8 плана 0005).
    # Проверки и привязки к каналам уходят каскадом, но SQLite делает каскад только с
    # PRAGMA foreign_keys, поэтому удаляем явно.
    for table in (
        "checks",
        "monitor_notification_channels",
        "monitors",
        "notification_channels",
        "telegram_connection",
    ):
        op.execute(sa.text(f"DELETE FROM {table}"))

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_sub", sa.String(length=128), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("photo_url", sa.String(length=2048), nullable=True),
        sa.Column("blocked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("telegram_id", name=op.f("uq_users_telegram_id")),
        sa.UniqueConstraint("telegram_sub", name=op.f("uq_users_telegram_sub")),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("is_superadmin", sa.Boolean(), nullable=False),
        sa.Column("build_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sessions_token_hash")),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_expires_at"), ["expires_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_sessions_user_id"), ["user_id"], unique=False)

    with op.batch_alter_table("monitors", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch_op.create_index(batch_op.f("ix_monitors_user_id"), ["user_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_monitors_user_id_users"),
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("notification_channels", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch_op.drop_constraint(
            batch_op.f("uq_notification_channels_telegram_chat_id"), type_="unique"
        )
        batch_op.create_index(
            batch_op.f("ix_notification_channels_user_id"), ["user_id"], unique=False
        )
        batch_op.create_unique_constraint(
            batch_op.f("uq_notification_channels_user_id"), ["user_id", "telegram_chat_id"]
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_notification_channels_user_id_users"),
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("telegram_connection", schema=None) as batch_op:
        # Подключение Telegram больше не одно на сервис.
        batch_op.drop_constraint(batch_op.f("ck_telegram_connection_singleton"), type_="check")
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=False))
        batch_op.create_unique_constraint(batch_op.f("uq_telegram_connection_bot_id"), ["bot_id"])
        batch_op.create_unique_constraint(batch_op.f("uq_telegram_connection_user_id"), ["user_id"])
        batch_op.create_foreign_key(
            batch_op.f("fk_telegram_connection_user_id_users"),
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # Без Пользователей у записей нет владельца, а Подключение Telegram снова одно.
    for table in (
        "checks",
        "monitor_notification_channels",
        "monitors",
        "notification_channels",
        "telegram_connection",
    ):
        op.execute(sa.text(f"DELETE FROM {table}"))

    with op.batch_alter_table("telegram_connection", schema=None) as batch_op:
        batch_op.create_check_constraint(batch_op.f("ck_telegram_connection_singleton"), "id = 1")
        batch_op.drop_constraint(
            batch_op.f("fk_telegram_connection_user_id_users"), type_="foreignkey"
        )
        batch_op.drop_constraint(batch_op.f("uq_telegram_connection_user_id"), type_="unique")
        batch_op.drop_constraint(batch_op.f("uq_telegram_connection_bot_id"), type_="unique")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("notification_channels", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_notification_channels_user_id_users"), type_="foreignkey"
        )
        batch_op.drop_constraint(batch_op.f("uq_notification_channels_user_id"), type_="unique")
        batch_op.drop_index(batch_op.f("ix_notification_channels_user_id"))
        batch_op.create_unique_constraint(
            batch_op.f("uq_notification_channels_telegram_chat_id"), ["telegram_chat_id"]
        )
        batch_op.drop_column("user_id")

    with op.batch_alter_table("monitors", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_monitors_user_id_users"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_monitors_user_id"))
        batch_op.drop_column("user_id")

    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_user_id"))
        batch_op.drop_index(batch_op.f("ix_sessions_expires_at"))

    op.drop_table("sessions")
    op.drop_table("users")
    # ### end Alembic commands ###
