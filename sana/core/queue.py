import asyncio
from typing import Any
from collections.abc import AsyncIterator

class StreamingQueue:
    def __init__(self) -> None:
        self.finished: bool = False
        self.queue = asyncio.Queue()

    async def put(self, item: Any) -> None:
        await self.queue.put(item)

    async def finish(self) -> None:
        self.finished = True
        await self.queue.put(None)

    async def stream(self) -> AsyncIterator[Any]:
        while True:
            item = await self.queue.get()
            if item is None and self.finished:
                break
            yield item
