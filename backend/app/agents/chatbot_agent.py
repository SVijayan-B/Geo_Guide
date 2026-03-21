import os
from groq import Groq
from dotenv import load_dotenv
from app.agents.memory_agent import MemoryAgent
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from app.services.chat_memory_service import ChatMemoryService

load_dotenv()


class ChatbotAgent:

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
        self.memory = MemoryAgent()

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        # Keeps prompt compact and predictable.
        return "\n".join([f'{m["role"].upper()}: {m["content"]}' for m in history])

    def chat(
        self,
        user_id: int,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        recommendations: Optional[List[Dict[str, Any]]] = None,
        disruption: Optional[Dict[str, Any]] = None,
        session_id: Optional[int] = None,
        db: Optional[Session] = None,
        memory: Optional[str] = None,
    ):
        # 🧠 Memory precedence:
        # 1) explicit `memory` argument (graph/vector retrieval)
        # 2) DB-backed session memory
        # 3) legacy in-memory memory
        if memory is not None:
            history_str = memory
        elif session_id is not None and db is not None:
            history_service = ChatMemoryService()
            history = history_service.get_recent_messages(db, session_id=session_id)
            history_str = self._format_history(history)
        else:
            history = self.memory.get(user_id)
            history_str = str(history)

        prompt = f"""
        You are AURA Travel AI.

        USER QUERY:
        {query}

        CONTEXT:
        {context}

        RECOMMENDATIONS:
        {recommendations}

        DISRUPTION:
        {disruption}

        MEMORY (previous interactions):
        {history_str}

        TASK:
        - Answer conversationally
        - Use context + recommendations
        - Be helpful for travel planning
        - Suggest budget-friendly options
        """

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a smart travel assistant."},
                {"role": "user", "content": prompt}
            ]
        )

        output = response.choices[0].message.content

        # 💾 Save memory
        if session_id is not None and db is not None:
            ChatMemoryService().append_message(db, session_id=session_id, role="assistant", content=output)
        else:
            self.memory.save(user_id, {"query": query, "response": output})

        return output