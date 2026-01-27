from flask import Blueprint
from flask import render_template
from flask import url_for
from flask.views import View
from markupsafe import Markup
from sqlalchemy import inspect

from www.extension import db

from mq_filter import model as model_module
from mq_filter.model import Airline
from mq_filter.model import Connection
from mq_filter.model import Channel
from mq_filter.model import QueueManager
from mq_filter.model import Queue
from mq_filter.model import AirlineRoutingRule
from mq_filter.model import Message
from mq_filter.model import MessageMove

class ListView(View):

    def __init__(self, querygetter, template, more_context=None):
        self.querygetter = querygetter
        self.template = template
        self.more_context = more_context

    def dispatch_request(self):
        objects = db.session.scalars(self.querygetter()).all()
        context = {
            'objects': objects,
        }
        if self.more_context:
            context.update(self.more_context)
        return render_template(self.template, **context)


class InstanceView(View):

    def __init__(self, model, template, more_context=None):
        self.model = model
        self.template = template
        self.more_context = more_context

    def dispatch_request(self, **identity):
        instance = db.session.get(self.model, identity)
        context = {
            'instance': instance,
        }
        if self.more_context:
            context.update(self.more_context)
        return render_template(self.template, **context)


url_type = {
    int: 'int',
}

def render_object(obj):
    if isinstance(obj, Airline):
        href = url_for('airline.instance', id=obj.id)
        html = f'<a href="{ href }">{ obj.name }</a>'
    elif isinstance(obj, Queue):
        href = url_for('queue.instance', id=obj.id)
        html = f'<a href="{ href }">{ obj.name }</a>'
    elif isinstance(obj, QueueManager):
        href = url_for('queue_manager.instance', id=obj.id)
        html = f'<a href="{ href }">{ obj.manager_name }</a>'
    elif isinstance(obj, AirlineRoutingRule):
        href = url_for('airline_routing_rule.instance', id=obj.id)
        html = f'<a href="{ href }">{ obj.display_name }</a>'
    elif obj is not None:
        html = str(obj)
    else:
        html = ''
    return Markup(html)

def name_or_title(column, key):
    info = getattr(column, 'info', {})
    return info.get('title', getattr(column, 'name', key))

def table_model(model, skip_pk=True, skip_fk=True):
    """
    Create data structure for templates to render a table from a model and its
    instances.
    """
    inspector = inspect(model)

    attributes = []
    for key, attr in inspector.all_orm_descriptors.items():
        if key.startswith('_'):
            continue

        if skip_pk and hasattr(attr, 'primary_key') and attr.primary_key:
            continue

        if skip_fk and hasattr(attr, 'foreign_keys') and attr.foreign_keys:
            continue

        attributes.append((key, attr))

    table = {
        'model': model,
        'attributes': attributes,
        'titles': [name_or_title(attr, key) for key, attr in attributes],
    }
    return table

def create_model_blueprint(model, prefix=None):
    model_bp = Blueprint(model.__tablename__, __name__)

    if prefix is None:
        prefix = ''

    debug = False
    model_bp.add_url_rule(
        f'{prefix}/{model.__tablename__}',
        view_func = ListView.as_view(
            name = 'list',
            querygetter = lambda: db.select(model),
            template = 'table.html',
            more_context = {
                'title': model.__tablename__,
                'description': model.__doc__,
                'table': table_model(model),
                'instance_links': True,
                'render_object': render_object,
                'debug': debug,
            },
        )
    )

    inspector = inspect(model)
    instance_url = f'{prefix}/{model.__tablename__}'

    for key in inspector.primary_key:
        arg_type = url_type[key.type.python_type]
        instance_url += f'/<{arg_type}:{key.name}>'

    model_bp.add_url_rule(
        instance_url,
        view_func = InstanceView.as_view(
            name = 'instance',
            model = model,
            template = 'instance.html',
            more_context = {
                'title': model.__tablename__,
                'table': table_model(model),
                'render_object': render_object,
                'debug': debug,
            }
        )
    )

    return model_bp

def init_app(app):
    index_bp = Blueprint('index', __name__, url_prefix=prefix)

    @index_bp.route('/')
    def root():
        list_items = []

        html = []
        for name in model_views:
            item = {
                'href': url_for(f'{name}.list'),
                'name': name,
            }
            list_items.append(item)

        context = {
            'list_items': list_items,
            'title': 'Object Index',
        }
        return render_template('list.html', **context)

    app.register_blueprint(index_bp)

    for blueprint in model_views.values():
        app.register_blueprint(blueprint)

prefix = '/obj'
model_views = {
    'airline': create_model_blueprint(Airline, prefix),
    'connection': create_model_blueprint(Connection, prefix),
    'channel': create_model_blueprint(Channel, prefix),
    'queue_manager': create_model_blueprint(QueueManager, prefix),
    'queue': create_model_blueprint(Queue, prefix),
    'airline_routing_rule': create_model_blueprint(AirlineRoutingRule, prefix),
    'message': create_model_blueprint(Message, prefix),
    'message_move': create_model_blueprint(MessageMove, prefix),
}

