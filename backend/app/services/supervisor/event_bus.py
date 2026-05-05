import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class PipelineEventBus:
    """
    In-memory event bus for real-time SSE streaming.

    Each complaint gets its own asyncio.Queue.
    Pipeline nodes publish events as they complete.
    SSE endpoint reads from the queue and streams to frontend.

    Why asyncio.Queue: thread-safe, native async, zero dependencies.
    For Production: replace with Redis pub/sub for multi-worker support.
    """

    def __init__(self):
        # complaint_id → asyncio.Queue
        self._queues: dict[str, asyncio.Queue] = {}

    def create_queue(self, complaint_id: str) -> None:
        """Create a queue for a new complaint pipeline run."""
        self._queues[complaint_id] = asyncio.Queue()

    def has_queue(self, complaint_id: str) -> bool:
        """Return True only if a pipeline is actively running for this complaint."""
        return complaint_id in self._queues

    async def publish(self, complaint_id: str, event: dict) -> None:
        """
        Publish an event to a complaint's queue.
        Called by each LangGraph node when it starts or completes.
        """
        if complaint_id in self._queues:
            et = event.get("event", "?")
            if et in ("pipeline_complete", "pipeline_error"):
                logger.info("[event_bus] publish complaint_id=%s event=%s", complaint_id, et)
            else:
                logger.debug("[event_bus] publish complaint_id=%s event=%s", complaint_id, et)
            await self._queues[complaint_id].put(event)
        else:
            logger.warning(
                "[event_bus] publish dropped — no queue for complaint_id=%s event=%s",
                complaint_id,
                event.get("event"),
            )

    async def subscribe(self, complaint_id: str):
        """
        Async generator that yields events for an SSE stream.
        Yields None sentinel to signal stream end.

        Waits for POST /pipeline/run to create the queue so GET /stream can be
        opened in the same moment without missing events.
        """
        deadline = time.monotonic() + 120.0
        while complaint_id not in self._queues:
            await asyncio.sleep(0.05)
            if time.monotonic() > deadline:
                logger.warning(
                    "[event_bus] SSE subscribe timeout — no queue for complaint_id=%s",
                    complaint_id,
                )
                yield {
                    "event": "pipeline_error",
                    "complaint_id": complaint_id,
                    "error": (
                        "Timed out waiting for the pipeline to start. "
                        "Use POST /api/v1/pipeline/run/{id} first, then connect to this stream. "
                        "If you already did, check the backend terminal for errors."
                    ),
                }
                return

        queue = self._queues.get(complaint_id)
        if not queue:
            return

        logger.info("[event_bus] SSE subscribed complaint_id=%s", complaint_id)

        try:
            while True:
                event = await queue.get()
                if event is None:  # sentinel — pipeline complete
                    break
                yield event
        finally:
            # Clean up the queue only after the frontend has finished reading
            # This fixes the race condition where the pipeline finishes before the frontend connects.
            if complaint_id in self._queues:
                del self._queues[complaint_id]

    async def close(self, complaint_id: str) -> None:
        """
        Signal the SSE stream to close by putting a None sentinel.
        Call this when the pipeline finishes.
        """
        if complaint_id in self._queues:
            logger.info("[event_bus] close stream complaint_id=%s", complaint_id)
            await self._queues[complaint_id].put(None)


# Module-level singleton — imported by all agents and the SSE route
event_bus = PipelineEventBus()