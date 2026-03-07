"""add unique airline routing rule constraint

Revision ID: b7e04932b129
Revises: 
Create Date: 2026-03-07 09:24:00.035004

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = 'b7e04932b129'
down_revision = None
branch_labels = None
depends_on = None

metadata = sa.MetaData()

airline_routing_rule_table = sa.Table(
    'airline_routing_rule',
    metadata,
    sa.Column('id', sa.Integer, primary_key=True),
    sa.Column('airline_id', sa.Integer, sa.ForeignKey('airline.id')),
    sa.Column('source_queue_id', sa.Integer, sa.ForeignKey('queue.id'), nullable=False),
    sa.Column('destination_queue_id', sa.Integer, sa.ForeignKey('queue.id'), nullable=False),
)

def upgrade():
    """
    Upgrade schema.
    """
    # Remove existing dupes
    conn = op.get_bind()

    duplicates = (
        sa.select(
            airline_routing_rule_table.c.id,
            sa.func.row_number().over(
                partition_by=(
                    airline_routing_rule_table.c.airline_id,
                    airline_routing_rule_table.c.source_queue_id,
                    airline_routing_rule_table.c.destination_queue_id
                ),
                order_by=airline_routing_rule_table.c.id
            ).label("rn")
        ).cte("duplicates")
    )

    # Delete all rows where rn > 1
    del_stmt = (
        sa.delete(airline_routing_rule_table)
        .where(airline_routing_rule_table.c.id.in_(
            sa.select(duplicates.c.id).where(duplicates.c.rn > 1)
        ))
    )

    conn.execute(del_stmt)

    op.alter_column(
        'airline_routing_rule',
        'source_queue_id',
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.alter_column(
        'airline_routing_rule',
        'destination_queue_id',
        existing_type=sa.INTEGER(),
        nullable=False,
    )
    op.create_unique_constraint(
        'unique_airline_routing_rule',
        'airline_routing_rule',
        [
            'airline_id',
            'source_queue_id',
             'destination_queue_id',
        ]
    )


def downgrade():
    """
    Downgrade schema.
    """
    op.drop_constraint('unique_airline_routing_rule', 'airline_routing_rule', type_='unique')
    op.alter_column('airline_routing_rule', 'destination_queue_id',
               existing_type=sa.INTEGER(),
               nullable=True)
    op.alter_column('airline_routing_rule', 'source_queue_id',
               existing_type=sa.INTEGER(),
               nullable=True)
