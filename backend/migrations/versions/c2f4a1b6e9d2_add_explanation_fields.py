"""add explanation fields

Revision ID: c2f4a1b6e9d2
Revises: 86f8fb99a643
Create Date: 2026-04-24 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2f4a1b6e9d2"
down_revision: Union[str, None] = "86f8fb99a643"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "freight_bill_decisions",
        sa.Column("decision_explanation", sa.Text(), nullable=True),
    )
    op.add_column(
        "review_tasks",
        sa.Column("review_summary", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_tasks", "review_summary")
    op.drop_column("freight_bill_decisions", "decision_explanation")
