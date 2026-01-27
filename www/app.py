from flask import Flask

from .extension import db
from . import view

def create_app():
    app = Flask(__name__)

    app.config.from_envvar('MQ_FILTER_WWW_CONFIG')

    db.init_app(app)
    view.init_app(app)

    return app
