"""marked id as uuid in folder_in_s3 table

Revision ID: 1f98f61eee7e
Revises: 08a5a965092a
Create Date: 2024-11-14 09:49:47.197713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f98f61eee7e'
down_revision: Union[str, None] = '08a5a965092a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('user_s3_folders',
    sa.Column('id', sa.UUID(), nullable=False),
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
    sa.Column('folder_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['folder_id'], ['user_s3_folders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('temporary_presigned_image_urls',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('url', sa.String(), nullable=False),
    sa.Column('validity', sa.DateTime(timezone=True), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('folder_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['folder_id'], ['user_s3_folders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_temporary_presigned_image_urls_id'), 'temporary_presigned_image_urls', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_temporary_presigned_image_urls_id'), table_name='temporary_presigned_image_urls')
    op.drop_table('temporary_presigned_image_urls')
    op.drop_table('imagesmetadata')
    op.drop_table('user_s3_folders')
    # ### end Alembic commands ###
