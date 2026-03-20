from datetime import datetime
from sentence_transformers import SentenceTransformer


class ContextService:

    def __init__(self):
        # Pretrained embedding model
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def get_time_of_day(self):
        hour = datetime.now().hour

        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"

    def get_travel_phase(self, status):
        if status == "planned":
            return "pre_departure"
        elif status == "ongoing":
            return "in_transit"
        return "unknown"

    def build_context(self, trip):
    # 🔥 HANDLE BOTH dict + object
        if isinstance(trip, dict):
            origin = trip.get("origin")
            destination = trip.get("destination")
            status = trip.get("status")
        else:
            origin = trip.origin
            destination = trip.destination
            status = trip.status

        time_of_day = self.get_time_of_day()
        phase = self.get_travel_phase(status)

        context_text = f"""
        User is traveling from {origin} to {destination}.
        It is {time_of_day}.
        Travel phase is {phase}.
        """

        embedding = self.model.encode(context_text).tolist()

        return {
            "text": context_text,
            "embedding": embedding,
            "time_of_day": time_of_day,
            "travel_phase": phase
        }