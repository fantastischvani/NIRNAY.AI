from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseAgent(ABC):

    @abstractmethod
    async def run(self, query: str, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Every agent MUST implement this method.
        Must return:
        {
            "agent": "<AgentName>",
            "output": {...}
        }
        """
        pass
