import asyncio
from typing import Callable

from fastapi import Request


class StreamManager:
    def __init__(self):
        self._queues: set[asyncio.Queue] = set()

    def connect(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.add(queue)
        return queue

    def disconnect(self, queue: asyncio.Queue):
        self._queues.discard(queue)

    def broadcast(self, event: str, data: dict):
        dead = set()
        for queue in self._queues:
            try:
                queue.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                dead.add(queue)
        for queue in dead:
            self.disconnect(queue)


stream_manager = StreamManager()
