from datetime import datetime


class ContextService:

    def get_time_of_day(self):
        current_hour = datetime.now().hour

        if 5 <= current_hour < 12:
            return "morning"
        elif 12 <= current_hour < 17:
            return "afternoon"
        elif 17 <= current_hour < 21:
            return "evening"
        else:
            return "night"

    def get_travel_phase(self, trip_status: str):
        if trip_status == "planned":
            return "pre_departure"
        elif trip_status == "ongoing":
            return "in_transit"
        elif trip_status == "completed":
            return "post_trip"
        return "unknown"

    def build_context(self, trip):
        return {
            "time_of_day": self.get_time_of_day(),
            "travel_phase": self.get_travel_phase(trip.status),
            "origin": trip.origin,
            "destination": trip.destination
        }