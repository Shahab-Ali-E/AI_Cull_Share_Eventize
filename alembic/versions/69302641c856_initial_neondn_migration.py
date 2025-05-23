"""Initial neondn migration

Revision ID: 69302641c856
Revises: 0a24e2682db8
Create Date: 2025-05-05 12:01:43.296637

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69302641c856'
down_revision: Union[str, None] = '0a24e2682db8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('contact_us',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('first_name', sa.String(), nullable=True),
    sa.Column('last_name', sa.String(), nullable=True),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('phone', sa.String(), nullable=True),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('contact_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contact_us_id'), 'contact_us', ['id'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('username', sa.String(), nullable=True),
    sa.Column('first_name', sa.String(), nullable=True),
    sa.Column('last_name', sa.String(), nullable=True),
    sa.Column('profile_image_url', sa.String(), nullable=False),
    sa.Column('email', sa.String(), nullable=False),
    sa.Column('email_verified', sa.Boolean(), nullable=False),
    sa.Column('phone_numbers', sa.JSON(), nullable=True),
    sa.Column('session_created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('session_last_active_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('total_culling_storage_used', sa.Float(), nullable=False),
    sa.Column('total_image_share_storage_used', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_table('culling_folders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('path_in_s3', sa.String(), nullable=False),
    sa.Column('total_size', sa.Integer(), nullable=False),
    sa.Column('culling_done', sa.Boolean(), nullable=False),
    sa.Column('culling_in_progress', sa.Boolean(), nullable=False),
    sa.Column('culling_task_ids', sa.JSON(), nullable=True),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('event_arrangment_form',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('fullName', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=100), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=False),
    sa.Column('eventType', sa.String(length=100), nullable=False),
    sa.Column('eventDescription', sa.Text(), nullable=True),
    sa.Column('eventDate', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('numberOfGuests', sa.Integer(), nullable=False),
    sa.Column('budget', sa.Float(), nullable=False),
    sa.Column('selectCountry', sa.String(length=100), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.Column('alternativeCity', sa.String(length=100), nullable=True),
    sa.Column('portfolio', sa.String(length=100), nullable=True),
    sa.Column('specialRequirements', sa.Text(), nullable=True),
    sa.Column('submittedAt', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('userId', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['userId'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('smart_share_folders',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.String(length=250), nullable=True),
    sa.Column('cover_image', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('path_in_s3', sa.String(), nullable=False),
    sa.Column('total_size', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('Published', 'Not Published', 'Pending', name='publishstatus'), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('culling_images_metadata',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('file_type', sa.String(), nullable=False),
    sa.Column('upload_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('image_download_path', sa.String(), nullable=False),
    sa.Column('image_download_validity', sa.DateTime(timezone=True), nullable=False),
    sa.Column('culling_folder_id', sa.UUID(), nullable=False),
    sa.Column('detection_status', sa.String(), nullable=False),
    sa.ForeignKeyConstraint(['culling_folder_id'], ['culling_folders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('smart_share_folders_users_association',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('smart_share_folder_id', sa.UUID(), nullable=False),
    sa.Column('accessed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['smart_share_folder_id'], ['smart_share_folders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('smart_share_images_metadata',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('file_type', sa.String(), nullable=False),
    sa.Column('upload_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('image_download_path', sa.String(), nullable=False),
    sa.Column('image_download_validity', sa.DateTime(timezone=True), nullable=False),
    sa.Column('smart_share_folder_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['smart_share_folder_id'], ['smart_share_folders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('temporary_culling_image_urls_metadata',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('file_type', sa.String(), nullable=False),
    sa.Column('image_download_path', sa.String(), nullable=False),
    sa.Column('image_download_validity', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('culling_folder_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['culling_folder_id'], ['culling_folders.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('temporary_culling_image_urls_metadata')
    op.drop_table('smart_share_images_metadata')
    op.drop_table('smart_share_folders_users_association')
    op.drop_table('culling_images_metadata')
    op.drop_table('smart_share_folders')
    op.drop_table('event_arrangment_form')
    op.drop_table('culling_folders')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_contact_us_id'), table_name='contact_us')
    op.drop_table('contact_us')
    # ### end Alembic commands ###
