from src.Exception import AIEthicsException
import sys
from src.config.tz_llm import tz_call
from src.utils.structuredOutput import AgentState

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
            result=await self.summaryagent(state["search_result"])
            state["summary"]=[result]
            return state
        except Exception as e:
            raise AIEthicsException(e,sys)