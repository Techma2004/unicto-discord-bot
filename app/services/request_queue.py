import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Any


logger = logging.getLogger("nova")


@dataclass
class QueueRequest:
    """
    Represents one request waiting to be processed.
    """

    handler: Callable[..., Awaitable[Any]]
    args: tuple
    kwargs: dict
    future: asyncio.Future


class RequestQueue:
    """
    Controls how many NOVA AI requests can be processed
    at the same time.

    Current configuration:
    - 1 Gemini request at a time
    - Maximum 20 waiting requests
    """

    MAX_QUEUE_SIZE = 20
    WORKERS = 1

    def __init__(self):
        self.queue = asyncio.Queue(
            maxsize=self.MAX_QUEUE_SIZE
        )

        self.workers = []
        self.started = False

    async def start(self):
        """
        Start queue workers.
        """

        if self.started:
            return

        self.started = True

        for worker_number in range(self.WORKERS):
            worker = asyncio.create_task(
                self._worker(worker_number)
            )

            self.workers.append(worker)

        logger.info(
            "Request Queue started | Workers: %s | Max queue: %s",
            self.WORKERS,
            self.MAX_QUEUE_SIZE,
        )

    async def stop(self):
        """
        Stop queue workers gracefully.
        """

        if not self.started:
            return

        self.started = False

        for worker in self.workers:
            worker.cancel()

        await asyncio.gather(
            *self.workers,
            return_exceptions=True,
        )

        self.workers.clear()

        logger.info(
            "Request Queue stopped."
        )

    async def submit(
        self,
        handler,
        *args,
        **kwargs,
    ):
        """
        Add a request to the queue.

        Returns:
            The handler's result.

        Raises:
            RuntimeError if the queue is full.
        """

        if not self.started:
            raise RuntimeError(
                "Request Queue is not running."
            )

        loop = asyncio.get_running_loop()

        future = loop.create_future()

        request = QueueRequest(
            handler=handler,
            args=args,
            kwargs=kwargs,
            future=future,
        )

        try:
            self.queue.put_nowait(request)

        except asyncio.QueueFull:
            logger.warning(
                "Request Queue is full. Request rejected."
            )

            raise RuntimeError(
                "NOVA is currently handling many requests. "
                "Please try again shortly."
            )

        position = self.queue.qsize()

        logger.info(
            "Request queued | Position: %s | Queue size: %s",
            position,
            self.queue.qsize(),
        )

        return await future

    async def _worker(self, worker_number):
        """
        Process requests one at a time.
        """

        logger.info(
            "Queue worker %s started.",
            worker_number,
        )

        while True:

            request = await self.queue.get()

            try:

                logger.info(
                    "Worker %s processing request | Remaining queue: %s",
                    worker_number,
                    self.queue.qsize(),
                )

                result = await request.handler(
                    *request.args,
                    **request.kwargs,
                )

                if not request.future.done():
                    request.future.set_result(
                        result
                    )

            except asyncio.CancelledError:

                if not request.future.done():
                    request.future.cancel()

                raise

            except Exception as error:

                logger.exception(
                    "Queue worker %s failed while processing request.",
                    worker_number,
                )

                if not request.future.done():
                    request.future.set_exception(
                        error
                    )

            finally:
                self.queue.task_done()


request_queue = RequestQueue()
