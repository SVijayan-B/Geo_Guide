from langgraph.graph import StateGraph
from typing import TypedDict, Any

from app.services.context_service import ContextService
from app.services.recommendation_service import RecommendationService
from app.agents.decision_agent import DecisionAgent
from app.agents.disruption_agent import DisruptionAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.chatbot_agent import ChatbotAgent
from app.services.vector_memory_service import VectorMemoryService


# 🧠 STATE
class TravelPipelineState(TypedDict):
    # Input
    trip: dict
    user_id: str

    # Intermediate
    context: dict
    memory: dict
    disruption: dict
    recommendations: list

    # Output
    decision: dict
    chatbot_response: str


# ------------------------
# NODES
# ------------------------

def context_node(state):
    service = ContextService()

    context = service.build_context(state["trip"])

    state["context"] = context
    return state


def memory_node(state):
    # Vector-db retrieval (semantic memory). Fallback to legacy in-memory on failure.
    history_str = ""
    docs = []
    try:
        vector_service = VectorMemoryService()
        docs = vector_service.query_similar(
            user_id=int(state["user_id"]),
            query_text=state["context"].get("text", ""),
            k=6,
        )
        if docs:
            history_str = "\n".join(
                [
                    f'{(d["metadata"].get("role") or "memory").upper()}: {d["document"]}'
                    for d in docs
                    if d.get("document")
                ]
            )
    except Exception:
        agent = MemoryAgent()
        history = agent.get(state["user_id"])
        history_str = str(history)

    state["memory"] = {"history_str": history_str, "docs": docs}
    return state


def disruption_node(state):
    agent = DisruptionAgent()
    disruption = agent.predict_delay(state["trip"], state["context"])
    state["disruption"] = disruption
    return state


def recommendation_node(state):
    service = RecommendationService()
    recs = service.recommend(
        state["context"],
        memory_docs=state["memory"].get("docs", []),
    )
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


def chatbot_node(state):
    # Final conversational synthesis. This is intentionally the last node.
    agent = ChatbotAgent()
    query = state["context"].get("text", "Plan my trip.")
    response = agent.chat(
        user_id=state["user_id"],
        query=query,
        context=state["context"],
        recommendations=state["recommendations"],
        disruption=state["disruption"],
        memory=state["memory"].get("history_str", ""),
    )
    state["chatbot_response"] = response
    return state


# ------------------------
# GRAPH
# ------------------------

def build_graph():
    graph = StateGraph(TravelPipelineState)

    graph.add_node("context", context_node)
    graph.add_node("memory", memory_node)
    graph.add_node("disruption", disruption_node)
    graph.add_node("recommendation", recommendation_node)
    graph.add_node("decision", decision_node)
    graph.add_node("chatbot", chatbot_node)

    graph.set_entry_point("context")
    graph.add_edge("context", "memory")
    graph.add_edge("memory", "disruption")
    graph.add_edge("disruption", "recommendation")
    graph.add_edge("recommendation", "decision")
    graph.add_edge("decision", "chatbot")

    return graph.compile()