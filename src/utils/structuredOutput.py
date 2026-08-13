from typing import TypedDict,List,Dict


class AgentState(TypedDict):
    topic:str
    search_result:List[str]
    summary:List[str]
    report:str
    iteration:int
    session_id:int
    session_history:List[Dict]
    ltm_context:str
    verified:bool
    error:str
