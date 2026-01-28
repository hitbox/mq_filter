from contextlib import contextmanager

import sqlalchemy as sa

try:
    import pymqi
except ImportError:
    pymqi = None

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import relationship

class Base(DeclarativeBase):

    @classmethod
    def get_or_create(cls, session, **kwargs):
        query = sa.select(cls).filter_by(**kwargs)
        instance = session.scalars(query).one_or_none()
        if instance is None:
            instance = cls(**kwargs)
            session.add(instance)
            session.flush()
        return instance


class Connection(Base):
    __tablename__ = 'connection'

    id = sa.Column(sa.Integer, primary_key=True)

    name = sa.Column(sa.String, nullable=False)

    host = sa.Column(sa.String, nullable=False)
    port = sa.Column(sa.String, nullable=True)

    queue_managers = relationship(
        'QueueManager',
        back_populates='connection',
    )

    def as_string(self):
        result = str(self.host)
        if self.port:
            result += f'({self.port})'
        return result


class Channel(Base):
    __tablename__ = 'channel'

    id = sa.Column(sa.Integer, primary_key=True)

    name = sa.Column(sa.String)

    queue_managers = relationship(
        'QueueManager',
        back_populates='channel',
    )


class QueueManager(Base):
    __tablename__ = 'queue_manager'

    id = sa.Column(sa.Integer, primary_key=True)

    manager_name = sa.Column(sa.String)

    channel_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('channel.id'),
    )

    channel = relationship(
        'Channel',
        back_populates='queue_managers',
    )

    connection_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('connection.id'),
    )

    connection = relationship(
        'Connection',
        back_populates='queue_managers',
    )

    source_queues = relationship(
        'Queue',
        back_populates = 'queue_manager',
    )

    @contextmanager
    def connect(self):
        kwargs = {
            'queue_manager': self.manager_name,
            'channel': self.channel.name,
            'conn_info': self.connection,
        }
        qmgr = pymqi.connect(**kwargs)
        try:
            yield qmgr
        finally:
            qmgr.disconnect()

    @classmethod
    def by_name(cls, name, session):
        query = sa.select(cls).where(cls.manager_name == name)
        return session.scalars(query).one_or_none()


class Queue(Base):
    """
    An MQ queue object to read or put to.
    """

    __tablename__ = 'queue'

    id = sa.Column(sa.Integer, primary_key=True)

    name = sa.Column(sa.String, nullable=False)

    short_name = sa.Column(sa.String, nullable=False)

    queue_manager_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('queue_manager.id'),
    )

    queue_manager = relationship(
        'QueueManager',
        back_populates = 'source_queues',
    )

    airline_source_rules = relationship(
        'AirlineRoutingRule',
        foreign_keys = 'AirlineRoutingRule.source_queue_id',
        back_populates = 'source_queue',
        uselist = False,
    )

    airline_destination_rules = relationship(
        'AirlineRoutingRule',
        foreign_keys = 'AirlineRoutingRule.destination_queue_id',
        back_populates = 'destination_queue',
        uselist = False,
    )

    source_messages = relationship(
        'MessageMove',
        foreign_keys = 'MessageMove.source_queue_id',
        back_populates = 'source_queue',
    )

    destination_messages = relationship(
        'MessageMove',
        foreign_keys = 'MessageMove.destination_queue_id',
        back_populates = 'destination_queue',
    )

    @classmethod
    def one_by_short_name(cls, short_name, session):
        query = sa.select(Queue).where(Queue.short_name == short_name)
        return session.scalars(query).one()

    def connect(self):
        kwargs = {
            'queue_manager': self.queue_manager.name,
            'channel': self.channel.name,
            'conn_info': self.connection,
        }
        return pymqi.connect(**kwargs)

    def get(self, waitms=None, browse=False, ignore_no_messages=True):
        try:
            qmgr = self.connect()

            options = 0
            if browse:
                options |= pymqi.CMQC.MQOO_BROWSE

            qconn = pymqi.Queue(qmgr, self.name, options)

            gmo = pymqi.GMO()
            if waitms is not None:
                gmo.Options |= pymqi.CMQC.MQGMO_WAIT
                gmo.WaitInterval = waitms

            if browse:
                gmo.Options |= pymqi.CMQC.MQGMO_BROWSE_FIRST

            message = None
            md = None
            try:
                md = pymqi.MD()
                message = qconn.get(None, md, gmo)

            except pymqi.MQMIError as e:
                if e.reason == pymqi.CMQC.MQRC_NO_MSG_AVAILABLE:
                    if ignore_no_messages:
                        pass
                    else:
                        raise
                else:
                    raise

            finally:
                qconn.close()

            return message, md
        finally:
            qmgr.disconnect()

    def as_row(self):
        """
        Short list of identifying names for console printing.
        """
        return [self.short_name, self.name]


