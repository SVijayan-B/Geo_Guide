from ultralytics import YOLO
from transformers import pipeline


class VisionAgent:

    def __init__(self):
        # 🎯 Object detection (CNN-based)
        self.detector = YOLO("yolov8n.pt")

        # 🧠 Semantic understanding
        self.captioner = pipeline(
            "image-to-text",
            model="Salesforce/blip-image-captioning-base"
        )

    def detect_objects(self, image_path):
        results = self.detector(image_path)

        objects = []
        for r in results:
            for box in r.boxes:
                objects.append(r.names[int(box.cls)])

        return list(set(objects))

    def describe_scene(self, image_path):
        result = self.captioner(image_path)
        return result[0]["generated_text"]

    def analyze_image(self, image_path):
        objects = self.detect_objects(image_path)
        description = self.describe_scene(image_path)

        return {
            "objects": objects,
            "description": description
        }