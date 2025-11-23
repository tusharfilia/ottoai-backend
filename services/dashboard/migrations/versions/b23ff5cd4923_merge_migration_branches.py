"""merge_migration_branches

Revision ID: b23ff5cd4923
Revises: 722bd74987e3, 20250120000000
Create Date: 2025-11-23 15:50:51.329916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b23ff5cd4923'
down_revision: Union[str, None] = ('722bd74987e3', '20250120000000')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
