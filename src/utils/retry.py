from src.Exception import AIEthicsException
from src.Logger import logging
import sys
import asyncio

async def with_retry(funCall,max_retry=3,delay=1.0,backoff=2.0):
    last_exception=None
    wait=delay
    for i in range(1,max_retry+1):
        try:
            return await funCall()
        except Exception as e:
            last_exception=e
            logging.warning(f"Attempt {i}/{max_retry} failed:")
            if i<max_retry:
                logging.info(f"Retrying in {wait:.1f}s")
                await asyncio.sleep(wait)    # here worker can perform another tasks after this task sleep that's why we use await asyncio.sleep() not time.sleep()
                wait*=backoff
    raise AIEthicsException(last_exception,sys)
            
            