import os
from groq import Groq
from dotenv import load_dotenv
from app.agents.memory_agent import MemoryAgent

load_dotenv()


class ChatbotAgent:

    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
        self.memory = MemoryAgent()

    def chat(self, user_id, query, context=None, recommendations=None, disruption=None):
        # 🧠 Get memory
        history = self.memory.get(user_id)

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
        {history}

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
        self.memory.save(user_id, {"query": query, "response": output})

        return output