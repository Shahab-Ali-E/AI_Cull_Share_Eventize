"""fixed association between secondary user and smart share folders

Revision ID: 20560bfce18b
Revises: 26d859caac1b
Create Date: 2025-01-29 09:59:58.784406

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20560bfce18b'
down_revision: Union[str, None] = '26d859caac1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    pass
    # ### end Alembic commands ###
