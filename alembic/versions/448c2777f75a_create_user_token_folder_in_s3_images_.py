"""create User, Token, Folder_In_S3, Images_Meta_data tables

Revision ID: 448c2777f75a
Revises: 
Create Date: 2024-09-11 18:02:55.194020

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '448c2777f75a'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('email_verified', sa.Boolean(), nullable=False),
    sa.Column('picture', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('total_culling_storage_used', sa.Float(), nullable=False),
    sa.Column('total_image_share_storage_used', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_table('tokens',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('access_token', sa.String(), nullable=False),
    sa.Column('refresh_token', sa.String(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_s3_folders',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('location_in_s3', sa.String(), nullable=False),
    sa.Column('total_size', sa.Integer(), nullable=False),
    sa.Column('module', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('imagesmetadata',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('file_type', sa.String(), nullable=False),
    sa.Column('upload_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('download_path', sa.String(), nullable=False),
    sa.Column('link_validity', sa.DateTime(timezone=True), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('folder_id', sa.BigInteger(), nullable=False),
    sa.ForeignKeyConstraint(['folder_id'], ['user_s3_folders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('imagesmetadata')
    op.drop_table('user_s3_folders')
    op.drop_table('tokens')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    # ### end Alembic commands ###
