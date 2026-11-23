"""
SENTINEL proactive scheduler service (Phase 4).

Standalone service that runs the investigation scheduler.
Decoupled from API so scheduler keeps running even if API restarts.

Usage (standalone):
    python -m sentinel.scheduler.main

Usage (Docker):
    docker run ... python -m sentinel.scheduler.main
"""
import asyncio
import logging
import signal
from datetime import datetime

from configs.logging_config import configure_logging
from sentinel.scheduler.proactive import start_scheduler, stop_scheduler

configure_logging()
logger = logging.getLogger(__name__)


def handle_signal(signum, frame):
    """Graceful shutdown on SIGTERM/SIGINT."""
    logger.info('{"event":"scheduler_shutdown_requested","signal":%d}', signum)
    stop_scheduler()
    logger.info('{"event":"scheduler_stopped"}')
    exit(0)


async def main():
    """Start scheduler and block forever (until signal)."""
    logger.info('{"event":"scheduler_starting","timestamp":"%s"}', datetime.utcnow().isoformat())

    # Register signal handlers
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    start_scheduler()
    logger.info('{"event":"scheduler_started"}')

    # Block forever (signals will trigger shutdown)
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info('{"event":"scheduler_interrupted_by_user"}')
        stop_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
