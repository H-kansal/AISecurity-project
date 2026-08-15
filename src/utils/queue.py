import json
import uuid
import redis.asyncio as aioredis
import redis
import asyncio
from src.config.config import Config
from src.Exception import AIEthicsException
import sys
import logging


async def add_job(redis,topic,session_id,output_format,config):
    try:
        job_id=str(uuid.uuid4())
        await redis.xadd(config.stream_key,{
            "job_id": job_id,
            "topic": topic,
            "session_id": session_id,
            "output_format": output_format,
        })
        
        return job_id
    except Exception as e:
        raise AIEthicsException(e,sys)

async def set_result(redis,config,job_id,result):
    try:
        await redis.setex(f"result:{job_id}",config.result_ttl,json.dumps(result))
        
    except Exception as e:
        raise AIEthicsException(e,sys)


async def get_result(redis,config,job_id):
    try:
        data=await redis.get(f"result:{job_id}")
        return json.loads(data) if data else None
    except Exception as e:
        raise AIEthicsException(e,sys)



async def ensure_group(redis, config):    # this is to make sure that the consumer group is created so that each job is done by only one worker and also if the stream key is not available then it will create it
    try:
        await redis.xgroup_create(
            config.stream_key,
            config.consumer_group,
            id="0",
            mkstream=True
        )
        logging.info("Redis consumer group created")

    except Exception as e:
        if "BUSYGROUP" in str(e):
            logging.info("Redis consumer group already exists")
        else:
            logging.exception("Failed to create Redis consumer group")
            raise


async def consume_jobs(redis,config):
    try:
        messages=await redis.xreadgroup(
            config.consumer_group,
            config.consumer_name,
            {config.stream_key: ">"},
            count=1,
            block=1000,
        )              #interpret like this-> Worker consumer_name(worker-1), who belongs to the consumer_group(workers) group, wants the next job from the stream key(research:jobs)

        if not messages:
            return []
        
        jobs=[]
        for _,entries in messages:
            for msg_id,data in entries:
                jobs.append({"msg_id":msg_id,"data":data})

        return jobs
    except (redis.exceptions.TimeoutError, asyncio.TimeoutError):
        return []
    except Exception as e:
        raise AIEthicsException(e,sys)

async def ack_job(redis, config, msg_id):
    try:
        await redis.xack(config.stream_key, config.consumer_group, msg_id)
    except Exception as e:
        raise AIEthicsException(e,sys)