class Airline(Base):
    """
    Object representing a single airline.
    """

    __tablename__ = 'airline'

    id = sa.Column(sa.Integer, primary_key=True)

    name = sa.Column(
        sa.String,
        info = {
            'title': 'Name',
        },
    )

    iata_code = sa.Column(
        sa.String(2),
        sa.CheckConstraint(
            "iata_code ~ '^[A-Z0-9]{2}$'",
        ),
        nullable = False,
        unique = True,
        info = {
            'title': 'IATA',
        },
    )

    icao_code = sa.Column(
        sa.String(3),
        sa.CheckConstraint(
            "icao_code ~ '^[A-Z0-9]{3}$'",
        ),
        nullable = False,
        unique = True,
        info = {
            'title': 'ICAO',
        },
    )

    destination_queues = relationship(
        'AirlineRoutingRule',
        back_populates = 'airline',
    )


class AirlineRoutingRule(Base):
    """
    The queue to move messages to for parsed airline code.
    """
    __tablename__ = 'airline_routing_rule'

    id = sa.Column(
        sa.Integer,
        primary_key = True,
    )

    airline_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('airline.id'),
    )

    airline = relationship(
        'Airline',
        back_populates = 'destination_queues',
        info = {
            'title': 'Airline',
        },
    )

    source_queue_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('queue.id'),
    )

    source_queue = relationship(
        'Queue',
        foreign_keys = [source_queue_id],
        back_populates = 'airline_source_rules',
        uselist = False,
        info = {
            'title': 'Source Queue',
        },
    )

    destination_queue_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('queue.id'),
    )

    destination_queue = relationship(
        'Queue',
        foreign_keys = [destination_queue_id],
        back_populates = 'airline_destination_rules',
        uselist = False,
        info = {
            'title': 'Destination Queue',
        },
    )

    @property
    def display_name(self):
        return f'{self.airline.name} to {self.destination_queue.name}'

    @classmethod
    def from_(cls, queue_manager, airline, session):
        query = sa.select(cls).where(
            cls.queue_manager_id == queue_manager.id,
            cls.airline_id == airline.id,
        )
        return session.scalars(query).one_or_none()


class Message(Base):
    __tablename__ = 'message'

    id = sa.Column(
        sa.Integer,
        primary_key = True,
    )

    message_bytes = sa.Column(sa.LargeBinary)

    moves = relationship(
        'MessageMove',
        back_populates = 'message',
    )

    @property
    def message_string(self):
        if self.message_bytes:
            return self.message_bytes.decode()
        return None


class MessageMove(Base):
    __tablename__ = 'message_move'

    id = sa.Column(
        sa.Integer,
        primary_key = True,
    )

    message_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('message.id'),
        nullable = False,
    )

    message = relationship(
        'Message',
        back_populates = 'moves',
    )

    moved_at = sa.Column(
        sa.DateTime(timezone=True),
        server_default = sa.func.now(),
        nullable = False,
    )

    source_queue_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('queue.id'),
    )

    source_queue = relationship(
        'Queue',
        foreign_keys = [source_queue_id],
        back_populates = 'source_messages',
    )

    destination_queue_id = sa.Column(
        sa.Integer,
        sa.ForeignKey('queue.id'),
    )

    destination_queue = relationship(
        'Queue',
        back_populates = 'destination_messages',
        foreign_keys = [destination_queue_id],
    )

