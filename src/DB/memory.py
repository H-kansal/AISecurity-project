import difflib
import json
import asyncio
from datetime import datetime
import redis.asyncio as aioredis
from sentence_transformers import SentenceTransformer
from src.Exception import AIEthicsException
from src.DB.pool import get_pool
import sys

model=SentenceTransformer("all-MiniLM-L6-v2")



# below are for short term memory
async def set_session(redis,config,role,content,sessionId):
    try:
        session_key=f"session:{sessionId}"
        await redis.rpush(session_key,json.dumps({"role":role,"content":content}))
        await redis.ltrim(session_key,-config.session_max_messages,-1)
        await redis.expire(session_key,config.session_ttl)
        
    except Exception as e:
        raise AIEthicsException(e,sys)


async def get_session(redis,config,sessionId):
    try:
        session_key=f"session:{sessionId}"
        message=await redis.lrange(session_key,0,-1)
        return [json.loads(m) for m in message]
    except Exception as e:
        raise AIEthicsException(e,sys)



# now we do things for long term memory(postgres)
async def ltm_db_configuration(config):
    try:
        pool=get_pool()
        async with pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")   # this is to install pgvector extension so that we can deal with this vector and all
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS reports (
                    id         TEXT PRIMARY KEY,
                    topic      TEXT NOT NULL,
                    report     TEXT NOT NULL,
                    embedding  vector(384),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )           
            """)
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS reports_embedding_idx
                ON reports USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = {config.ivfflat_lists})
            """)       # indexing using the embeddings for faster search
            await conn.execute("CREATE INDEX IF NOT EXISTS reports_topic_idx ON reports (topic)")   # indexing using topic
            await conn.execute("CREATE INDEX IF NOT EXISTS reports_created_idx ON reports (created_at DESC)")   # indexing using the time stamp
    except Exception as e:
        raise AIEthicsException(e,sys)

async def ltm_store(config,topic,report,report_id):
    try:
        embedding=await asyncio.to_thread(lambda: model.encode(topic).tolist())
        pool=get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO reports(id,topic,report,embedding,created_at) VALUES ($1, $2, $3, $4::vector, $5) ON CONFLICT (id) DO NOTHING 
                """,
                report_id,topic,report,str(embedding),datetime.utcnow()
            )
    except Exception as e:
        raise AIEthicsException(e,sys)



async def ltm_search(config,topic):
    try:
        embedding=await asyncio.to_thread(lambda: model.encode(topic).tolist())
        pool=get_pool()
        async with pool.acquire() as conn:
            row=await conn.fetchrow(
                """
                    SELECT id,topic,report,created_at,1-(embedding<=>$1) AS SIMILARITY    
                    FROM reports
                    WHERE created_at> NOW()-($2||'days')::INTERVAL
                    AND 1-(embedding <=> $1::vector)>$3
                    ORDER BY similarity DESC LIMIT 1
                """,    # <=> is the symbol to calculate the cosine distance, and for similarity 1-distance
                str(embedding),str(config.ltm_days),config.ltm_threshold
            )
            return dict(row) if row else None
    except Exception as e:
        raise AIEthicsException(e,sys)



async def ltm_related_search(config,topic):
    try:
        embedding=await asyncio.to_thread(lambda: model.encode(topic).tolist())
        pool=get_pool()
        async with pool.acquire() as conn:
            row=await conn.fetchrow(
                """
                    SELECT report FROM reports where 1-(embedding <=> $1::vector) BETWEEN 0.5 AND $2 ORDER BY created_at DESC LIMIT 1
                """,
                str(embedding), config.ltm_threshold - 0.01
            )
            return row["report"] if row else None

    except Exception as e:
        raise AIEthicsException(e,sys)


async def ltm_report_diff(config,topic):
    try:
        pool=get_pool()
        async with pool.acquire() as conn:
            rows=await conn.fetch(
                """
                    SELECT report,created_at FROM reports WHERE topic=$1 ORDER BY created_at DESC LIMIT 2
                """,
                topic
            )
            if len(rows)<2:
                return None
            
            old=rows[1]["report"]
            new=rows[0]["report"]
            
            old_lines=old.splitlines(keepends=True)   # split line wise but preserve the \n at end of line
            new_lines=new.splitlines(keepends=True)
            
            diff_lines=list(difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"previous ({rows[1]['created_at'].date()})",
                tofile=f"latest ({rows[0]['created_at'].date()})",
                lineterm="",
            ))
            return "\n".join(diff_lines[:config.ltm_diff_limit*10]) or "No significant changes detected."
            
    except Exception as e:
        raise AIEthicsException(e,sys)
