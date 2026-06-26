import os
try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import cv2
import numpy as np
import base64

app = FastAPI()

YOLO_MODEL_PATH = "models/card_seg.pt"
card_seg_model = None

if YOLO is not None and os.path.exists(YOLO_MODEL_PATH):
    card_seg_model = YOLO(YOLO_MODEL_PATH)
    print("YOLO card segmentation model loaded.")
else:
    print("YOLO model not found. Using OpenCV fallback crop.")

class GradeCardRequest(BaseModel):
    front_image: str
    back_image: str

class SurfaceEnhanceRequest(BaseModel):
    image: str

class VLMGradeRequest(BaseModel):
    front_image: str
    back_image: str
    front_surface_image: str | None = None
    back_surface_image: str | None = None
    front_centering: dict
    back_centering: dict

# Allow frontend React app to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://pregrader.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def order_points(points):
    """
    Orders 4 points into:
    top-left, top-right, bottom-right, bottom-left
    """
    rect = np.zeros((4, 2), dtype="float32")

    s = points.sum(axis=1)
    rect[0] = points[np.argmin(s)]  # top-left
    rect[2] = points[np.argmax(s)]  # bottom-right

    diff = np.diff(points, axis=1)
    rect[1] = points[np.argmin(diff)]  # top-right
    rect[3] = points[np.argmax(diff)]  # bottom-left

    return rect


def four_point_transform(image, points):
    rect = order_points(points)
    top_left, top_right, bottom_right, bottom_left = rect

    width_a = np.linalg.norm(bottom_right - bottom_left)
    width_b = np.linalg.norm(top_right - top_left)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(top_right - bottom_right)
    height_b = np.linalg.norm(top_left - bottom_left)
    max_height = int(max(height_a, height_b))

    destination = np.array(
        [
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ],
        dtype="float32",
    )

    matrix = cv2.getPerspectiveTransform(rect, destination)
    warped = cv2.warpPerspective(image, matrix, (max_width, max_height))

    return warped

def crop_card_with_yolo(image):
    """
    Uses YOLO segmentation to detect the card mask,
    then crops and straightens the card using OpenCV.

    Requires:
    backend/models/card_seg.pt

    Returns:
    cropped_image, success, message, debug_image
    """

    if card_seg_model is None:
        return None, False, "YOLO model not loaded", image.copy()

    debug_image = image.copy()

    results = card_seg_model.predict(
        source=image,
        conf=0.25,
        retina_masks=True,
        verbose=False
    )

    if not results or results[0].masks is None:
        return None, False, "YOLO found no card mask", debug_image

    result = results[0]

    masks = result.masks.data.cpu().numpy()
    boxes = result.boxes.xyxy.cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()

    if len(masks) == 0:
        return None, False, "YOLO returned empty masks", debug_image

    # Pick highest confidence mask
    best_index = int(np.argmax(confidences))
    mask = masks[best_index]

    # Resize mask to original image size if needed
    mask = cv2.resize(mask, (image.shape[1], image.shape[0]))

    # Convert mask to 0/255
    mask_uint8 = (mask > 0.5).astype(np.uint8) * 255

    # Clean mask
    kernel = np.ones((7, 7), np.uint8)
    mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, kernel)
    mask_uint8 = cv2.morphologyEx(mask_uint8, cv2.MORPH_OPEN, kernel)

    contours, _ = cv2.findContours(
        mask_uint8,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return None, False, "Could not convert YOLO mask to contour", debug_image

    contour = max(contours, key=cv2.contourArea)

    # Draw YOLO mask contour for debug
    cv2.drawContours(debug_image, [contour], -1, (0, 255, 0), 8)

    # Get rotated rectangle around card
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    points = np.array(box, dtype="float32")

    cv2.drawContours(debug_image, [box.astype(int)], -1, (255, 0, 0), 8)

    warped = four_point_transform(image, points)

    h, w = warped.shape[:2]
    if w > h:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)

    final = resize_to_card_ratio(warped)

    return final, True, "YOLO card crop successful", debug_image


def resize_to_card_ratio(image):
    """
    Pokemon card ratio is around 63mm x 88mm.
    We normalize output to portrait 735 x 1025.
    """
    target_width = 735
    target_height = 1025

    resized = cv2.resize(image, (target_width, target_height))
    return resized


