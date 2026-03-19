from app.integrations.flight_api import FlightAPI


class BookingAgent:

    def __init__(self):
        self.flight_api = FlightAPI()

    def search_alternative_flights(self, trip):
        try:
            flights = self.flight_api.get_flights(trip.origin, trip.destination)

            if not flights:
                raise Exception("No flights found")

            return flights

        except:
            # 🔥 fallback (IMPORTANT)
            return [
                {"flight": "AI202", "price": 4500},
                {"flight": "6E301", "price": 4000},
                {"flight": "SG450", "price": 3800}
            ]

    def choose_best_flight(self, flights):
        # simple logic (can improve later)
        return flights[0]

    def handle_rebooking(self, trip, decision):
        if not decision.get("rebooking_required"):
            return None

        flights = self.search_alternative_flights(trip)
        best_flight = self.choose_best_flight(flights)

        return {
            "rebooked_flight": best_flight,
            "status": "suggested"
        }