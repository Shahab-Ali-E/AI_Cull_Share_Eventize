"""culling_done feild in Folder_in_s3 table marke it true when culling done

Revision ID: 369a43c3f15a
Revises: 5e4fef5969d4
Create Date: 2024-11-15 12:21:43.896899

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '369a43c3f15a'
down_revision: Union[str, None] = '5e4fef5969d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('user_s3_folders', sa.Column('culling_done', sa.Boolean(), nullable=False))
    op.drop_column('users', 'culling_done')
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('users', sa.Column('culling_done', sa.BOOLEAN(), autoincrement=False, nullable=False))
    op.drop_column('user_s3_folders', 'culling_done')
    # ### end Alembic commands ###
