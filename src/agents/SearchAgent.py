from src.Exception import AIEthicsException
import sys
from src.config.tz_llm import tz_call
from src.utils.structuredOutput import AgentState

class SearchAgent:
    def __init__(self,config):
        self.config=config

    async def searchagent(self,topic,session_history):
        try:
            context_hist=""
            if session_history:
                recent=session_history[-4:]
                context_hist="\n\n Previous conversation history (use this to understand what the user already knows and what angle they care about):\n"
                context_hist+="\n".join(f"{m['role'].upper()}: {m['content']}" for m in recent)
            
            message=f"You are a research specialist. Find and list 5 key facts, recent developments, "
            f"and important details about: {topic}. Be thorough and specific."
            f"{context_hist}"
            return await tz_call(self.config,message,"research_summarize")
        except Exception as e:
            raise AIEthicsException(e,sys)
    
    async def searchNode(self,state:AgentState):
        try:
            result=await self.searchagent(state["topic"],state.get("session_history",[]))
            state["search_result"]=[result]
            return state
        except Exception as e:
            raise AIEthicsException(e,sys)