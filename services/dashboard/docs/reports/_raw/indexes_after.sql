=== DATABASE INDEXES ===
migrations/versions/002_add_performance_indexes.py:"""Add performance indexes for tenant-scoped queries
migrations/versions/002_add_performance_indexes.py:Revision ID: 002_add_performance_indexes
migrations/versions/002_add_performance_indexes.py:revision = '002_add_performance_indexes'
migrations/versions/002_add_performance_indexes.py:    """Add performance indexes for tenant-scoped queries."""
migrations/versions/002_add_performance_indexes.py:    # Add indexes for calls table (if it exists)
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_calls_tenant_created_at', 'calls', ['tenant_id', 'created_at'])
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_calls_tenant_status', 'calls', ['tenant_id', 'status'])
migrations/versions/002_add_performance_indexes.py:    # Add indexes for followups table (if it exists)
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_followups_tenant_created_at', 'followups', ['tenant_id', 'created_at'])
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_followups_tenant_status', 'followups', ['tenant_id', 'status'])
migrations/versions/002_add_performance_indexes.py:    # Add indexes for messages table (if it exists)
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_messages_tenant_created_at', 'messages', ['tenant_id', 'created_at'])
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_messages_tenant_status', 'messages', ['tenant_id', 'status'])
migrations/versions/002_add_performance_indexes.py:    # Add indexes for leads/contacts table (if it exists)
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_leads_tenant_phone', 'leads', ['tenant_id', 'phone'])
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_contacts_tenant_phone', 'contacts', ['tenant_id', 'phone'])
migrations/versions/002_add_performance_indexes.py:    # Add indexes for appointments table (if it exists)
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_appointments_tenant_created_at', 'appointments', ['tenant_id', 'created_at'])
migrations/versions/002_add_performance_indexes.py:        op.create_index('ix_appointments_tenant_status', 'appointments', ['tenant_id', 'status'])
migrations/versions/002_add_performance_indexes.py:    """Remove performance indexes."""
migrations/versions/002_add_performance_indexes.py:    # Remove indexes for calls table
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_calls_tenant_created_at', 'calls')
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_calls_tenant_status', 'calls')
migrations/versions/002_add_performance_indexes.py:    # Remove indexes for followups table
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_followups_tenant_created_at', 'followups')
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_followups_tenant_status', 'followups')
migrations/versions/002_add_performance_indexes.py:    # Remove indexes for messages table
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_messages_tenant_created_at', 'messages')
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_messages_tenant_status', 'messages')
migrations/versions/002_add_performance_indexes.py:    # Remove indexes for leads/contacts table
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_leads_tenant_phone', 'leads')
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_contacts_tenant_phone', 'contacts')
migrations/versions/002_add_performance_indexes.py:    # Remove indexes for appointments table
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_appointments_tenant_created_at', 'appointments')
migrations/versions/002_add_performance_indexes.py:        op.drop_index('ix_appointments_tenant_status', 'appointments')
migrations/versions/20250426190959_8c79001578c0_recreate_all_tables.py:    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=True)
migrations/versions/20250426190959_8c79001578c0_recreate_all_tables.py:    op.create_index(op.f('ix_services_name'), 'services', ['name'], unique=True)
migrations/versions/20250426190959_8c79001578c0_recreate_all_tables.py:    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
migrations/versions/20250426190959_8c79001578c0_recreate_all_tables.py:    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
migrations/versions/backups/3e87b46d526e_recreate_all_tables_manually.py:    op.create_index(op.f('ix_companies_name'), 'companies', ['name'], unique=True)
migrations/versions/backups/3e87b46d526e_recreate_all_tables_manually.py:    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
migrations/versions/backups/3e87b46d526e_recreate_all_tables_manually.py:    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
migrations/versions/backups/3e87b46d526e_recreate_all_tables_manually.py:    op.create_index(op.f('ix_calls_call_id'), 'calls', ['call_id'], unique=False)
migrations/versions/backups/3e87b46d526e_recreate_all_tables_manually.py:    op.create_index(op.f('ix_transcript_analyses_analysis_id'), 'transcript_analyses', ['analysis_id'], unique=False)
migrations/versions/backups/create_transcript_analyses_table.py:        sa.Index('ix_transcript_analyses_analysis_id', 'analysis_id')
migrations/versions/backups/create_transcript_analyses_table.py:    # Create index on call_id for faster lookups
migrations/versions/backups/create_transcript_analyses_table.py:    op.create_index('ix_transcript_analyses_call_id', 'transcript_analyses', ['call_id'], unique=False)
migrations/versions/backups/create_transcript_analyses_table.py:    # Drop indexes first
migrations/versions/backups/create_transcript_analyses_table.py:    op.drop_index('ix_transcript_analyses_call_id', table_name='transcript_analyses')
migrations/versions/backups/create_transcript_analyses_table.py:    op.drop_index('ix_transcript_analyses_analysis_id', table_name='transcript_analyses')
migrations/versions/backups/664f29938dcc_remove_appointment_id_from_calls.py:    # First check if the index exists before trying to drop it
migrations/versions/backups/664f29938dcc_remove_appointment_id_from_calls.py:    indexes = insp.get_indexes('calls')
migrations/versions/backups/664f29938dcc_remove_appointment_id_from_calls.py:    index_names = [index['name'] for index in indexes]
migrations/versions/backups/664f29938dcc_remove_appointment_id_from_calls.py:    # Only drop the index if it exists
migrations/versions/backups/664f29938dcc_remove_appointment_id_from_calls.py:    if 'ix_calls_appointment_id' in index_names:
migrations/versions/backups/664f29938dcc_remove_appointment_id_from_calls.py:        op.drop_index(op.f('ix_calls_appointment_id'), table_name='calls')
migrations/versions/backups/664f29938dcc_remove_appointment_id_from_calls.py:    # Add the index back
migrations/versions/backups/664f29938dcc_remove_appointment_id_from_calls.py:    op.create_index(op.f('ix_calls_appointment_id'), 'calls', ['appointment_id'], unique=False)
migrations/versions/001_add_idempotency_keys.py:    # Create indexes
migrations/versions/001_add_idempotency_keys.py:    op.create_index(
migrations/versions/001_add_idempotency_keys.py:    op.create_index(
migrations/versions/001_add_idempotency_keys.py:    op.drop_index('idx_idem_provider_tenant', table_name='idempotency_keys')
migrations/versions/001_add_idempotency_keys.py:    op.drop_index('idx_idem_last_seen', table_name='idempotency_keys')
