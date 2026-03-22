from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from app.agents.Booking_agent import BookingAgent
from app.agents.chatbot_agent import ChatbotAgent
from app.agents.deal_agent import DealAgent
from app.agents.decision_agent import DecisionAgent
from app.agents.disruption_agent import DisruptionAgent
from app.agents.place_agent import PlaceAgent
from app.agents.price_agent import PriceAgent
from app.agents.vision_agent import VisionAgent


@dataclass
class AgentEntry:
    name: str
    factory: Callable[[], Any]
    description: str


class AgentRegistry:
    """Lightweight registry used by orchestrators and background workflows."""

    def __init__(self) -> None:
        self._entries: Dict[str, AgentEntry] = {}

    def register(self, *, name: str, factory: Callable[[], Any], description: str) -> None:
        self._entries[name] = AgentEntry(name=name, factory=factory, description=description)

    def get(self, name: str) -> Any:
        if name not in self._entries:
            raise KeyError(f"Agent '{name}' is not registered")
        return self._entries[name].factory()

    def list(self) -> list[dict[str, str]]:
        return [
            {"name": entry.name, "description": entry.description}
            for entry in sorted(self._entries.values(), key=lambda item: item.name)
        ]


def build_default_registry() -> AgentRegistry:
    registry = AgentRegistry()
    registry.register(name="chatbot", factory=ChatbotAgent, description="Conversational synthesis agent")
    registry.register(name="vision", factory=VisionAgent, description="Image understanding agent")
    registry.register(name="place", factory=PlaceAgent, description="Place knowledge agent")
    registry.register(name="price", factory=PriceAgent, description="Price estimation agent")
    registry.register(name="deal", factory=DealAgent, description="Deal search agent")
    registry.register(name="disruption", factory=DisruptionAgent, description="Disruption prediction agent")
    registry.register(name="decision", factory=DecisionAgent, description="Decision policy agent")
    registry.register(name="booking", factory=BookingAgent, description="Rebooking and booking suggestion agent")
    return registry
