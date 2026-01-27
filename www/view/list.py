from flask import Blueprint
from flask import render_template
from flask.views import View

from www.extension import db

from mq_filter.model import Airline

class ListView(View):

    def __init__(self, querygetter, template):
        self.querygetter = querygetter
        self.template = template

    def dispatch_request(self):
        objects = db.scalars(self.querygetter()).all()
        context = {
            'instance': instance,
            'objects': objects,
        }
        return render_template(self.template, **context)


list_bp = Blueprint('list', __name__)

list_bp.add_url_rule(
    '/airline',
    view_func = InstanceView.as_view('airline', lambda: db.select(Airline), 'airline.html'),
)
