from app.integrations.location_api import LocationAPI


class DealAgent:

    def __init__(self):
        self.location_api = LocationAPI()

    def find_best_deals(self, city, item, target_price):
        places = self.location_api.get_places(city)

        deals = []

        for p in places:
            deals.append({
                "place": p["name"],
                "item": item,
                "estimated_price": int(target_price * 0.7),  # cheaper
                "deal_score": 0.9
            })

        return deals