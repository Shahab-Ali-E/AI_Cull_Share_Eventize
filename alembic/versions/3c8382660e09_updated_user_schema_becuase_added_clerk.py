"""updated user schema becuase added clerk

Revision ID: 3c8382660e09
Revises: 0e9a12e82498
Create Date: 2024-12-03 20:36:08.479195

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3c8382660e09'
down_revision: Union[str, None] = '0e9a12e82498'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('tokens')
    op.add_column('users', sa.Column('user_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('first_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(), nullable=True))
    op.add_column('users', sa.Column('profile_image_url', sa.String(), nullable=False))
    op.add_column('users', sa.Column('phone', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('session_created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('users', sa.Column('session_last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.drop_column('users', 'picture')
    op.drop_column('users', 'created_at')
    op.drop_column('users', 'name')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('name', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.add_column('users', sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False))
    op.add_column('users', sa.Column('picture', sa.VARCHAR(), autoincrement=False, nullable=False))
    op.drop_column('users', 'session_last_active_at')
    op.drop_column('users', 'session_created_at')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'profile_image_url')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'user_name')
    op.create_table('tokens',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('access_token', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('refresh_token', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=False),
    sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), autoincrement=False, nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.Column('user_id', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='tokens_user_id_fkey', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='tokens_pkey')
    )
    # ### end Alembic commands ###
