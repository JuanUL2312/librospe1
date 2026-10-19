"""conteo ciclico de inventario

Revision ID: f7c1d2e3a4b5
Revises: e4f5a6b7c8d9
Create Date: 2026-10-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7c1d2e3a4b5'
down_revision = 'e4f5a6b7c8d9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'conteos_stock',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('producto_id', sa.Integer(), sa.ForeignKey('productos.id'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios_sistema.id'), nullable=False),
        sa.Column('cantidad_sistema', sa.Integer(), nullable=False),
        sa.Column('cantidad_contada', sa.Integer(), nullable=False),
        sa.Column('diferencia', sa.Integer(), nullable=False),
        sa.Column('ajustado', sa.Integer(), server_default='0'),
        sa.Column('observacion', sa.String(length=300), nullable=True),
        sa.Column('fecha', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    with op.batch_alter_table('conteos_stock', schema=None) as batch_op:
        batch_op.create_index('ix_conteos_stock_producto', ['producto_id'], unique=False)


def downgrade():
    with op.batch_alter_table('conteos_stock', schema=None) as batch_op:
        batch_op.drop_index('ix_conteos_stock_producto')
    op.drop_table('conteos_stock')
