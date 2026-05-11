import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python.vision import FaceDetector, FaceDetectorOptions, RunningMode

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

_MODEL_SHORT = "/opt/models/blaze_face_short_range.tflite"
_MODEL_FULL = "/opt/models/blaze_face_full_range.tflite"


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _mediapipe_detect(image_path: str, model_path: str, min_confidence: float = 0.5) -> tuple[int, int, int, int] | None:
    img = cv2.imread(image_path)
    if img is None:
        return None
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=img_rgb)
    options = FaceDetectorOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        running_mode=RunningMode.IMAGE,
        min_detection_confidence=min_confidence,
    )
    with FaceDetector.create_from_options(options) as detector:
        result = detector.detect(mp_image)
    if not result.detections:
        return None
    largest = max(result.detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)
    bb = largest.bounding_box
    return (bb.origin_x, bb.origin_y, bb.width, bb.height)


def _haar_detect(image_path: str) -> tuple[int, int, int, int] | None:
    img = cv2.imread(image_path)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return (int(x), int(y), int(w), int(h))


def detect_face(image_path: str) -> tuple[int, int, int, int] | None:
    """Return (x, y, width, height) in pixels of the largest detected face, or None.

    Strategy: BlazeFace short-range → BlazeFace full-range → OpenCV Haar cascade.
    """
    return (
        _mediapipe_detect(image_path, _MODEL_SHORT)
        or _mediapipe_detect(image_path, _MODEL_FULL)
        or _haar_detect(image_path)
    )
