# Migration Rebuild Scripts

These scripts help you rebuild database migrations from your SQLAlchemy models when your dev and prod environments have diverged.

## Scripts Overview

1. `generate_migration_metadata.py` - Extracts metadata from your SQLAlchemy models (without requiring a database connection)
2. `generate_migration_from_metadata.py` - Generates an Alembic migration from the extracted metadata
3. `rebuild_migrations.py` - Master script that runs the above scripts in sequence with proper error handling

## How to Use

### Option 1: Quick Rebuild

Run the master script:

```bash
# From the dashboard directory
python scripts/rebuild_migrations.py

# Or from the scripts directory
python rebuild_migrations.py
```

This will:
1. Extract model metadata from your SQLAlchemy models
2. Generate a new migration file that recreates all tables
3. Update the `most_recent_migration.txt` file

### Option 2: Step-by-Step

If you prefer to run each step manually:

1. Extract model metadata:
```bash
# From the dashboard directory
python scripts/generate_migration_metadata.py

# Or from the scripts directory
python generate_migration_metadata.py
```

2. Generate migration from metadata:
```bash
# From the dashboard directory
python scripts/generate_migration_from_metadata.py

# Or from the scripts directory
python generate_migration_from_metadata.py
```

## Applying the Migration

After generating the migration, you can apply it with:

```bash
cd backend/services/dashboard
alembic upgrade head
```

## Important Notes

1. **No Database Connection Required**: The metadata extraction script uses regex pattern matching to analyze model files directly, so it doesn't require a database connection.

2. **Make Backups**: Always back up your database before applying these migrations.

3. **Review Generated Migrations**: The generated migration drops and recreates all tables. Review it carefully to ensure it's correct.

4. **Data Loss Warning**: This approach will delete all data in your tables. If you need to preserve data, you'll need to handle data migration separately.

5. **Foreign Key Constraints**: The script attempts to drop tables in reverse order, but you may need to adjust the order if you have complex foreign key relationships.

6. **Custom Indexes and Constraints**: The current implementation may not capture all custom indexes or constraints. Review and add these manually if needed.

7. **Path Flexibility**: The scripts are designed to work regardless of which directory you run them from. They will automatically locate the dashboard directory.

## Troubleshooting

1. **Parse Errors**: If the script can't parse your model files correctly, you may need to manually adjust the `model_metadata.py` file that gets generated.

2. **Missing Columns**: The regex parsing approach might miss some complex column definitions. Check the generated migration to ensure all columns are included.

3. **Circular Dependencies**: If your tables have circular foreign key references, you may need to modify the migration file to use deferred constraints. 