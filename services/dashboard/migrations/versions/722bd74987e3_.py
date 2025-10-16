"""empty message

Revision ID: 722bd74987e3
Revises: 003_ai_models, 8c79001578c0
Create Date: 2025-10-16 14:07:57.756619

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '722bd74987e3'
down_revision: Union[str, None] = ('003_ai_models', '8c79001578c0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
