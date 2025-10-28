from typing import List, Tuple, Dict
import numpy as np

Detection = Tuple[int, float, Tuple[int,int,int,int]]

class SimpleIOUTracker:
    """
    Minimal, deterministic IOU tracker good enough for a demo.
    Keeps IDs stable if boxes overlap; drops tracks after `max_lost` frames.
    """
    def __init__(self, iou_thresh: float = 0.3, max_lost: int = 30):
        self.iou_thresh = iou_thresh
        self.max_lost = max_lost
        self.next_id = 1
        self.tracks: Dict[int, dict] = {}  

    @staticmethod
    def iou(a, b) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
        inter_h = max(0, min(ay2, by2) - max(ay1, by1))
        inter = inter_w * inter_h
        a_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        b_area = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = a_area + b_area - inter + 1e-6
        return inter / union

    def update(self, detections: List[Detection]):
        
        for tid in list(self.tracks.keys()):
            self.tracks[tid]["lost"] += 1
            if self.tracks[tid]["lost"] > self.max_lost:
                self.tracks.pop(tid, None)

        matched = set()

       
        for tid, tr in list(self.tracks.items()):
            best_iou, best_idx = 0.0, -1
            for i, det in enumerate(detections):
                if i in matched:
                    continue
                _, _, bbox = det
                iou = self.iou(tr["bbox"], bbox)
                if iou > best_iou:
                    best_iou, best_idx = iou, i
            if best_iou >= self.iou_thresh and best_idx >= 0:
                cls_id, conf, bbox = detections[best_idx]
                self.tracks[tid].update({"bbox": bbox, "lost": 0, "cls": cls_id, "conf": conf})
                matched.add(best_idx)

        
        for i, det in enumerate(detections):
            if i in matched:
                continue
            cls_id, conf, bbox = det
            self.tracks[self.next_id] = {"bbox": bbox, "lost": 0, "cls": cls_id, "conf": conf}
            self.next_id += 1

        return self.tracks
