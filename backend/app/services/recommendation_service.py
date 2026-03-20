from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class RecommendationService:

    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def get_mock_places(self, location):
        return [
            {
                "name": "Budget Cafe",
                "description": "cheap food and snacks",
                "avg_price": 150
            },
            {
                "name": "Luxury Dine",
                "description": "premium dining experience",
                "avg_price": 1200
            },
            {
                "name": "Street Food Hub",
                "description": "local street food and quick meals",
                "avg_price": 100
            },
            {
                "name": "Mall Food Court",
                "description": "variety of food options",
                "avg_price": 300
            }
        ]

    def recommend(self, context, target_price=None):
        places = self.get_mock_places(context["text"])

        context_vector = context["embedding"]

        results = []

        for place in places:
            place_vector = self.model.encode(place["description"])

            similarity = cosine_similarity(
                [context_vector],
                [place_vector]
            )[0][0]

            # 💰 PRICE SCORE (NEW 🔥)
            price_score = 1

            if target_price:
                diff = abs(place["avg_price"] - target_price)
                price_score = 1 / (1 + diff)

            final_score = similarity * 0.7 + price_score * 0.3

            results.append({
                "name": place["name"],
                "score": float(final_score),
                "price": place["avg_price"]
            })

        results.sort(key=lambda x: x["score"], reverse=True)

        return results