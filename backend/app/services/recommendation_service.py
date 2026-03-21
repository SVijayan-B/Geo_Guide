from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class RecommendationService:

    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def get_mock_places(self, location):
        return [
            {
                "name": "Budget Cafe",
                "description": "cheap food and snacks with quick service",
                "avg_price": 150
                ,
                "tags": ["cheap", "snacks", "street", "morning", "afternoon"]
            },
            {
                "name": "Luxury Dine",
                "description": "premium dining experience for evenings and special occasions",
                "avg_price": 1200,
                "tags": ["premium", "dinner", "evening", "night"]
            },
            {
                "name": "Street Food Hub",
                "description": "local street food and quick meals with authentic flavors",
                "avg_price": 100,
                "tags": ["street", "quick", "afternoon", "evening"]
            },
            {
                "name": "Mall Food Court",
                "description": "variety of food options in a convenient mall setting",
                "avg_price": 300,
                "tags": ["family", "indoor", "afternoon", "evening"]
            }
        ]

    def _extract_budget(self, text: str) -> float | None:
        if not text:
            return None
        # Simple heuristic: look for "under 500", "budget 1200" etc.
        import re

        match = re.search(r"(?:budget|under)\s*([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)", text, re.IGNORECASE)
        if not match:
            return None
        num = match.group(1).replace(",", "")
        try:
            return float(num)
        except Exception:
            return None

    def recommend(self, context, target_price=None, memory_docs=None):
        context_text = context.get("text") or ""
        time_of_day = (context.get("time_of_day") or "").lower()

        places = self.get_mock_places(context_text)

        # Ensure we always have a usable context embedding.
        context_vector = context.get("embedding")
        if not context_vector or not isinstance(context_vector, list) or sum(context_vector) == 0:
            context_vector = self.model.encode(context_text).tolist()

        memory_docs = memory_docs or []
        memory_text = " ".join(
            [d.get("document", "") for d in memory_docs if isinstance(d, dict) and d.get("document")]
        )[:4000]

        memory_vector = None
        if memory_text.strip():
            memory_vector = self.model.encode(memory_text).tolist()

        # Time-aware desired tag hints.
        desired_tags: list[str] = []
        if time_of_day in ("morning", "night"):
            desired_tags = ["morning"] if time_of_day == "morning" else ["night"]
        elif time_of_day == "afternoon":
            desired_tags = ["afternoon", "quick"]
        elif time_of_day == "evening":
            desired_tags = ["evening", "dinner", "nightlife"]

        # Budget-aware fallback if caller didn't pass a target price.
        if target_price is None:
            extracted = self._extract_budget(memory_text or context_text)
            if extracted is not None:
                target_price = extracted

        results = []

        for place in places:
            place_text = place.get("description", "")
            tags = place.get("tags", [])
            if tags:
                place_text = place_text + " " + " ".join(tags)

            place_vector = self.model.encode(place_text)

            similarity = cosine_similarity(
                [context_vector],
                [place_vector]
            )[0][0]

            memory_similarity = 0.0
            if memory_vector is not None:
                memory_similarity = cosine_similarity(
                    [memory_vector],
                    [place_vector],
                )[0][0]

            # 💰 PRICE SCORE (NEW 🔥)
            price_score = 1

            if target_price:
                diff = abs(place["avg_price"] - target_price)
                price_score = 1 / (1 + diff)

            # 🕒 TIME-AWARE TAG SCORE (light heuristic)
            tag_match_score = 0.5
            if desired_tags and tags:
                desired_set = {t.lower() for t in desired_tags}
                place_set = {t.lower() for t in tags}
                tag_match_score = 1.0 if desired_set.intersection(place_set) else 0.5

            final_score = similarity * 0.65 + memory_similarity * 0.15 + price_score * 0.15 + tag_match_score * 0.05

            results.append({
                "name": place["name"],
                "score": float(final_score),
                "price": place["avg_price"],
            })

        results.sort(key=lambda x: x["score"], reverse=True)

        return results