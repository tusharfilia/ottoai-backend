"""remove_has_transcript_fields

Revision ID: efbcc30cbcfc
Revises: 664f29938dcc
Create Date: 2025-04-09 20:55:32.307548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'efbcc30cbcfc'
down_revision: Union[str, None] = '664f29938dcc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the has_transcript and has_in_person_transcript columns from the calls table
    op.drop_column('calls', 'has_transcript')
    
    # Check if has_in_person_transcript exists before dropping it
    conn = op.get_bind()
    insp = sa.engine.reflection.Inspector.from_engine(conn)
    columns = [column['name'] for column in insp.get_columns('calls')]
    
    if 'has_in_person_transcript' in columns:
        op.drop_column('calls', 'has_in_person_transcript')


def downgrade() -> None:
    # Add the has_transcript and has_in_person_transcript columns back
    op.add_column('calls', sa.Column('has_transcript', sa.Boolean(), nullable=True, server_default=sa.text('false')))
    op.add_column('calls', sa.Column('has_in_person_transcript', sa.Boolean(), nullable=True, server_default=sa.text('false')))
