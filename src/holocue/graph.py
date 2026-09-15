"""A small LangGraph: semantic planning followed by deterministic grounding validation.
Session persistence and compare-and-swap commits live in Store, which is the only task-state authority.
"""
from typing import TypedDict,Any
from .models import Session,SceneSpec,UserMessage,Decision
from .state import validate_decision
from .provider import PlannerError

class GraphState(TypedDict,total=False):
    session: dict
    scene: dict
    message: dict
    decision: dict
    trace: dict

def build_graph(planner):
    from langgraph.graph import StateGraph,START,END
    async def plan(state):
        d,trace=await planner.decide(Session.model_validate(state['session']),
                                   SceneSpec.model_validate(state['scene']),
                                   UserMessage.model_validate(state['message']))
        return {'decision':d.model_dump(),'trace':trace}
    def ground(state):
        try:
            validate_decision(Decision.model_validate(state['decision']),SceneSpec.model_validate(state['scene']))
        except Exception as e:
            raise PlannerError(str(e),state.get('trace',{})) from e
        return {}
    g=StateGraph(GraphState)
    g.add_node('interpret',plan);g.add_node('ground',ground)
    g.add_edge(START,'interpret');g.add_edge('interpret','ground');g.add_edge('ground',END)
    return g.compile()

class GraphPlanner:
    def __init__(self,planner):self.graph=build_graph(planner);self.mode=planner.mode
    async def decide(self,s,scene,msg):
        result=await self.graph.ainvoke({'session':s.model_dump(),'scene':scene.model_dump(),'message':msg.model_dump()},
                                       {'recursion_limit':6})
        return Decision.model_validate(result['decision']),result['trace']
