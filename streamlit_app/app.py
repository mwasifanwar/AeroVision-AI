import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import streamlit as st
import cv2, time, os, tempfile, datetime
import numpy as np
import csv

from src.detector import YOLOv8Detector
from src.tracker import SimpleIOUTracker
from src.viz import draw_track

st.set_page_config(page_title="Drone Car Detection", layout="wide")

st.sidebar.title("⚙️ Controls")
conf = st.sidebar.slider("Detection confidence", 0.10, 0.80, 0.35, 0.05)
iou_t = st.sidebar.slider("Tracker IOU threshold", 0.10, 0.80, 0.30, 0.05)
max_lost = st.sidebar.slider("Tracker max lost frames", 5, 120, 30, 5)
only_cars = st.sidebar.toggle("Detect only cars (COCO)", value=True)
record_video = st.sidebar.toggle("Record processed video", value=False)
show_fps = st.sidebar.toggle("Show FPS", value=True)

st.sidebar.markdown("### 🏷 Watermark")
wm_enable = st.sidebar.toggle("Enable watermark", value=True)
wm_text = st.sidebar.text_input("Text", value="By Wasif")
wm_opacity = st.sidebar.slider("Opacity", 0.05, 0.6, 0.18, 0.01)
wm_step = st.sidebar.slider("Tile spacing (px)", 150, 500, 280, 10)
wm_angle = st.sidebar.slider("Angle (°)", -60, 60, -30, 1)

st.sidebar.markdown("### 📄 Export")
csv_log = st.sidebar.toggle("Save CSV (detections & tracks)", value=True)

st.title("🚁 Drone Car Detection & Tracking (Streamlit)")
st.caption("Upload a **video** or a single **image**. Toggle recording to export MP4. Analytics & CSV included.")

def apply_watermark(frame, text="By Wasif", opacity=0.18, step=280, angle=-30):
    """
    Full-frame tiled watermark. Draws text on a rotated layer then blends back.
    """
    h, w = frame.shape[:2]
    overlay = np.zeros_like(frame)

    
    canvas = np.zeros_like(frame)
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 1.1
    thickness = 2
    color_text = (255, 255, 255)
    color_shadow = (0, 0, 0)

    
    for y in range(0, h, step):
        for x in range(0, w, step):
            cv2.putText(canvas, text, (x+2, y+2), font, scale, color_shadow, thickness, cv2.LINE_AA)
            cv2.putText(canvas, text, (x,   y),   font, scale, color_text,  thickness, cv2.LINE_AA)

   
    M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
    rotated = cv2.warpAffine(canvas, M, (w, h))
    return cv2.addWeighted(frame, 1.0, rotated, opacity, 0)

@st.cache_resource
def get_models(conf_val: float, only_cars_val: bool):
    det = YOLOv8Detector(conf=conf_val, only_cars=only_cars_val).load()
    trk = SimpleIOUTracker(iou_thresh=iou_t, max_lost=max_lost)
    return det, trk

detector, tracker = get_models(conf, only_cars)

col1, col2 = st.columns([2, 1])
with col2:
    up_video = st.file_uploader("Upload video (mp4/avi/mov)", type=["mp4", "avi", "mov"])
    up_image = st.file_uploader("Or upload image (png/jpg/jpeg)", type=["png", "jpg", "jpeg"])
    st.markdown("Snapshots & recordings save to `outputs/`.")

os.makedirs("outputs", exist_ok=True)

if up_image and not up_video:
    file_bytes = np.asarray(bytearray(up_image.read()), dtype=np.uint8)
    frame = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    dets = detector.infer(frame)
    tracks = tracker.update(dets)

    names = detector.class_names
    for tid, tr in tracks.items():
        cls_name = names.get(tr["cls"], str(tr["cls"]))
        draw_track(frame, tid, tr["bbox"], cls_name)

    if wm_enable:
        frame = apply_watermark(frame, text=wm_text, opacity=wm_opacity, step=wm_step, angle=wm_angle)

    st.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), use_column_width=True)

    with col2:
        if st.button("📸 Save Snapshot", type="primary"):
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = f"outputs/snapshot_{ts}.png"
            cv2.imwrite(out_path, frame)
            st.success(f"Saved: {out_path}")

