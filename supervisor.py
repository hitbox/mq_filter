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
    paths = cp['mq_filter'].get('ensure_dirs').split()
    for path in paths:
        os.makedirs(path, exist_ok=True)
    logging.config.fileConfig(cp)

    root = logging.getLogger()
    # copy root handlers to give to queue listener
    handlers = root.handlers[:]
    root.handlers.clear()

    log_queue = mp.Queue(-1)
    listener = logging.handlers.QueueListener(
        log_queue,
        *handlers,
        respect_handler_level=True,
    )
    listener.start()

    root.addHandler(logging.handlers.QueueHandler(log_queue))
    return log_queue, listener

def configure_worker_logging(log_queue):
    """
    Configure logging inside a worker process.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove any inherited handlers (important!)
    root.handlers.clear()

    queue_handler = logging.handlers.QueueHandler(log_queue)
    root.addHandler(queue_handler)

def worker_entry(worker, db_uri, log_queue, stop_event):
    """
    Wrapper so logging is configured before worker code runs.
    """
    configure_worker_logging(log_queue)

    logger = logging.getLogger("mq_filter.worker")

    worker.loop_forever(db_uri, stop_event)

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
        log_queue, listener = setup_logging(cp)

    logger = logging.getLogger("mq_filter.supervisor")

    if args.raise_test:
        logger.error('SMTP TEST')
        listener.stop()
        logging.shutdown()
        return

    stop_event = mp.Event()
    workers = []

    def shutdown(signum=None, frame=None):
        if stop_event.is_set():
            # already stopping
            return

        logger.info('shutdown signal=%s', signum)
        stop_event.set()
        for p in workers:
            logger.info('waiting 15 second for worker %s to stop', p.name)
            p.join(timeout=15)
            if p.is_alive():
                logger.warning('killing worker %s(pid=%s) to stop', p.name, p.pid)
                p.kill()
                p.join()
        logger.info('all workers stopped')
        listener.stop()
        logging.shutdown()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    atexit.register(shutdown)

    queue_like = cp['mq_filter']['queue_like']

    engine = sa.create_engine(DATABASE_URI)
    with Session(engine) as session:
        query = (
            sa.select(Queue)
            .join(AirlineRoutingRule, AirlineRoutingRule.source_queue_id == Queue.id)
            .where(
                Queue.short_name.ilike(queue_like),
            )
            .distinct()
        )
        for queue in session.scalars(query):
            name = queue.short_name
            logger.info('%s', name)
            worker = Worker(name)

            process = mp.Process(
                target = worker_entry,
                args = (worker, DATABASE_URI, log_queue, stop_event),
                name = f"worker-{name}",
                daemon = True,
            )
            workers.append(process)

    logger.info("Starting %d workers", len(workers))
    for p in workers:
        p.start()

    # wait for signal/atexit handler to stop us
    stop_event.wait()

    logger.info("supervisor shut down")

if __name__ == "__main__":
    main()
