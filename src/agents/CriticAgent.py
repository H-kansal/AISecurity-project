from src.Exception import AIEthicsException
import sys
from src.config.tz_llm import tz_call
from src.utils.structuredOutput import AgentState
import logging
logger = logging.getLogger("CriticAgent")

class CriticAgent:
    def __init__(self,config):
        self.config=config

    async def criticagent(self,report):
        try:
            response= await tz_call(
                self.config,
                f"Review this report for factual consistency and logical coherence. "
                f"Reply with YES if it passes or NO with a brief reason:\n\n"
                f"{report[:self.config.agent_report_truncate]}",
                "research_summarize"
            )
            return response.strip().upper().startswith("YES")

        except Exception as e:
            raise AIEthicsException(e,sys)

    
    async def criticNode(self,state:AgentState):
        try:
            logger.info(f"job_id={state['job_id']} event=critic_node topic={state['topic'][:50]}")
            result=await self.criticagent(state["report"])
            state["verified"]=result
            logger.info(f"job_id={state['job_id']} event=critic_node completed topic={state['topic'][:50]}")
            return state
        except Exception as e:
            raise AIEthicsException(e,sys)
    