from src.Exception import AIEthicsException
import sys
from src.config.config import Config
from fastapi import Request,HTTPException,FastAPI,Depends
from contextlib import asynccontextmanager
from src.utils.structuredOutput import AgentState
import uuid
import redis.asyncio as aioredis
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import traceback
from datetime import datetime
from fastapi.responses import Response, FileResponse

import logging
from src.DB.cache import get_cache,set_cache
from src.DB.memory import set_session,get_session
from src.DB.memory import ltm_store,ltm_search,ltm_related_search,ltm_report_diff
from src.utils.guardrails import validate_output,validate_input
from src.utils.queue import ack_job,set_result,ensure_group,consume_jobs,add_job,get_result
from src.utils.output import generate_pdf,generate_json_report
from src.DB.pool import init_pool,close_pool
from src.agents.agentFlow import Agent
from src.Evaluation import evalute_report

logger = logging.getLogger("worker")


config=Config()
redis_client=None
graph=None


async def rate_limit(request:Request):
    try:
        client_ip=request.client.host # getting the client ip
        key=f"ratelimit:{client_ip}"
        count=await redis_client.incr(key)
        if count==1:
            redis_client.expire(key,config.rate_limit_window)
        if count>config.rate_limit_requests:
            raise HTTPException(status_code=429,detail="Rate limit exceeded. Try again later.")
    except Exception as e:
        raise AIEthicsException(e,sys)



async def process_job(data,msg_id):
    try:
        topic=data['topic']
        session_id=data['session_id']
        output_format=data['output_format']
        job_id=data['job_id']
        logger.info(f"job_id={job_id} event=received msg_id={msg_id} topic={topic[:50]}")

        cache=await get_cache(redis,config,topic)
        if cache:  # cache hit
            logger.info(f"job_id={job_id} event=cache_hit")
            await set_session(redis_client,config,"assistant",cache,session_id)
            await ltm_store(config,topic,cache,str(uuid.uuid4()))
        else:
            logger.info(f"job_id={job_id} event=cache_miss")
            ltm_search_result=ltm_search(config,topic)
            if ltm_search_result:     # ltm hit
                logger.info(f"job_id={job_id} event=ltm_hit")
                await set_session(redis_client,config,"assistant",ltm_search_result['report'],session_id)
                await ltm_store(config,topic,ltm_search_result['report'],str(uuid.uuid4()))
            else:
                logger.info(f"job_id={job_id} event=ltm_miss")
                session_history=get_session(redis_client,config,session_id)
                ltm_context=ltm_related_search(config,topic)
                logger.info(f"job_id={job_id} event=generating_report")

                state:AgentState={
                    "topic":topic,
                    "session_id":session_id,
                    "session_history":session_history,
                    "ltm_context":ltm_context,
                    "search_result": [],
                    "summary": [],
                    "report": "",
                    "verified": False,
                    "iteration": 0
                }
                 
                result=await graph.ainvoke(state)
                logger.info(f"job_id={job_id} event=report_generated")
                report=result['report']
                ok,reason=validate_output(config,report)
                if not ok:
                    logger.info(f"job_id={job_id} event=report_blocked reason={reason}")
                    await set_result(redis_client,config,job_id,{"status":"blocked","error":reason})
                    await ack_job(redis_client,config,msg_id)
                    return
                logger.info(f"job_id={job_id} event=report_verified")
                await set_session(redis_client,config,"assistant",report[:config.agent_report_truncate],session_id)
                await set_cache(redis_client,topic,report,config)
                await ltm_store(config,topic,report,str(uuid.uuid4()))
                logger.info(f"job_id={job_id} event=evaluating_report")
                scores= await evalute_report(config,topic,report,job_id)
                logger.info(f"job_id={job_id} event=report_evaluated")
                result={"status":"completed","topic":topic,"report":report,"scores":scores}
                if output_format == "pdf":
                    logger.info(f"job_id={job_id} event=generating_pdf")
                    pdf_bytes = generate_pdf(topic, report)
                    result["pdf_base64"] = __import__("base64").b64encode(pdf_bytes).decode()
                    logger.info(f"job_id={job_id} event=pdf_generated")
                elif output_format == "json":
                    logger.info(f"job_id={job_id} event=generating_json")
                    result["structured"] = generate_json_report(topic, report, job_id, datetime.utcnow())
                    logger.info(f"job_id={job_id} event=json_generated")
                
                await set_result(redis_client,config,job_id,result)
                logger.info(f"job_id={job_id} event=report_completed")
                
    except Exception as e:
        raise AIEthicsException(e,sys)
    finally:
        await ack_job(redis_client,config,msg_id)