def straighten_card(image):

    # First try YOLO segmentation crop if model exists
    yolo_crop, yolo_success, yolo_message, yolo_debug = crop_card_with_yolo(image)

    if yolo_success:
        return yolo_crop, True, yolo_message, yolo_debug
    
    original = image.copy()
    debug_image = image.copy()

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Slight blur to reduce noise
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    # Use threshold first because scanned cards usually sit on white background
    # This helps separate the card from scanner background.
    _, thresh = cv2.threshold(blur, 245, 255, cv2.THRESH_BINARY_INV)

    # Close gaps
    kernel = np.ones((7, 7), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return resize_to_card_ratio(original), False, "No contours found", debug_image

    image_area = image.shape[0] * image.shape[1]

    candidates = []

    for contour in contours:
        area = cv2.contourArea(contour)

        # Ignore tiny noise
        if area < image_area * 0.05:
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

        x, y, w, h = cv2.boundingRect(contour)
        aspect_ratio = w / h if h != 0 else 0

        # Pokemon card portrait ratio is about 0.716.
        # But scanned/rotated card can vary, so allow wider range.
        valid_ratio = 0.55 <= aspect_ratio <= 0.90 or 1.10 <= aspect_ratio <= 1.80

        if valid_ratio:
            candidates.append((area, contour, approx))

    if not candidates:
        return resize_to_card_ratio(original), False, "No card-like contour found", debug_image

    # Choose largest card-like contour
    candidates = sorted(candidates, key=lambda x: x[0], reverse=True)
    _, contour, approx = candidates[0]

    # Draw detected contour for debugging
    cv2.drawContours(debug_image, [contour], -1, (0, 255, 0), 8)

    # Instead of requiring exactly 4 points, use minAreaRect.
    # This works better for scans.
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    points = np.array(box, dtype="float32")

    cv2.drawContours(debug_image, [box.astype(int)], -1, (255, 0, 0), 8)

    warped = four_point_transform(original, points)

    h, w = warped.shape[:2]
    if w > h:
        warped = cv2.rotate(warped, cv2.ROTATE_90_CLOCKWISE)

    final = resize_to_card_ratio(warped)

    return final, True, "Card straightened successfully", debug_image

def image_to_base64(image):
    success, buffer = cv2.imencode(".jpg", image)

    if not success:
        raise ValueError("Could not encode image")

    encoded = base64.b64encode(buffer).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"

def base64_to_image(base64_string):
    """
    Converts data:image/jpeg;base64,... into OpenCV image.
    """
    if "," in base64_string:
        base64_string = base64_string.split(",")[1]

    image_bytes = base64.b64decode(base64_string)
    np_array = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

    return image

def create_surface_enhancement(image):
    """
    Creates a TAG-like embossed surface overlay.

    This produces a grey relief image where outlines, print texture,
    scratches, whitening, and surface differences become more visible.
    """

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Resize-safe denoise
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Improve local contrast without blowing out the whole card
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8))
    gray = clahe.apply(gray)

    # Emboss kernels from different directions
    emboss_kernel_1 = np.array([
        [-2, -1, 0],
        [-1,  1, 1],
        [ 0,  1, 2]
    ], dtype=np.float32)

    emboss_kernel_2 = np.array([
        [ 0, -1, -2],
        [ 1,  1, -1],
        [ 2,  1,  0]
    ], dtype=np.float32)

    emboss_kernel_3 = np.array([
        [-1, -1, -1],
        [ 0,  1,  0],
        [ 1,  1,  1]
    ], dtype=np.float32)

    # Apply emboss filters
    embossed_1 = cv2.filter2D(gray, cv2.CV_32F, emboss_kernel_1)
    embossed_2 = cv2.filter2D(gray, cv2.CV_32F, emboss_kernel_2)
    embossed_3 = cv2.filter2D(gray, cv2.CV_32F, emboss_kernel_3)

    # Combine directional emboss maps
    embossed = (
        0.45 * embossed_1 +
        0.35 * embossed_2 +
        0.20 * embossed_3
    )

    # Shift to mid-grey base, like actual emboss relief
    embossed = embossed + 128

    # Normalize to visible range
    embossed = cv2.normalize(embossed, None, 0, 255, cv2.NORM_MINMAX)
    embossed = np.uint8(embossed)

    # Add fine edge detail
    edges = cv2.Laplacian(gray, cv2.CV_64F, ksize=3)
    edges = np.uint8(np.absolute(edges))
    edges = cv2.normalize(edges, None, 0, 255, cv2.NORM_MINMAX)

    # Blend emboss relief + edges
    result = cv2.addWeighted(embossed, 0.82, edges, 0.18, 0)

    # Make it grey, not bright/colourful
    result = cv2.convertScaleAbs(result, alpha=1.55, beta=-35)

    # Smooth tiny scanner noise but keep outlines
    result = cv2.bilateralFilter(result, 5, 40, 40)

    # Convert to BGR for frontend display
    result_bgr = cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)

    return result_bgr

