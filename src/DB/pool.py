import asyncpg
from src.Exception import AIEthicsException
import sys


pool=None

async def init_pool(config):
    try:
        global pool
        pool=await asyncpg.create_pool(
            config.database_url,
            min_size=config.db_pool_min,
            max_size=config.db_pool_max,
        )
    except Exception as e:
        raise AIEthicsException(e,sys)

async def close_pool():
    try:
        global pool
        await pool.close()
        pool=None
    except Exception as e:
        raise AIEthicsException(e,sys)

def get_pool():
    if pool is not None:
        return pool
    raise AIEthicsException("pool not initialized",sys)
