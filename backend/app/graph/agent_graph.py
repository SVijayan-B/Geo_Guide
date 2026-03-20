from langgraph.graph import StateGraph
from typing import TypedDict
from types import SimpleNamespace
from app.services.context_service import ContextService
from app.services.recommendation_service import RecommendationService
from app.agents.decision_agent import DecisionAgent
from app.agents.disruption_agent import DisruptionAgent


# 🧠 STATE
class AgentState(TypedDict):
    trip: dict
    context: dict
    disruption: dict
    recommendations: list
    decision: dict


# ------------------------
# NODES
# ------------------------

def context_node(state):
    service = ContextService()

    context = service.build_context(state["trip"])

    state["context"] = context
    return state

def disruption_node(state):
    agent = DisruptionAgent()
    disruption = agent.predict_delay(state["trip"], state["context"])
    state["disruption"] = disruption
    return state


def recommendation_node(state):
    service = RecommendationService()
    recs = service.recommend(state["context"])
    state["recommendations"] = recs
    return state


def decision_node(state):
    agent = DecisionAgent()
    decision = agent.make_decision(
        state["context"]["text"],
        state["recommendations"],
        state["disruption"]
    )
    state["decision"] = decision
    return state


# ------------------------
# GRAPH
# ------------------------

def build_graph():
    graph = StateGraph(AgentState)
    
    graph.add_node("context", context_node)
    graph.add_node("disruption", disruption_node)
    graph.add_node("recommendation", recommendation_node)
    graph.add_node("decision", decision_node)

    graph.set_entry_point("context")

    graph.add_edge("context", "disruption")
    graph.add_edge("disruption", "recommendation")
    graph.add_edge("recommendation", "decision")

    return graph.compile()