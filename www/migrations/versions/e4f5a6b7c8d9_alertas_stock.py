"""alertas de stock configurables

Revision ID: e4f5a6b7c8d9
Revises: d2e3f4a5b6c7
Create Date: 2026-09-07 23:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e4f5a6b7c8d9'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('productos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stock_minimo', sa.Integer(), nullable=True, server_default='5'))
        batch_op.add_column(sa.Column('stock_maximo', sa.Integer(), nullable=True, server_default='100'))


def downgrade():
    with op.batch_alter_table('productos', schema=None) as batch_op:
        batch_op.drop_column('stock_maximo')
        batch_op.drop_column('stock_minimo')
