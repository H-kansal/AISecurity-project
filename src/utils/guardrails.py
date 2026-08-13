import boto3
import asyncio
from src.utils.retry import with_retry
from src.Exception import AIEthicsException
import sys

def apply_guardrail_sync(config, text: str, source: str) -> dict:
    try:
        client = boto3.client("bedrock-runtime", region_name=config.aws_region)
        return client.apply_guardrail(
            guardrailIdentifier=config.bedrock_guardrail_id,
            guardrailVersion=config.bedrock_guardrail_version,
            source=source,
            content=[{"text": {"text": text}}],
        )
    except Exception as e:
        raise AIEthicsException(e,sys)


async def validate_input(config,text):
    try:
        response=await with_retry(
            lambda: asyncio.to_thread(apply_guardrail_sync,config,text,"INPUT"),  # here we are not giving reference of apply_guardrail_sync because boto3 is synchoronous so it would block main thread and we are calling it inside asyncio.to_thread to make it async using a worker thread
            max_retry=config.llm_max_retries,
            delay=config.llm_retry_delay,
        )
        if response.get("action") == "GUARDRAIL_INTERVENED":
            return False, "Input blocked by safety guardrail."
        return True, ""
    except Exception as e:
        raise AIEthicsException(e,sys)


async def validate_output(config,text):
    try:
        response=await with_retry(
            lambda: asyncio.to_thread(apply_guardrail_sync,config,text,"OUTPUT"),
            max_retry=config.llm_max_retries,
            delay=config.llm_retry_delay,
        )
        if response.get("action") == "GUARDRAIL_INTERVENED":
            return False, "Output blocked by safety guardrail."
        return True, ""
    except Exception as e:
        raise AIEthicsException(e,sys)