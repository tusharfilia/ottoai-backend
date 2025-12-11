"""Add appointment location fields and assigned_by_csr_id

Revision ID: 8168aa9bda7a
Revises: 20251209000000
Create Date: 2025-12-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8168aa9bda7a'
down_revision = '20251209000000'
branch_labels = None
depends_on = None


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade():
    # Add location_address to appointments table (from Shunya entities)
    if not column_exists('appointments', 'location_address'):
        op.add_column(
            'appointments',
            sa.Column('location_address', sa.String(), nullable=True, comment='Address from Shunya entities (triggers property enrichment)')
        )
    
    # Add location_lat and location_lng to appointments table (for geofencing)
    if not column_exists('appointments', 'location_lat'):
        op.add_column(
            'appointments',
            sa.Column('location_lat', sa.Float(), nullable=True, comment='Latitude for geofencing (synced from geo_lat or property enrichment)')
        )
    
    if not column_exists('appointments', 'location_lng'):
        op.add_column(
            'appointments',
            sa.Column('location_lng', sa.Float(), nullable=True, comment='Longitude for geofencing (synced from geo_lng or property enrichment)')
        )
    
    # Add assigned_by_csr_id to appointments table (CSR who assigned the appointment)
    if not column_exists('appointments', 'assigned_by_csr_id'):
        op.add_column(
            'appointments',
            sa.Column('assigned_by_csr_id', sa.String(), sa.ForeignKey('users.id'), nullable=True, comment='CSR user ID who assigned this appointment')
        )
        op.create_index(op.f('ix_appointments_assigned_by_csr_id'), 'appointments', ['assigned_by_csr_id'], unique=False)


def downgrade():
    # Drop assigned_by_csr_id
    if column_exists('appointments', 'assigned_by_csr_id'):
        op.drop_index(op.f('ix_appointments_assigned_by_csr_id'), table_name='appointments')
        op.drop_column('appointments', 'assigned_by_csr_id')
    
    # Drop location_lng
    if column_exists('appointments', 'location_lng'):
        op.drop_column('appointments', 'location_lng')
    
    # Drop location_lat
    if column_exists('appointments', 'location_lat'):
        op.drop_column('appointments', 'location_lat')
    
    # Drop location_address
    if column_exists('appointments', 'location_address'):
        op.drop_column('appointments', 'location_address')
