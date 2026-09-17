import asyncio
from valuetravel.config import get_settings
from valuetravel.search import Search
from valuetravel.managed import MemoryService
from valuetravel.data import MEMBERS


async def main():
    settings = get_settings()
    s = Search(settings)
    print("Catalog packages indexed:", await asyncio.to_thread(s.seed))
    await asyncio.to_thread(s.router)
    memory = MemoryService(settings)
    for m in MEMBERS:
        records = [
            {
                "id": f"{m['member_id']}-seed-{i}",
                "owner_id": m["member_id"],
                "text": text,
                "memory_type": "semantic",
                "topics": ["travel", "demo-seed"],
            }
            for i, text in enumerate(m["preferences"])
        ]
        result = await asyncio.to_thread(
            memory.reset_long_term, m["member_id"], records
        )
        print(m["member_id"], result)
    await memory.close()


if __name__ == "__main__":
    asyncio.run(main())
