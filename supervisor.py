import argparse
import atexit
import configparser
import logging.config
import logging.handlers
import multiprocessing as mp
import os
import signal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from instance.database import DATABASE_URI
from mq_filter.model import AirlineRoutingRule
from mq_filter.model import Queue
from mq_filter.worker import Worker

def setup_logging(cp):
    """
    Set up logging so that all go throughs a listener queue.
    """
    paths = cp['mq_filter'].get('ensure_dirs', '').split()
    if paths:
        for path in paths:
            os.makedirs(path, exist_ok=True)
    logging.config.fileConfig(cp)

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('config', nargs='+', help='INI config')
    parser.add_argument(
        '--raise-test',
        action = 'store_true',
        help = 'Raise exception to test logging.'
    )
    args = parser.parse_args(argv)

    cp = configparser.ConfigParser()
    cp.read(args.config)

    # Configure logging if given from config.
    if set(['loggers', 'handlers', 'formatters']).issubset(cp):
        setup_logging(cp)

    logger = logging.getLogger("mq_filter.supervisor")

    if args.raise_test:
        logger.error('SMTP TEST')
        listener.stop()
        logging.shutdown()
        return

    queue_like = cp['mq_filter']['queue_like']
    engine = sa.create_engine(DATABASE_URI)
    with Session(engine) as session:
        query = (
            sa.select(Queue)
            .join(AirlineRoutingRule, AirlineRoutingRule.source_queue_id == Queue.id)
            .where(
                Queue.short_name.ilike(f'%{queue_like}%'),
            )
            .distinct()
        )
        queue = session.scalars(query).one()
        name = queue.short_name
        logger.info('%s', name)
        worker = Worker(queue.short_name)
        worker.loop_forever(DATABASE_URI)

    logger.info("supervisor shut down")

if __name__ == "__main__":
    main()