elif up_video:
    t = tempfile.NamedTemporaryFile(delete=False, suffix=up_video.name)
    t.write(up_video.read())
    t.flush()

    cap = cv2.VideoCapture(t.name)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 360)
    fps_src = cap.get(cv2.CAP_PROP_FPS) or 30

    writer = None
    out_video_path = None
    if record_video:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        out_video_path = f"outputs/processed_{ts}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(out_video_path, fourcc, fps_src, (w, h))

    # analytics & CSV
    seen_ids = set()
    total_frames = 0
    csv_file = None
    csv_writer = None
    csv_path = None
    if csv_log:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = f"outputs/detections_{ts}.csv"
        csv_file = open(csv_path, "w", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["frame_idx", "track_id", "cls_id", "conf", "x1", "y1", "x2", "y2"])

    stframe = st.empty()
    prev = time.time()
    frame_count = 0

    run = st.button("▶️ Start", type="primary")
    stop = st.button("⏹️ Stop")

    while run and cap.isOpened() and not stop:
        ok, frame = cap.read()
        if not ok:
            break

        total_frames += 1

        # detection + tracking
        dets = detector.infer(frame)
        tracker.iou_thresh = iou_t
        tracker.max_lost = max_lost
        tracks = tracker.update(dets)

        # analytics & csv logging
        for tid, tinfo in tracks.items():
            seen_ids.add(tid)
            if csv_writer is not None:
                x1, y1, x2, y2 = tinfo["bbox"]
                csv_writer.writerow([
                    total_frames, tid, tinfo.get("cls", -1),
                    f"{tinfo.get('conf', 0):.4f}", x1, y1, x2, y2
                ])

        # draw tracked boxes
        names = detector.class_names
        for tid, tr in tracks.items():
            cls_name = names.get(tr["cls"], str(tr["cls"]))
            draw_track(frame, tid, tr["bbox"], cls_name)

        # FPS overlay
        if show_fps:
            frame_count += 1
            now = time.time()
            if now - prev >= 0.5:
                fps = frame_count / (now - prev)
                prev, frame_count = now, 0
            try:
                fps
            except NameError:
                fps = 0.0
            cv2.putText(frame, f"FPS: {fps:.1f}", (12, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3)
            cv2.putText(frame, f"FPS: {fps:.1f}", (12, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)

        # watermark last so it sits on top
        if wm_enable:
            frame = apply_watermark(frame, text=wm_text, opacity=wm_opacity, step=wm_step, angle=wm_angle)

        # write processed video
        if writer is not None:
            writer.write(frame)

        # show frame
        stframe.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), use_column_width=True)

        # live metrics in the side column
        with col2:
            st.metric("Current cars (tracks)", len(tracks))
            st.metric("Unique cars (session)", len(seen_ids))
            st.metric("Frames processed", total_frames)

    # cleanup
    cap.release()
    if writer is not None:
        writer.release()
    if csv_file is not None:
        csv_file.close()

    with col2:
        if out_video_path is not None and os.path.exists(out_video_path):
            st.success(f"Saved processed video: {out_video_path}")
            with open(out_video_path, "rb") as f:
                st.download_button("⬇️ Download MP4", data=f, file_name=os.path.basename(out_video_path), mime="video/mp4")
        if csv_path is not None and os.path.exists(csv_path):
            st.success(f"Saved CSV: {csv_path}")
            with open(csv_path, "rb") as f:
                st.download_button("⬇️ Download CSV", data=f, file_name=os.path.basename(csv_path), mime="text/csv")

# =========================
# Idle state
# =========================
else:
    st.info("Upload a video (recommended) or a single image to begin.")
