from __future__ import annotations

from typing import Any, Dict, Protocol


class AgentProtocol(Protocol):
    """Common contract for all first-party travel agents."""

    name: str

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent behavior and return a structured response."""
        ...
