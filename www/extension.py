from flask_sqlalchemy import SQLAlchemy

from mq_filter.model import Base

db = SQLAlchemy(metadata=Base.metadata)
