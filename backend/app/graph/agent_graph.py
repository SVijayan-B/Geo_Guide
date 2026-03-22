from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import StateGraph

from app.agents.chatbot_agent import ChatbotAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.disruption_agent import DisruptionAgent
from app.services.context_service import ContextService
from app.services.recommendation_service import RecommendationService
from app.services.vector_memory_service import VectorMemoryService


class PipelineInput(TypedDict, total=False):
    user_id: int
    trip: dict[str, Any]
    query: str
    image_path: str
    city: str
    mode: str
    budget: float
    traveler_type: str
    days: int


class TravelPipelineState(TypedDict):
    input: PipelineInput
    context: dict[str, Any]
    memory: dict[str, Any]
    disruption: dict[str, Any]
    recommendation: dict[str, Any]
    decision: dict[str, Any]
    output: dict[str, Any]


def _normalize_trip(raw_trip: Any) -> dict[str, Any] | None:
    if raw_trip is None:
        return None
    if isinstance(raw_trip, dict):
        return {
            "id": raw_trip.get("id"),
            "user_id": raw_trip.get("user_id"),
            "origin": raw_trip.get("origin"),
            "destination": raw_trip.get("destination"),
            "status": raw_trip.get("status", "planned"),
        }
    return {
        "id": getattr(raw_trip, "id", None),
        "user_id": getattr(raw_trip, "user_id", None),
        "origin": getattr(raw_trip, "origin", None),
        "destination": getattr(raw_trip, "destination", None),
        "status": getattr(raw_trip, "status", "planned"),
    }


def _safe_user_id(state: TravelPipelineState) -> int:
    raw = (state.get("input") or {}).get("user_id")
    try:
        return int(raw)
    except Exception:
        return 0


def context_node(state: TravelPipelineState) -> TravelPipelineState:
    svc = ContextService()
    normalized_input = dict(state.get("input") or {})
    trip = _normalize_trip(normalized_input.get("trip"))

    if trip:
        context_payload = svc.build_context(trip)
        context_payload["origin"] = trip.get("origin")
        context_payload["destination"] = trip.get("destination")
    else:
        city = normalized_input.get("city") or "destination"
        query = normalized_input.get("query") or f"Travel guidance for {city}"
        text = (
            f"User is asking: {query}. "
            f"Current city context: {city}. "
            f"Travel phase is conversational assistance."
        )
        context_payload = {
            "text": text,
            "embedding": svc.model.encode(text).tolist(),
            "time_of_day": svc.get_time_of_day(),
            "travel_phase": "conversation",
            "origin": None,
            "destination": city,
        }

    return {
        **state,
        "input": {**normalized_input, "trip": trip},
        "context": context_payload,
    }


def memory_node(state: TravelPipelineState) -> TravelPipelineState:
    docs: list[dict[str, Any]] = []
    history_str = ""

    try:
        query_text = (state.get("context") or {}).get("text", "")
        user_id = _safe_user_id(state)
        docs = VectorMemoryService().query_similar(user_id=user_id, query_text=query_text, k=6)
        history_str = "\n".join(
            [
                f"{(doc.get('metadata', {}).get('role') or 'memory').upper()}: {doc.get('document', '')}"
                for doc in docs
                if doc.get("document")
            ]
        )
    except Exception:
        docs = []
        history_str = ""

    return {
        **state,
        "memory": {
            "documents": docs,
            "history": history_str,
            "count": len(docs),
        },
    }


def disruption_node(state: TravelPipelineState) -> TravelPipelineState:
    trip = (state.get("input") or {}).get("trip")
    context = state.get("context") or {}

    if not trip:
        disruption = {
            "delay_probability": 0.0,
            "risk_level": "low",
            "reason": "No active trip provided; disruption analysis skipped.",
        }
    else:
        disruption = DisruptionAgent().predict_delay(trip, context)

    return {**state, "disruption": disruption}


def recommendation_node(state: TravelPipelineState) -> TravelPipelineState:
    input_payload = state.get("input") or {}
    trip = input_payload.get("trip") or {}
    context = state.get("context") or {}

    destination = trip.get("destination") or input_payload.get("city") or context.get("destination")
    mode = input_payload.get("mode") or "pre_trip_plan"

    recommendation = RecommendationService().recommend(
        context=context,
        memory_docs=(state.get("memory") or {}).get("documents", []),
        mode=mode,
        origin=trip.get("origin"),
        destination=destination,
        days=int(input_payload.get("days") or 3),
        budget=input_payload.get("budget"),
        traveler_type=input_payload.get("traveler_type") or "foodie",
        image_context=input_payload.get("query"),
    )

    return {**state, "recommendation": recommendation}


def decision_node(state: TravelPipelineState) -> TravelPipelineState:
    context_text = (state.get("context") or {}).get("text", "")
    recommendation_payload = state.get("recommendation") or {}
    disruption = state.get("disruption") or {}

    decision = DecisionAgent().make_decision(
        context_text,
        recommendation_payload.get("recommendations", []),
        disruption,
    )
    return {**state, "decision": decision}


def chatbot_node(state: TravelPipelineState) -> TravelPipelineState:
    input_payload = state.get("input") or {}
    context = state.get("context") or {}
    recommendation_payload = state.get("recommendation") or {}

    query = input_payload.get("query") or context.get("text") or "Help me plan my trip"

    response_text = ChatbotAgent().chat(
        user_id=_safe_user_id(state),
        query=query,
        context=context,
        recommendations=recommendation_payload.get("recommendations", []),
        disruption=state.get("disruption") or {},
        memory=(state.get("memory") or {}).get("history", ""),
    )

    output_payload = {
        "chat_data": {
            "response": response_text,
            "recommendations": recommendation_payload.get("recommendations", []),
            "plans": recommendation_payload.get("plans", []),
            "mode": recommendation_payload.get("mode"),
            "alternate_flight_message": recommendation_payload.get("alternate_flight_message"),
            "explanation": (state.get("decision") or {}).get("reason"),
            "price_comparison": None,
            "context_awareness": {
                "memory_hits": (state.get("memory") or {}).get("count", 0),
                "risk_level": (state.get("disruption") or {}).get("risk_level"),
            },
        },
        "map_data": {"routes": []},
        "decision": state.get("decision") or {},
    }

    return {**state, "output": output_payload}


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
