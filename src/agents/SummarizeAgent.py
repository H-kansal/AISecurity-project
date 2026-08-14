from src.Exception import AIEthicsException
import sys
from src.config.tz_llm import tz_call
from src.utils.structuredOutput import AgentState
import logging
logger = logging.getLogger("SummarizeAgent")
class SummarizeAgent:
    def __init__(self,config):
        self.config=config

    async def summaryagent(self,search_results):
        try:
            combined_result="\n\n".join(search_results)
            return await tz_call(
                self.config,
                f"Summarize these research findings into clear, structured bullet points:\n\n{combined}",
                "research_summarize"
            )
        except Exception as e:
            raise AIEthicsException(e,sys)

    
    async def summaryNode(self,state:AgentState):
        try:
            logger.info(f"job_id={state['job_id']} event=summarize_node topic={state['topic'][:50]}")
            result=await self.summaryagent(state["search_result"])
            state["summary"]=[result]
            logger.info(f"job_id={state['job_id']} event=summarize_node completed topic={state['topic'][:50]}")
            return state
        except Exception as e:
            raise AIEthicsException(e,sys)