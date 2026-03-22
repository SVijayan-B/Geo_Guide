from __future__ import annotations

import os


class VisionAgent:
    _detector = None
    _captioner = None
    _init_attempted = False

    def __init__(self):
        if not VisionAgent._init_attempted:
            VisionAgent._init_attempted = True
            try:
                from ultralytics import YOLO

                VisionAgent._detector = YOLO("yolov8n.pt")
            except Exception:
                VisionAgent._detector = None

            try:
                from transformers import pipeline

                VisionAgent._captioner = pipeline("image-to-text", model="Salesforce/blip-image-captioning-base")
            except Exception:
                VisionAgent._captioner = None

    def _fallback_description(self, image_path: str) -> str:
        filename = os.path.basename(image_path)
        stem = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").strip()
        return f"Image appears to contain {stem or 'a travel scene'}."

    def detect_objects(self, image_path: str) -> list[str]:
        detector = VisionAgent._detector
        if detector is None:
            stem = os.path.splitext(os.path.basename(image_path))[0]
            tokens = [token.lower() for token in stem.replace("-", " ").replace("_", " ").split() if token]
            return tokens[:5] or ["object"]

        try:
            results = detector(image_path)
            objects: list[str] = []
            for result in results:
                for box in result.boxes:
                    objects.append(result.names[int(box.cls)])
            return list(set(objects)) or ["object"]
        except Exception:
            return ["object"]

    def describe_scene(self, image_path: str) -> str:
        captioner = VisionAgent._captioner
        if captioner is None:
            return self._fallback_description(image_path)

        try:
            result = captioner(image_path)
            text = result[0].get("generated_text") if result else None
            return text or self._fallback_description(image_path)
        except Exception:
            return self._fallback_description(image_path)

    def analyze_image(self, image_path: str) -> dict[str, object]:
        objects = self.detect_objects(image_path)
        description = self.describe_scene(image_path)
        return {"objects": objects, "description": description}
