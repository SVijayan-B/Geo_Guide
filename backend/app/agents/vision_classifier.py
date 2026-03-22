from __future__ import annotations


class VisionClassifier:
    PLACE_KEYWORDS = {
        "building",
        "tower",
        "temple",
        "monument",
        "church",
        "mosque",
        "palace",
        "museum",
        "bridge",
        "fort",
        "cathedral",
        "landmark",
        "statue",
    }

    def classify(self, vision_output: dict) -> str:
        objects = [str(item).lower() for item in (vision_output.get("objects") or [])]
        description = str(vision_output.get("description") or "").lower()

        if any(word in description for word in self.PLACE_KEYWORDS):
            return "place"
        if any(word in self.PLACE_KEYWORDS for word in objects):
            return "place"
        return "object"
