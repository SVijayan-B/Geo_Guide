from __future__ import annotations

from app.integrations.location_api import LocationAPI


class DealAgent:
    def __init__(self):
        self.location_api = LocationAPI()

    def find_best_deals(self, city: str, item: str, target_price: float) -> list[dict[str, object]]:
        places = self.location_api.get_places(city)
        if not places:
            places = [
                {"name": f"{city} Local Market", "category": "market"},
                {"name": f"{city} Budget Mall", "category": "shopping"},
                {"name": f"{city} Value Hub", "category": "retail"},
            ]

        deals = []
        for idx, place in enumerate(places[:5]):
            discount_factor = 0.65 + (idx * 0.05)
            estimated = round(float(target_price) * min(discount_factor, 0.9), 2)
            deals.append(
                {
                    "place": place.get("name"),
                    "item": item,
                    "estimated_price": estimated,
                    "deal_score": round(1.0 - (idx * 0.08), 2),
                    "category": place.get("category"),
                }
            )

        return deals