def detect_centering(image):
    """
    Better centering detection for straightened card images.

    Instead of detecting random rectangles, this scans from each card edge
    toward the center and finds the strongest transition between the border
    and the printed card design.

    Works better for scanned, flat, already-straightened cards.
    """

    h, w = image.shape[:2]

    # Convert to LAB because it separates brightness and color better
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)

    # Use L channel for brightness + A/B for color transitions
    l_channel, a_channel, b_channel = cv2.split(lab)

    # Blur to reduce scanner noise
    l_blur = cv2.GaussianBlur(l_channel, (7, 7), 0)
    a_blur = cv2.GaussianBlur(a_channel, (7, 7), 0)
    b_blur = cv2.GaussianBlur(b_channel, (7, 7), 0)

    # Gradients show where strong visual changes happen
    grad_x_l = cv2.Sobel(l_blur, cv2.CV_64F, 1, 0, ksize=3)
    grad_x_a = cv2.Sobel(a_blur, cv2.CV_64F, 1, 0, ksize=3)
    grad_x_b = cv2.Sobel(b_blur, cv2.CV_64F, 1, 0, ksize=3)

    grad_y_l = cv2.Sobel(l_blur, cv2.CV_64F, 0, 1, ksize=3)
    grad_y_a = cv2.Sobel(a_blur, cv2.CV_64F, 0, 1, ksize=3)
    grad_y_b = cv2.Sobel(b_blur, cv2.CV_64F, 0, 1, ksize=3)

    grad_x = np.abs(grad_x_l) + np.abs(grad_x_a) + np.abs(grad_x_b)
    grad_y = np.abs(grad_y_l) + np.abs(grad_y_a) + np.abs(grad_y_b)

    def strongest_vertical_edge(x_start, x_end, y_start_ratio=0.18, y_end_ratio=0.82):
        """
        Finds strong vertical transition between x_start and x_end.
        Used for left/right borders.
        """
        y1 = int(h * y_start_ratio)
        y2 = int(h * y_end_ratio)

        roi = grad_x[y1:y2, x_start:x_end]

        if roi.size == 0:
            return None

        # Average gradient strength per x column
        column_scores = roi.mean(axis=0)

        # Smooth scores
        column_scores = cv2.GaussianBlur(
            column_scores.reshape(1, -1),
            (1, 15),
            0
        ).flatten()

        best_index = int(np.argmax(column_scores))
        return x_start + best_index

    def strongest_horizontal_edge(y_start, y_end, x_start_ratio=0.18, x_end_ratio=0.82):
        """
        Finds strong horizontal transition between y_start and y_end.
        Used for top/bottom borders.
        """
        x1 = int(w * x_start_ratio)
        x2 = int(w * x_end_ratio)

        roi = grad_y[y_start:y_end, x1:x2]

        if roi.size == 0:
            return None

        # Average gradient strength per y row
        row_scores = roi.mean(axis=1)

        # Smooth scores
        row_scores = cv2.GaussianBlur(
            row_scores.reshape(-1, 1),
            (15, 1),
            0
        ).flatten()

        best_index = int(np.argmax(row_scores))
        return y_start + best_index

    # Expected search zones.
    # We do NOT search the whole image, because artwork has many strong edges.
    # We only search where borders should logically be.
    left_x = strongest_vertical_edge(
        int(w * 0.03),
        int(w * 0.22)
    )

    right_x = strongest_vertical_edge(
        int(w * 0.78),
        int(w * 0.97)
    )

    top_y = strongest_horizontal_edge(
        int(h * 0.03),
        int(h * 0.22)
    )

    bottom_y = strongest_horizontal_edge(
        int(h * 0.78),
        int(h * 0.97)
    )

    # Fallbacks based on typical Pokemon card border zones
    if left_x is None:
        left_x = int(w * 0.08)

    if right_x is None:
        right_x = int(w * 0.92)

    if top_y is None:
        top_y = int(h * 0.08)

    if bottom_y is None:
        bottom_y = int(h * 0.92)

    # Sanity clamp.
    # This prevents impossible detections.
    left_x = int(np.clip(left_x, int(w * 0.03), int(w * 0.22)))
    right_x = int(np.clip(right_x, int(w * 0.78), int(w * 0.97)))
    top_y = int(np.clip(top_y, int(h * 0.03), int(h * 0.22)))
    bottom_y = int(np.clip(bottom_y, int(h * 0.78), int(h * 0.97)))

    left_border = left_x
    right_border = w - right_x
    top_border = top_y
    bottom_border = h - bottom_y

    horizontal_total = left_border + right_border
    vertical_total = top_border + bottom_border

    if horizontal_total <= 0:
        left_percent = 50
        right_percent = 50
    else:
        left_percent = round((left_border / horizontal_total) * 100)
        right_percent = 100 - left_percent

    if vertical_total <= 0:
        top_percent = 50
        bottom_percent = 50
    else:
        top_percent = round((top_border / vertical_total) * 100)
        bottom_percent = 100 - top_percent

    # Create visual overlay
    overlay = image.copy()

    # Outer card box - green
    cv2.rectangle(
        overlay,
        (0, 0),
        (w - 1, h - 1),
        (0, 255, 0),
        5
    )

    # Detected inner border box - blue
    cv2.rectangle(
        overlay,
        (left_x, top_y),
        (right_x, bottom_y),
        (255, 0, 0),
        5
    )

    # Border measurement lines
    mid_y = h // 2
    mid_x = w // 2

    # Left border line
    cv2.line(overlay, (0, mid_y), (left_x, mid_y), (0, 255, 255), 4)

    # Right border line
    cv2.line(overlay, (right_x, mid_y), (w, mid_y), (0, 255, 255), 4)

    # Top border line
    cv2.line(overlay, (mid_x, 0), (mid_x, top_y), (0, 255, 255), 4)

    # Bottom border line
    cv2.line(overlay, (mid_x, bottom_y), (mid_x, h), (0, 255, 255), 4)

    # Text background
    cv2.rectangle(overlay, (15, 15), (360, 120), (0, 0, 0), -1)

    cv2.putText(
        overlay,
        f"L|R {left_percent}|{right_percent}",
        (30, 55),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 255, 255),
        3,
        cv2.LINE_AA
    )

    cv2.putText(
        overlay,
        f"T|B {top_percent}|{bottom_percent}",
        (30, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (0, 255, 255),
        3,
        cv2.LINE_AA
    )

    return {
        "left": left_percent,
        "right": right_percent,
        "top": top_percent,
        "bottom": bottom_percent,
        "inner_box": {
            "x": int(left_x),
            "y": int(top_y),
            "width": int(right_x - left_x),
            "height": int(bottom_y - top_y),
        },
        "border_pixels": {
            "left": int(left_border),
            "right": int(right_border),
            "top": int(top_border),
            "bottom": int(bottom_border),
        },
        "overlay_image": image_to_base64(overlay),
    }

def analyze_card_with_vlm(
    front_image,
    back_image,
    front_surface_image,
    back_surface_image,
    front_centering,
    back_centering,
):
    """
    Sends original + embossed images to VLM and returns structured grading report.
    """

    prompt = f"""
You are a trading card pre-grading assistant using a BGS-style evaluation framework.

Analyze the provided Pokémon card images.

You will receive:
1. Front original image
2. Back original image
3. Front embossed/surface-enhanced image if available
4. Back embossed/surface-enhanced image if available
5. Manual centering measurements

Manual centering:
Front: L/R {front_centering.get("left")}/{front_centering.get("right")}, T/B {front_centering.get("top")}/{front_centering.get("bottom")}
Back: L/R {back_centering.get("left")}/{back_centering.get("right")}, T/B {back_centering.get("top")}/{back_centering.get("bottom")}

Manual card boundary:
Front outer card boundary percent: {front_centering.get("cardBoundaryPercent")}
Back outer card boundary percent: {back_centering.get("cardBoundaryPercent")}

Important rules:
- Use BGS-style grading categories: centering, corners, edges, and surface.
- Treat the grade as an unofficial pre-grade estimate, not an official Beckett/BGS grade.
- Estimate subgrades first, then estimate the overall grade from those subgrades and visible defects.
- Do not simply average the subgrades. A clearly weak category should constrain the overall grade.
- The manually defined outer card boundary is the card. Do not grade or penalize anything outside that boundary.
- Ignore scanner bed, table/background, crop padding, shadows, sleeves, holders, glare, dust, and artifacts outside the manual outer boundary.
- Only defects visible on or inside the manually defined card boundary may affect the grade.
- Be cautious. Say "possible" when uncertain.
- Do not invent defects that are not visible.
- Confidence controls grade impact.
- Defects with confidence below 0.80 should not lower the estimated grade or subgrades.
- Findings below 0.80 confidence may be mentioned as possible issues, but treat them as informational only.
- Findings below 0.60 confidence should usually not affect the grade unless multiple independent visible signs support the same issue.
- High grade penalties should be based on clearly visible findings with confidence >= 0.80.
- If glare, sleeve, reflection, blur, or poor lighting blocks inspection, state that.
- For scanned/photographed cards, do not claim final professional grade certainty.
- Estimate grade only as a pre-grade.
- Give location-based findings, e.g. top-left corner, bottom edge, right surface, holo area.
- Use the embossed images to help inspect surface texture, scratches, whitening, print lines, and dents.
- If the image is in a sleeve/toploader and reflections obscure the surface, lower confidence.

Return strict JSON only.
"""

    schema = {
        "type": "object",
        "properties": {
            "estimated_grade": {
                "type": "number",
                "description": "Overall estimated pre-grade from 1 to 10, can use decimals like 8.5.",
            },
            "grade_band": {
                "type": "string",
                "description": "Short band such as Poor, Good, Near Mint, Mint, Gem Mint candidate.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence from 0 to 1.",
            },
            "subgrades": {
                "type": "object",
                "properties": {
                    "centering": {"type": "number"},
                    "corners": {"type": "number"},
                    "edges": {"type": "number"},
                    "surface": {"type": "number"},
                },
                "required": ["centering", "corners", "edges", "surface"],
                "additionalProperties": False,
            },
            "front_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "location": {"type": "string"},
                        "severity": {"type": "string"},
                        "confidence": {"type": "number"},
                        "description": {"type": "string"},
                    },
                    "required": [
                        "type",
                        "location",
                        "severity",
                        "confidence",
                        "description",
                    ],
                    "additionalProperties": False,
                },
            },
            "back_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "location": {"type": "string"},
                        "severity": {"type": "string"},
                        "confidence": {"type": "number"},
                        "description": {"type": "string"},
                    },
                    "required": [
                        "type",
                        "location",
                        "severity",
                        "confidence",
                        "description",
                    ],
                    "additionalProperties": False,
                },
            },
            "limitations": {
                "type": "array",
                "items": {"type": "string"},
            },
            "summary": {
                "type": "string",
            },
        },
        "required": [
            "estimated_grade",
            "grade_band",
            "confidence",
            "subgrades",
            "front_findings",
            "back_findings",
            "limitations",
            "summary",
        ],
        "additionalProperties": False,
    }

    content = [
        {
            "type": "input_text",
            "text": prompt,
        },
        {
            "type": "input_image",
            "image_url": front_image,
        },
        {
            "type": "input_image",
            "image_url": back_image,
        },
    ]

    if front_surface_image:
        content.append(
            {
                "type": "input_image",
                "image_url": front_surface_image,
            }
        )

    if back_surface_image:
        content.append(
            {
                "type": "input_image",
                "image_url": back_surface_image,
            }
        )

    response = client.responses.create(
        model="gpt-5.4",
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "card_pregrade_report",
                "schema": schema,
                "strict": True,
            }
        },
    )

    return json.loads(response.output_text)


