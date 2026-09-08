"""ubigeo y documento de usuarios

Revision ID: c1f2a3b4d5e6
Revises: b47a12cdb3da
Create Date: 2026-09-07 22:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1f2a3b4d5e6'
down_revision = 'b47a12cdb3da'
branch_labels = None
depends_on = None


def upgrade():
    # Tablas de ubigeo del Perú
    op.create_table(
        'departamentos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('ubigeo', sa.String(length=2), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'provincias',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('ubigeo', sa.String(length=4), nullable=True),
        sa.Column('departamento_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['departamento_id'], ['departamentos.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table(
        'distritos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=150), nullable=False),
        sa.Column('ubigeo', sa.String(length=6), nullable=True),
        sa.Column('provincia_id', sa.Integer(), nullable=True),
        sa.Column('departamento_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['departamento_id'], ['departamentos.id']),
        sa.ForeignKeyConstraint(['provincia_id'], ['provincias.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Nuevas columnas en clientes (departamento, provincia, distrito)
    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('departamento', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('provincia', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('distrito', sa.String(length=150), nullable=True))

    # Nuevo campo en usuarios_sistema (DNI o Carnet de Extranjería)
    with op.batch_alter_table('usuarios_sistema', schema=None) as batch_op:
        batch_op.add_column(sa.Column('documento', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('usuarios_sistema', schema=None) as batch_op:
        batch_op.drop_column('documento')

    with op.batch_alter_table('clientes', schema=None) as batch_op:
        batch_op.drop_column('distrito')
        batch_op.drop_column('provincia')
        batch_op.drop_column('departamento')

    op.drop_table('distritos')
    op.drop_table('provincias')
    op.drop_table('departamentos')