async def _worker_loop():
    logger.info("========== WORKER STARTING ==========")
    try:
        await ensure_group(redis_client, config)
        logger.info("Redis consumer group initialized successfully")
    except Exception:
        logger.exception("FAILED TO INITIALIZE REDIS CONSUMER GROUP")
        raise
    logger.info("Worker is now waiting for jobs...")
    while True:
        try:
            logger.info("Waiting for Redis jobs...")
            jobs = await consume_jobs(redis_client, config)
            logger.info(f"Received {len(jobs)} job(s) from Redis")
            for job in jobs:
                logger.info(
                    f"Dispatching job: {job['data']['job_id']}, "
                    f"message_id={job['msg_id']}"
                )
                asyncio.create_task(
                    _process_job(job["data"], job["msg_id"])
                )
        except Exception:
            logger.exception("ERROR INSIDE WORKER LOOP")
            await asyncio.sleep(1)



@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_client, graph
    logger.info("Application startup started")
    redis_client = await aioredis.from_url(
        config.redis_url,
        decode_responses=True
    )
    logger.info("Redis client initialized")
    await init_pool(config)
    logger.info("Database pool initialized")
    await db_migrate(config)
    logger.info("Database migration completed")
    graph = build_graph(config)
    logger.info("Agent graph built")
    app.state.config = config
    asyncio.create_task(_worker_loop())
    logger.info("Worker task created")
    yield
    await redis_client.aclose()
    await close_pool()



app=FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

class RequestClass(BaseModel):
    topic:str
    output_format:str
    session_id:str


@app.get("/health")
async def health():
    try:
        await redis_client.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {
        "status": "ok" if redis_ok else "degraded",
        "redis": "ok" if redis_ok else "error",
    }



@app.post("/research", dependencies=[Depends(rate_limit)])
async def start_research(req: RequestClass):
    ok, reason = await validate_input(config, req.topic)
    if not ok:
        raise HTTPException(status_code=400, detail=reason)
    session_id = req.session_id or str(uuid.uuid4())
    await set_session(redis_client,config,"user",req.topic,session_id)
    job_id = await add_job(redis_client,req.topic,session_id,req.output_format,config)
    return {"job_id": job_id, "session_id": session_id}


@app.get("/result/{job_id}")
async def get_job_result(job_id: str):
    result = await get_result(redis_client,config,job_id)
    if result is None:
        return {"status": "pending"}
    return result


@app.get("/session/{session_id}")
async def get_curr_session(session_id: str):
    messages = await get_session(redis_client,config,session_id)
    return {"session_id": session_id, "messages": messages}


@app.get("/diff/{topic}")
async def report_diff(topic: str):
    diff = await ltm_report_diff(config,topic)
    return {"topic": topic, "diff": diff or "No previous report found."}


@app.get("/result/{job_id}/pdf")
async def download_pdf(job_id: str):
    result = await get_result(redis_client,config,job_id)
    if not result or result.get("status") != "done":
        raise HTTPException(status_code=404, detail="Report not ready")
    pdf_bytes = generate_pdf(result.get("topic", "Report"), result["report"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={job_id}.pdf"},
    )


@app.get("/stats")
async def stats():
    info = await redis_client.info()
    keys = await redis_client.dbsize()
    cache_keys = len([k async for k in redis_client.scan_iter("semantic:*")])
    session_keys = len([k async for k in redis_client.scan_iter("session:*")])
    return {
        "redis": {
            "total_keys": keys,
            "cache_entries": cache_keys,
            "active_sessions": session_keys,
            "memory_used_mb": round(info["used_memory"] / 1024 / 1024, 2),
            "connected_clients": info["connected_clients"],
            "uptime_hours": round(info["uptime_in_seconds"] / 3600, 1),
        },
        "tensorzero_url": config.tensorzero_url,
        "guardrail_id": config.bedrock_guardrail_id,
    }


@app.get("/evaluate/{job_id}")
async def evaluation_result(job_id:str):
    result=await get_result(redis_client,config,job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not ready")
    scores=await evalute_report(config,result['topic'],result['report'],job_id)
    result['scores']=scores
    return result