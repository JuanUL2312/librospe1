"""caja y metodo de pago en ventas

Revision ID: d2e3f4a5b6c7
Revises: c1f2a3b4d5e6
Create Date: 2026-09-07 23:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd2e3f4a5b6c7'
down_revision = 'c1f2a3b4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # Tabla de caja (apertura/cierre)
    op.create_table(
        'cajas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('monto_inicial', sa.Numeric(10, 2), nullable=True),
        sa.Column('fecha_apertura', sa.DateTime(), nullable=True),
        sa.Column('fecha_cierre', sa.DateTime(), nullable=True),
        sa.Column('monto_esperado', sa.Numeric(10, 2), nullable=True),
        sa.Column('monto_real', sa.Numeric(10, 2), nullable=True),
        sa.Column('diferencia', sa.Numeric(10, 2), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios_sistema.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Nuevas columnas en ventas (método de pago y vuelto)
    with op.batch_alter_table('ventas', schema=None) as batch_op:
        batch_op.add_column(sa.Column('metodo_pago', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('monto_recibido', sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column('vuelto', sa.Numeric(10, 2), nullable=True))


def downgrade():
    with op.batch_alter_table('ventas', schema=None) as batch_op:
        batch_op.drop_column('vuelto')
        batch_op.drop_column('monto_recibido')
        batch_op.drop_column('metodo_pago')

    op.drop_table('cajas')
