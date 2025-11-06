"""Add storage tables

Revision ID: 2025110601_storage_tables
Revises: 4c055ac6469f
Create Date: 2025-11-06 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2025110601_storage_tables'
down_revision = '4c055ac6469f'
branch_labels = None
depends_on = None


def upgrade():
    """Create storage-related tables."""
    
    # Create storage_files table
    op.create_table('storage_files',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('path', sa.String(length=1000), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('size', sa.BigInteger(), nullable=True),
        sa.Column('content_type', sa.String(length=255), nullable=True),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('is_directory', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_key')
    )
    
    # Create indexes for storage_files
    op.create_index('idx_storage_files_project_path', 'storage_files', ['project_id', 'path'])
    op.create_index('idx_storage_files_user_path', 'storage_files', ['user_id', 'path'])
    op.create_index('idx_storage_files_active', 'storage_files', ['is_deleted', 'project_id', 'user_id'])
    op.create_index(op.f('ix_storage_files_project_id'), 'storage_files', ['project_id'])
    op.create_index(op.f('ix_storage_files_user_id'), 'storage_files', ['user_id'])
    op.create_index(op.f('ix_storage_files_path'), 'storage_files', ['path'])
    
    # Create file_versions table
    op.create_table('file_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('storage_key', sa.String(length=500), nullable=False),
        sa.Column('size', sa.BigInteger(), nullable=True),
        sa.Column('comment', sa.Text(), nullable=True),
        sa.Column('tag', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['file_id'], ['storage_files.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_id', 'version_number')
    )
    
    # Create indexes for file_versions
    op.create_index('idx_file_versions_file_id', 'file_versions', ['file_id'])
    op.create_index('idx_file_versions_tag', 'file_versions', ['tag'])


def downgrade():
    """Drop storage-related tables."""
    
    # Drop indexes first
    op.drop_index('idx_file_versions_tag', table_name='file_versions')
    op.drop_index('idx_file_versions_file_id', table_name='file_versions')
    op.drop_index(op.f('ix_storage_files_path'), table_name='storage_files')
    op.drop_index(op.f('ix_storage_files_user_id'), table_name='storage_files')
    op.drop_index(op.f('ix_storage_files_project_id'), table_name='storage_files')
    op.drop_index('idx_storage_files_active', table_name='storage_files')
    op.drop_index('idx_storage_files_user_path', table_name='storage_files')
    op.drop_index('idx_storage_files_project_path', table_name='storage_files')
    
    # Drop tables
    op.drop_table('file_versions')
    op.drop_table('storage_files')