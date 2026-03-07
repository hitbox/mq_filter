"""
HTML Table objects for database model objects.
"""
from markupsafe import escape
from markupsafe import Markup

from .html import Column
from .html import Table
from mq_filter.model import MessageMove
from mq_filter.model import Queue

def definition_list(data: dict):
    html = ['<dl>']
    for key, value in data.items():
        html.append(f'<dt>{key}</dt><dd>{escape(value)}</dd>')
    html.append('</dl>')
    return Markup(''.join(html))

queue_table = Table(
    columns = [
        Column('id'),
    ],
    model = Queue,
)

message_move_table = Table(
    columns = [
        Column('message', renderer=lambda message_move: Markup(
            f'<pre>{message_move.message.message_string}</pre>'
        )),
        Column('moved_at'),
        Column(
            'destination_queue',
            renderer = lambda message_move: message_move.destination_queue.name,
        ),
        Column(
            'data_for_airline',
            header = 'Parse',
            renderer = lambda message_move: definition_list(message_move.data_for_airline)
        ),
    ],
    model = MessageMove,
)

for_model = {
    Queue: queue_table,
    MessageMove: message_move_table,
}
