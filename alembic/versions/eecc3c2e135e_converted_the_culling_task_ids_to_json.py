"""converted the culling_task_ids to JSON

Revision ID: eecc3c2e135e
Revises: b5e34e234169
Create Date: 2025-04-23 07:00:01.404407
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'eecc3c2e135e'
down_revision: Union[str, None] = 'b5e34e234169'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # drop Celery tables first (as before)
    op.drop_table('celery_taskmeta')
    op.drop_table('celery_tasksetmeta')

    # alter array to JSON with explicit USING cast
    op.alter_column(
        'culling_folders',
        'culling_task_ids',
        existing_type=postgresql.ARRAY(sa.VARCHAR()),
        type_=sa.JSON(),
        existing_nullable=True,
        postgresql_using='to_json(culling_task_ids)'
    )


def downgrade() -> None:
    # revert JSON back to VARCHAR[] using a JSONB→array cast
    op.alter_column(
        'culling_folders',
        'culling_task_ids',
        existing_type=sa.JSON(),
        type_=postgresql.ARRAY(sa.VARCHAR()),
        existing_nullable=True,
        postgresql_using=(
            "array(SELECT jsonb_array_elements_text(culling_task_ids::jsonb))"
        )
    )

    # recreate Celery tables
    op.create_table(
        'celery_tasksetmeta',
        sa.Column('id', sa.INTEGER(), primary_key=True, nullable=False),
        sa.Column('taskset_id', sa.VARCHAR(length=155), nullable=True),
        sa.Column('result', postgresql.BYTEA(), nullable=True),
        sa.Column('date_done', postgresql.TIMESTAMP(), nullable=True),
        sa.UniqueConstraint('taskset_id', name='celery_tasksetmeta_taskset_id_key')
    )
    op.create_table(
        'celery_taskmeta',
        sa.Column('id', sa.INTEGER(), primary_key=True, nullable=False),
        sa.Column('task_id', sa.VARCHAR(length=155), nullable=True),
        sa.Column('status', sa.VARCHAR(length=50), nullable=True),
        sa.Column('result', postgresql.BYTEA(), nullable=True),
        sa.Column('date_done', postgresql.TIMESTAMP(), nullable=True),
        sa.Column('traceback', sa.TEXT(), nullable=True),
        sa.Column('name', sa.VARCHAR(length=155), nullable=True),
        sa.Column('args', postgresql.BYTEA(), nullable=True),
        sa.Column('kwargs', postgresql.BYTEA(), nullable=True),
        sa.Column('worker', sa.VARCHAR(length=155), nullable=True),
        sa.Column('retries', sa.INTEGER(), nullable=True),
        sa.Column('queue', sa.VARCHAR(length=155), nullable=True),
        sa.UniqueConstraint('task_id', name='celery_taskmeta_task_id_key')
    )
