from .main import main_bp
from .main import navigation
from .instance import instance_bp
from . import model as model_view

def init_app(app):
    app.register_blueprint(instance_bp)
    app.register_blueprint(main_bp)

    model_view.init_app(app)

    @app.context_processor
    def context_processor():
        return {
            'navigation': navigation,
        }

