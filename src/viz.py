import cv2
from typing import Tuple

def draw_track(frame, track_id: int, bbox: Tuple[int,int,int,int], label: str, color=(0,255,0)):
    x1, y1, x2, y2 = bbox
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    text = f"ID {track_id} | {label}"
    tw, th = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
    y_text = max(15, y1 - 8)
    cv2.rectangle(frame, (x1, y_text - th - 6), (x1 + tw + 6, y_text + 4), (0,0,0), -1)
    cv2.putText(frame, text, (x1 + 3, y_text), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    return frame
