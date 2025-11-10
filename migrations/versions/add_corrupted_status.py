"""add corrupted to version_status enum

Revision ID: add_corrupted_status
Revises: 644b55aae6e4
Create Date: 2025-11-10 06:30:00.000000

Note: Static analysis warnings about op.get_bind() and op.execute() are expected.
Alembic injects these methods dynamically at runtime.

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "add_corrupted_status"
down_revision = "644b55aae6e4"
branch_labels = None
depends_on = None


def upgrade():
    """Add 'corrupted' value to version_status enum."""
    # PostgreSQL: Add new enum value
    # SQLite: No action needed - enum is just model-level constraint
    connection = op.get_bind()  # pyright: ignore
    if connection.dialect.name == "postgresql":
        op.execute(  # pyright: ignore
            "ALTER TYPE version_status ADD VALUE IF NOT EXISTS 'corrupted'"
        )


def downgrade():
    """Remove 'corrupted' value from version_status enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type, which is complex.
    For simplicity, we leave the value in place during downgrade.
    """
    # Cannot easily remove enum values in PostgreSQL - downgrade not implemented
