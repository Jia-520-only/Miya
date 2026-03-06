import asyncio
import sys
sys.path.insert(0, '.')

from core.embedding_client import EmbeddingClient, EmbeddingProvider

async def test():
    client = EmbeddingClient(provider=EmbeddingProvider.SENTENCE_TRANSFORMERS)
    await client.initialize()
    v = await client.embed('hello')
    print(f'Success: {len(v)} dimensions')

asyncio.run(test())
