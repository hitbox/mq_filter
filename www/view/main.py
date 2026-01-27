from flask import Blueprint
from flask import render_template

from www.extension import db
from www.html import Table

from mq_filter.model import Queue
from mq_filter.model import Airline
from mq_filter.model import AirlineRoutingRule

main_bp = Blueprint('main', __name__)

rules_table = Table(
    attributes = [
        'airline.iata_code',
        'source_queue.name',
        'destination_queue.name',
    ],
)

rules_table.model_class = AirlineRoutingRule

navigation = [
    {
        'endpoint': 'main.root',
        'text': 'Home',
    },
    {
        'endpoint': 'main.about',
        'text': 'About',
    },
    {
        'endpoint': 'main.contact',
        'text': 'Contact',
    },
    {
        'endpoint': 'main.rules',
        'text': 'Routing Rules',
    },
    {
        'endpoint': 'index.root',
        'text': 'Objects',
    },
]

@main_bp.route('/')
def root():
    return render_template('base.html')

@main_bp.route('/about')
def about():
    return render_template('about.html')

@main_bp.route('/contact')
def contact():
    return render_template('contact.html')

@main_bp.route('/rules')
def rules():
    query = (
        db.select(AirlineRoutingRule)
        .join(Airline)
        .join(Queue, Queue.id == AirlineRoutingRule.source_queue_id)
        .order_by(Airline.name, Queue.name)
    )
    rules = db.session.scalars(query).all()

    context = {
        'rules': rules,
        'table': rules_table,
    }

    return render_template('rules.html', **context)
