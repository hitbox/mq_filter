from flask import Blueprint
from flask import render_template
from flask.views import View

from www.extension import db

from mq_filter.model import Airline

class InstanceView(View):

    def __init__(self, model, template):
        self.model = model
        self.template = template

    def dispatch_request(self, **instance_identity):
        instance = db.session.get(self.model, instance_identity)
        context = {
            'instance': instance,
        }
        return render_template(self.template, **context)


instance_bp = Blueprint('instance', __name__)

instance_bp.add_url_rule(
    '/airline/<int:id>',
    view_func = InstanceView.as_view('airline', Airline, 'airline.html'),
)

instance_bp.add_url_rule(
    '/queue/<int:id>',
    view_func = InstanceView.as_view('queue', Airline, 'queue.html'),
)
