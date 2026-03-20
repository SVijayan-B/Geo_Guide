class VisionClassifier:

    def classify(self, vision_output):
        objects = vision_output["objects"]
        description = vision_output["description"].lower()

        # 🏛️ Place detection
        place_keywords = ["building", "tower", "temple", "monument", "church"]

        if any(word in description for word in place_keywords):
            return "place"

        # 🍔 Object detection
        return "object"