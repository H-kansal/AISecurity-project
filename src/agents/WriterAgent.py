from src.Exception import AIEthicsException
import sys
from src.config.tz_llm import tz_call
from src.utils.structuredOutput import AgentState
import logging
logger = logging.getLogger("WriterAgent")
class WriterAgent:
    def __init__(self,config):
        self.config=config
    
    async def writeragent(self,topic,summaries,ltm_context):
        try:
            combined="\n\n".join(summaries)
            ltm_section = ""
            if ltm_context:
                ltm_section = (
                    f"\n\nPREVIOUS RESEARCH ON A RELATED TOPIC (use this as reference — "
                    f"build on it, correct outdated information, and highlight what has changed):\n"
                    f"{ltm_context[:2000]}"
                )
            
            return await tz_call(
                self.config,
                f"Write a comprehensive, well-structured research report on: '{topic}'\n\n"
                f"Current research findings:\n{combined}"
                f"{ltm_section}\n\n"
                f"Include: Executive Summary, Key Findings, Analysis, and Conclusion.",
                "report_write",
            )
        except Exception as e:
            raise AIEthicsException(e,sys)

    async def writerNode(self,state:AgentState):
        try:
            logger.info(f"job_id={state['job_id']} event=writer_node topic={state['topic'][:50]}")
            result=await self.writeragent(state["topic"],state.get("summary",[]),state.get("ltm_context",""))
            state["report"]=result
            state["iteration"]=state.get("iteration",0)+1
            logger.info(f"job_id={state['job_id']} event=writer_node completed topic={state['topic'][:50]}")
            return state
        except Exception as e:
            raise AIEthicsException(e,sys)