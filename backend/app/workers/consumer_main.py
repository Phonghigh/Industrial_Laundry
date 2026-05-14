"""
Standalone entry point for the stream consumer worker.

Run this as a separate process (or Docker service) for production isolation:

    python -m app.workers.consumer_main

Or via Docker Compose `worker` service — see infra/docker-compose.yml.

Why a separate process?
- Crashes in the consumer don't affect the API (no shared asyncio event loop)
- Consumer can be scaled, restarted, or deployed independently
- Resource usage (DB pool, memory) is isolated from API workers
- Enables independent observability (separate logs, separate health check)

For lightweight single-factory dev, set RUN_CONSUMER_IN_PROCESS=true in .env
to run the consumer inside the API process instead (see main.py).
"""

import asyncio
import signal
import sys

import structlog

from app.workers.stream_consumer import run_consumer

log = structlog.get_logger()

_shutdown = False


def _handle_signal(sig, _frame):
    global _shutdown
    log.info("worker_shutdown_signal", signal=sig)
    _shutdown = True


async def main() -> None:
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    log.info("worker_process_starting")

    try:
        await run_consumer()
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.error("worker_process_fatal", error=str(exc))
        sys.exit(1)
    finally:
        log.info("worker_process_stopped")


if __name__ == "__main__":
    asyncio.run(main())
