"""initial_schema

Revision ID: db672d8bf9b3
Revises: 
Create Date: 2026-11-17 16:01:02.615827

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'db672d8bf9b3'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('gender', sa.String(length=50), nullable=True),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='Patient'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('Guest', 'Patient', 'Admin')", name='ck_users_role'),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True, if_not_exists=True)

    # 2. Consultations table
    op.create_table(
        'consultations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('symptoms', sa.Text(), nullable=False),
        sa.Column('prediction', sa.String(length=100), nullable=False),
        sa.Column('triage_level', sa.String(length=20), nullable=False),
        sa.Column('specialist', sa.String(length=100), nullable=False, server_default='General Physician'),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("triage_level IN ('Low', 'Medium', 'High')", name='ck_consult_triage'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        if_not_exists=True,
    )
    op.create_index('ix_consultations_user_id', 'consultations', ['user_id'], unique=False, if_not_exists=True)
    op.create_index('ix_consultations_timestamp', 'consultations', ['timestamp'], unique=False, if_not_exists=True)

    # 3. Feedback table
    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('consult_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comments', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_feedback_rating'),
        sa.ForeignKeyConstraint(['consult_id'], ['consultations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('consult_id'),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table('feedback', if_exists=True)
    op.drop_table('consultations', if_exists=True)
    op.drop_table('users', if_exists=True)
