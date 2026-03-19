from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class RecommendationService:

    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def get_mock_places(self, location):
        return [
            {
                "name": "Cafe Sunrise",
                "description": "A calm place for breakfast and coffee"
            },
            {
                "name": "City Mall",
                "description": "Shopping and entertainment hub"
            },
            {
                "name": "Green Park",
                "description": "Relaxing park with nature and fresh air"
            },
            {
                "name": "Night Bar",
                "description": "Great nightlife and drinks"
            }
        ]

    def recommend(self, context):
        places = self.get_mock_places(context["text"])

        # Context embedding
        context_vector = context["embedding"]

        results = []

        for place in places:
            place_vector = self.model.encode(place["description"])

            similarity = cosine_similarity(
                [context_vector],
                [place_vector]
            )[0][0]

            results.append({
                "name": place["name"],
                "score": float(similarity)
            })

        results.sort(key=lambda x: x["score"], reverse=True)

        return results