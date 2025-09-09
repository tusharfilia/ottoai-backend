"""remove_appointment_id_from_calls

Revision ID: 664f29938dcc
Revises: add_in_person_transcript
Create Date: 2025-04-09 20:36:19.682997

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '664f29938dcc'
down_revision: Union[str, None] = 'add_in_person_transcript'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the appointment_id column from the calls table
    # First check if the index exists before trying to drop it
    conn = op.get_bind()
    insp = Inspector.from_engine(conn)
    indexes = insp.get_indexes('calls')
    index_names = [index['name'] for index in indexes]
    
    # Only drop the index if it exists
    if 'ix_calls_appointment_id' in index_names:
        op.drop_index(op.f('ix_calls_appointment_id'), table_name='calls')
    
    # Then drop the column
    op.drop_column('calls', 'appointment_id')


def downgrade() -> None:
    # Add the appointment_id column back
    op.add_column('calls', sa.Column('appointment_id', sa.String(), nullable=True))
    # Add the index back
    op.create_index(op.f('ix_calls_appointment_id'), 'calls', ['appointment_id'], unique=False)
