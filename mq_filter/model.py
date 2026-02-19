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

    def _connect(self):
        return pymqi.connect(
            queue_manager = self.manager_name,
            channel = self.channel.name,
            conn_info = self.connection.as_string(),
        )

    @contextmanager
    def connect(self):
        _qmgr = self._connect()
        try:
            yield _qmgr
        finally:
            _qmgr.disconnect()

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

    @classmethod
    def all_like_name(cls, short_name_pattern, session):
        query = sa.select(cls).where(cls.short_name.ilike(short_name_pattern)).order_by(cls.short_name)
        return session.scalars(query)

    @contextmanager
    def open(self, qmgr, options=None):
        if options is None:
            options = 0

        q = pymqi.Queue(qmgr, self.name, options)
        try:
            yield q
        finally:
            q.close()

    def browse_messages(self, qmgr, wait_interval=10_000):
        """
        Generate (mesage, md) tuples from queue without removing them. Use
        .get_mesage(md.MsgId) to remove message.
        """
        # XXX
        # - Absolutely cannot have a generator here. It is completely broken.
        qopts =  pymqi.CMQC.MQOO_INPUT_AS_Q_DEF | pymqi.CMQC.MQOO_BROWSE
        gmo = pymqi.GMO()

        messages = []

        with self.open(qmgr, qopts) as q:
            # BROWSE_FIRST on first iteration
            gmo.Options = pymqi.CMQC.MQGMO_BROWSE_FIRST | pymqi.CMQC.MQGMO_WAIT
            gmo.WaitInterval = wait_interval
            while True:
                try:
                    md = pymqi.MD()
                    message = q.get(None, md, gmo)
                    messages.append((message, md))
                except pymqi.MQMIError as e:
                    if e.reason == pymqi.CMQC.MQRC_NO_MSG_AVAILABLE:
                        # Break on no message or browsing ended.
                        break
                    raise

                # Switch to Browse next
                gmo.Options = pymqi.CMQC.MQGMO_BROWSE_NEXT | pymqi.CMQC.MQGMO_WAIT

        return messages

    def get_message(self, qmgr, message_id):
        q = pymqi.Queue(qmgr, self.name, pymqi.CMQC.MQOO_INPUT_AS_Q_DEF)
        try:
            md = pymqi.MD()
            md.MsgId = message_id

            gmo = pymqi.GMO()
            gmo.Options = pymqi.CMQC.MQMO_MATCH_MSG_ID

            message = q.get(None, md, gmo)
            qmgr.commit()
            return message
        finally:
            q.close()

    def put(self, qmgr, message):
        qconn = pymqi.Queue(qmgr, self.name)
        qconn.put(message)

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

    @classmethod
    def one_for_length(cls, airline_code, session):
        if len(airline_code) == 2:
            column = Airline.iata_code
        elif len(airline_code) == 3:
            column = Airline.icao_code
        query = (
            sa.select(Airline)
            .where(
                column == airline_code
            )
        )
        return session.scalars(query).one()


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
        nullable = False,
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
        nullable = False,
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
    def one_for_airline(cls, airline, source_queue, session):
        query = sa.select(
            AirlineRoutingRule
        ).where(
            AirlineRoutingRule.airline == airline,
            AirlineRoutingRule.source_queue == source_queue,
        )
        return session.scalars(query).one()


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
