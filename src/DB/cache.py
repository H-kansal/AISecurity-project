import json
import numpy as np
import redis.asyncio as aioredis
from sentence_transformers import SentenceTransformer
from src.Exception import AIEthicsException
import sys

model=SentenceTransformer("all-MiniLM-L6-v2")
EMBEDDING_PREFIX="embeded"      # prefix used to identify the keys in redis that are storing embeddings of query
ANSWER_PREFIX="answer"       # prefix used to identify the keys in redis that are storing answers of a the same query



def cosine_similarity(a: list, b: list) -> float:
    va, vb = np.array(a), np.array(b)
    return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))


def embed(text: str) -> list:
    return model.encode(text).tolist()

async def get_cache(redis,config,query):
    try:
        query_emb=embed(query)
        async for key in redis.scan_iter(f"{EMBEDDING_PREFIX}*"):
            stored_emb=json.loads(await redis.get(key))   # json.loads so that the string is converted to list
            if cosine_similarity(query_emb,stored_emb)>=config.cache_similarity_threshold:
                answer_key=key.replace(EMBEDDING_PREFIX,ANSWER_PREFIX)
                return await redis.get(answer_key)
    except Exception as e:
        raise AIEthicsException(e,sys)
    
    return None

async def set_cache(redis,query,answer,config):
    try:
        queryHash=abs(hash(query))
        query_emb=embed(query)
        await redis.setex(f"{ANSWER_PREFIX}{queryHash}",config.cache_ttl,answer)
        await redis.setex(f"{EMBEDDING_PREFIX}{queryHash}",config.cache_ttl,json.dumps(query_emb))   # here while storing in redis we use json.dumps because so that redis can store list as string because redis can't understand list and all
    except Exception as e:
        raise AIEthicsException(e,sys)