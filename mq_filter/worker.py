import logging
import smtplib
import time

from email.message import EmailMessage

import sqlalchemy as sa

try:
    import pymqi
except ImportError:
    pymqi = None

from sqlalchemy.orm import Session

from .model import Airline
from .model import AirlineRoutingRule
from .model import Base
from .model import Message
from .model import MessageMove
from .model import Queue
from .parse import ParseError
from .parse import extract_payload_from_mq
from .parse import parse_content_for_airline

class Worker:

    def __init__(self, source_queue_short_name):
        # NOTE we use a simple string so that we can use multiprocessing; and
        # get our actual objects later.
        self.source_queue_short_name = source_queue_short_name

    def get_logger(self):
        logger = logging.getLogger(f'mq_filter.worker.{self.source_queue_short_name}')
        return logger

    def move_messages(self, session):
        logger = self.get_logger()

        source_queue = Queue.one_by_short_name(self.source_queue_short_name, session)

        queue_manager = source_queue.queue_manager

        with queue_manager.connect() as qmgr:
            for message, md in source_queue.browse_messages(qmgr, wait_interval=1000):
                # Add new message and attempt-to-move object, to database
                db_message = Message(message_bytes=message)
                message_move = MessageMove(message=db_message, source_queue=source_queue)
                session.add(db_message)
                session.add(message_move)
                session.commit()
                # Try to decode and parse message to get airline, routing it to
                # another queue.
                try:
                    content = extract_payload_from_mq(message).strip()
                except UnicodeDecodeError:
                    logger.exception(
                        'An exception occurred while decoding %r.',
                        message,
                    )
                else:
                    try:
                        # Parse content for airline code and resolve database object.
                        data = parse_content_for_airline(content)

                        # Get airline db object from two or three letter code
                        # scraped from content.
                        airline_code = data['airline_code']
                        airline = Airline.one_for_length(airline_code, session)

                        # Put message for airline rule.
                        rule = AirlineRoutingRule.one_for_airline(airline, source_queue, session)
                        rule.destination_queue.put(qmgr, db_message.message_bytes, transactional=True)
                        message_move.destination_queue = rule.destination_queue
                        logger.info(
                            'rule from data=%r airline=%s to destination_queue=%s',
                            data,
                            airline.name,
                            rule.destination_queue.short_name,
                        )

                        message_move.destination_queue = rule.destination_queue
                        logger.info(
                            'message moved from %s to %s',
                            source_queue.name,
                            message_move.destination_queue.name,
                        )

                        # Remove message from queue
                        source_queue.get_message(qmgr, md.MsgId, transactional=True)

                        # Commit message gets/puts in one transaction.
                        qmgr.commit()

                        # Commit our database work.
                        session.commit()
                    except Exception:
                        logger.exception(
                            '%s: An exception occurred while moving message.',
                            self.source_queue_short_name)
                        session.rollback()
                        qmgr.backout()

    def loop_forever(self, database_uri):
        logger = self.get_logger()
        logger.info("Starting worker for queue %s", self.source_queue_short_name)

        engine = sa.create_engine(database_uri)

        while True:
            with Session(engine) as session:
                try:
                    self.move_messages(session)
                except pymqi.MQMIError as e:
                    if e.reason == pymqi.CMQC.MQRC_CONNECTION_BROKEN:
                        logger.warning('MQ connection broken, reconnecting...')

                        # Backoff before reconnecting
                        time.sleep(2)
                        continue

                    # Any other MQ error should still crash the worker
                    raise

                except Exception:
                    # Catch-all so the worker NEVER dies
                    logger.exception("unexpected exception in worker loop")
                    time.sleep(2)
