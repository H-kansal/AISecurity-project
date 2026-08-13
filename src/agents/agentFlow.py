from src.Exception import AIEthicsException
import sys
from src.agents.SearchAgent import SearchAgent
from src.agents.SummarizeAgent import SummarizeAgent
from src.agents.WriterAgent import WriterAgent
from src.agents.CriticAgent import CriticAgent
from src.utils.structuredOutput import AgentState
from langgraph.graph import StateGraph,END,START


class Agent:
    def __init__(self,config):
        self.config=config
        self.search_agent=SearchAgent(config)
        self.summarize_agent=SummarizeAgent(config)
        self.writer_agent=WriterAgent(config)
        self.critic_agent=CriticAgent(config)
    
    def routeGraph(self,state:AgentState)->str:
        try:
            if not state["verified"] and state["iteration"]<self.config.agent_max_iterations:
                return "search_node"
            return END
        except Exception as e:
            raise AIEthicsException(e,sys)
    

    def createGraph(self):
        try:
            workflow=StateGraph(AgentState)
            workflow.add_node("search_node",self.search_agent.searchNode)
            workflow.add_node("summarize_node",self.summarize_agent.summaryNode)
            workflow.add_node("writer_node",self.writer_agent.writerNode)
            workflow.add_node("critic_node",self.critic_agent.criticNode)
            
            workflow.add_edge(START,"search_node")
            workflow.add_edge("search_node","summarize_node")
            workflow.add_edge("summarize_node","writer_node")
            workflow.add_edge("writer_node","critic_node")
            workflow.add_conditional_edges(
                "critic_node",
                self.routeGraph,
                {END:END,
                "search_node":"search_node"}
            )
            
            return workflow.compile()
        except Exception as e:
            raise AIEthicsException(e,sys)