@app.get("/")
def home():
    return {"message": "Pregrader backend is running"}


@app.post("/straighten-card")
async def straighten_card_endpoint(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        np_array = np.frombuffer(contents, np.uint8)
        image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        if image is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid image file"},
            )

        straightened, success, message, debug_image = straighten_card(image)
        straightened_base64 = image_to_base64(straightened)
        debug_base64 = image_to_base64(debug_image)
        original_base64 = image_to_base64(image)

        return {
            "success": success,
            "message": message,
            "original_image": original_base64,
            "debug_image": debug_base64,
            "straightened_image": straightened_base64,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )
    
@app.post("/grade-card")
async def grade_card_endpoint(
    front: UploadFile = File(...),
    back: UploadFile = File(...)
):
    try:
        # Read front image
        front_contents = await front.read()
        front_array = np.frombuffer(front_contents, np.uint8)
        front_image = cv2.imdecode(front_array, cv2.IMREAD_COLOR)

        # Read back image
        back_contents = await back.read()
        back_array = np.frombuffer(back_contents, np.uint8)
        back_image = cv2.imdecode(back_array, cv2.IMREAD_COLOR)

        if front_image is None or back_image is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid front or back image"}
            )

        # Straighten both again before grading
        front_straightened, front_success, front_message, _ = straighten_card(front_image)
        back_straightened, back_success, back_message, _ = straighten_card(back_image)

        # Detect centering
        front_centering = detect_centering(front_straightened)
        back_centering = detect_centering(back_straightened)

        return {
            "success": True,
            "front": {
                "straighten_success": front_success,
                "straighten_message": front_message,
                "centering": {
                    "left": front_centering["left"],
                    "right": front_centering["right"],
                    "top": front_centering["top"],
                    "bottom": front_centering["bottom"],
                },
                "overlay_image": front_centering["overlay_image"],
            },
            "back": {
                "straighten_success": back_success,
                "straighten_message": back_message,
                "centering": {
                    "left": back_centering["left"],
                    "right": back_centering["right"],
                    "top": back_centering["top"],
                    "bottom": back_centering["bottom"],
                },
                "overlay_image": back_centering["overlay_image"],
            },
            "flaws": [
                "Centering calculated from detected inner border.",
                "Edge, corner, scratch, indent detection will be added in the next step."
            ],
            "estimated_grade": "Pending"
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
    
@app.post("/grade-card-base64")
async def grade_card_base64_endpoint(request: GradeCardRequest):
    try:
        front_image = base64_to_image(request.front_image)
        back_image = base64_to_image(request.back_image)

        if front_image is None or back_image is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid front or back image"}
            )

        # Do NOT straighten again here.
        # We grade exactly what the user sees on screen.
        front_centering = detect_centering(front_image)
        back_centering = detect_centering(back_image)

        return {
            "success": True,
            "front": {
                "centering": {
                    "left": front_centering["left"],
                    "right": front_centering["right"],
                    "top": front_centering["top"],
                    "bottom": front_centering["bottom"],
                },
                "overlay_image": front_centering["overlay_image"],
            },
            "back": {
                "centering": {
                    "left": back_centering["left"],
                    "right": back_centering["right"],
                    "top": back_centering["top"],
                    "bottom": back_centering["bottom"],
                },
                "overlay_image": back_centering["overlay_image"],
            },
            "flaws": [
                "Centering calculated from the straightened preview image.",
                "Scratch, whitening, and indent detection will be added next."
            ],
            "estimated_grade": "Pending"
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.post("/surface-enhance")
async def surface_enhance_endpoint(request: SurfaceEnhanceRequest):
    try:
        image = base64_to_image(request.image)

        if image is None:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid image"}
            )

        enhanced = create_surface_enhancement(image)
        enhanced_base64 = image_to_base64(enhanced)

        return {
            "success": True,
            "surface_image": enhanced_base64,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
    
@app.post("/vlm-grade-card")
async def vlm_grade_card_endpoint(request: VLMGradeRequest):
    try:
        print("Front original received:", bool(request.front_image))
        print("Back original received:", bool(request.back_image))
        print("Front embossed received:", bool(request.front_surface_image))
        print("Back embossed received:", bool(request.back_surface_image))
        
        report = analyze_card_with_vlm(
            front_image=request.front_image,
            back_image=request.back_image,
            front_surface_image=request.front_surface_image,
            back_surface_image=request.back_surface_image,
            front_centering=request.front_centering,
            back_centering=request.back_centering,
        )

        return {
            "success": True,
            "report": report,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )
