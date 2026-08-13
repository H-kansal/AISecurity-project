import asyncio
import re
import httpx
import logging
from langsmith import Client, traceable
from src.utils.retry import with_retry
from src.config.tz_llm import tz_call
from src.Exception import AIEthicsException
import sys


ls_client=None

def ls() -> Client:
    global ls_client
    if ls_client is None:
        ls_client = Client()
    return ls_client



def _parse_score(text: str) -> float:
    m = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*10", text, re.IGNORECASE)
    return round(float(m.group(1)) / 10.0, 2) if m else 0.5



@traceable(run_type="chain", name="eval:relevance")
async def eval_relevance(config, topic: str, report: str) -> dict:
    verdict = await tz_call(
        config,
        f"Rate how relevant this research report is to the topic '{topic}'.\n"
        f"Reply with exactly: SCORE: X/10 on the first line, then one sentence reason.\n\n"
        f"Report:\n{report[:config.eval_report_truncate]}",
        "research_summarize"
    )
    return {"key": "relevance", "score": _parse_score(verdict), "comment": verdict[:config.eval_comment_truncate]}



@traceable(run_type="chain", name="eval:completeness")
async def eval_completeness(config, report: str) -> dict:
    verdict = await tz_call(
        config,
        f"Does this research report contain all four required sections: "
        f"Executive Summary, Key Findings, Analysis, and Conclusion?\n"
        f"Reply with exactly: SCORE: X/10 on the first line, then one sentence reason.\n\n"
        f"Report:\n{report[:config.eval_report_truncate]}",
        "research_summarize"
    )
    return {"key": "completeness", "score": _parse_score(verdict), "comment": verdict[:config.eval_comment_truncate]}



@traceable(run_type="chain", name="eval:hallucination_risk")
async def eval_hallucination(config, topic: str, report: str) -> dict:
    verdict = await tz_call(
        config,
        f"Check this report on '{topic}' for hallucinations — fabricated statistics, "
        f"impossible dates, or claims that contradict well-known facts.\n"
        f"Score: 1/10 = zero hallucinations detected, 10/10 = many hallucinations.\n"
        f"Reply with exactly: SCORE: X/10 on the first line, then list any suspicious claims.\n\n"
        f"Report:\n{report[:config.eval_report_truncate]}",
        "research_summarize"
    )
    return {"key": "hallucination_risk", "score": _parse_score(verdict), "comment": verdict[:config.eval_comment_truncate]}



@traceable(run_type="chain", name="eval:overall_quality")
async def eval_quality(config, topic: str, report: str) -> dict:
    verdict = await tz_call(
        config,
        f"Rate the overall quality of this research report on '{topic}'.\n"
        f"Consider: depth of analysis, factual accuracy, writing clarity, logical structure, "
        f"and practical usefulness to a business analyst.\n"
        f"Reply with exactly: SCORE: X/10 on the first line, then two sentences explaining the rating.\n\n"
        f"Report:\n{report[:config.eval_report_truncate]}",
        "research_summarize"
    )
    return {"key": "overall_quality", "score": _parse_score(verdict), "comment": verdict[:config.eval_comment_truncate]}


@traceable(run_type="chain", name="evaluate-report")
async def evalute_report(config,topic,report,job_id):
    try:
        results=asyncio.gather(
            eval_relevance(config,topic,report),
            eval_completeness(config,report),
            eval_hallucination(config,topic,report),
            eval_quality(config,topic,report)
        )

        scores={r['key']:r['score'] for r in results}

        try:
           client=ls()
           dataset=client.read_dataset(dataset_name=config.langsmith_dataset)
        except Exception:
            dataset=client.create_dataset(
                config.langsmith_dataset,
                description="Research agent LLM-as-judge evaluation results"
            )
        
        client.create_example(
            inputs={"topic": topic},
            outputs={"report_preview": report[:400]},
            dataset_id=dataset.id,
            metadata={"job_id": job_id, **scores},
        )
        return scores

    except Exception as e:
        raise AIEthicsException(e,sys)