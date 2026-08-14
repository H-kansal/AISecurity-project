import httpx
from src.Exception import AIEthicsException
import sys
from src.utils.retry import with_retry


async def tz_llm_call(config,message,functionName):
    try:
        async with httpx.AsyncClient(timeout=120) as client:         # here we can also send requst by httpx.post but we are forming client so that for each request we don't have to make connection everytime
            response=await client.post(
                f"{config.tensorzero_url}/inference",
                json={
                    "function_name": functionName,
                    "input": {"messages": [{"role": "user", "content": message}]},
                },
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"]
    except Exception as e:
        raise AIEthicsException(e,sys)



async def tz_call(config,message,functionName):
    try:
        return await with_retry(
            lambda: tz_llm_call(config,message,functionName),
            max_retry=config.llm_max_retries,
            delay=config.llm_retry_delay
        )
    except Exception as e:
        raise AIEthicsException(e,sys)