from typing import List, Tuple, Optional
import numpy as np

class BaseDetector:
    def load(self): ...
    def infer(self, frame_bgr: np.ndarray) -> List[Tuple[int, float, Tuple[int,int,int,int]]]:

        raise NotImplementedError

class YOLOv8Detector(BaseDetector):
    def __init__(self, weights: str = "yolov8n.pt", conf: float = 0.25, device: Optional[str] = None, only_cars: bool = True):
        from ultralytics import YOLO
        self.model = YOLO(weights)
        self.conf = conf
        self.device = device
        self.only_cars = only_cars
        self._names = self.model.model.names if hasattr(self.model, "model") else self.model.names

        
        self._car_ids = {i for i, n in self._names.items()} if isinstance(self._names, dict) else set()

        if not self._car_ids and isinstance(self._names, list):
            self._car_ids = set(range(len(self._names)))
        self._car_ids = {i for i, n in (self._names.items() if isinstance(self._names, dict) else enumerate(self._names)) if str(n).lower() == "car"}

    def load(self):
        return self

    def infer(self, frame_bgr: np.ndarray):
        res = self.model.predict(source=frame_bgr[..., ::-1], conf=self.conf, device=self.device, verbose=False)
        outs = []
        for r in res:
            if getattr(r, "boxes", None) is None:
                continue
            for b in r.boxes:
                cls_id = int(b.cls.item())
                if self.only_cars and cls_id not in self._car_ids:
                    continue
                conf = float(b.conf.item())
                x1, y1, x2, y2 = map(int, b.xyxy[0].tolist())
                outs.append((cls_id, conf, (x1, y1, x2, y2)))
        return outs

    @property
    def class_names(self):
        if isinstance(self._names, dict):
            return self._names
        return {i: n for i, n in enumerate(self._names)}
