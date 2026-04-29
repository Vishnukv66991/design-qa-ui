from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os, uuid, math, io, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ImageStat
import cv2

# ── Tesseract: optional, degrades gracefully if not installed ──────────────
try:
    import pytesseract
    # Common Windows install path
    _win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.name == "nt" and os.path.exists(_win_path):
        pytesseract.pytesseract.tesseract_cmd = _win_path
    pytesseract.get_tesseract_version()   # raises if not found
    TESSERACT_OK = True
except Exception:
    TESSERACT_OK = False

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

CTA_KEYWORDS = [
    "buy now", "shop now", "order now", "add to cart",
    "register", "sign up", "get started", "create account",
    "learn more", "read more", "find out more",
    "subscribe", "download", "try free", "try now",
    "contact us", "book now", "get quote", "request demo",
    "watch now", "explore", "start now",
]

# ══════════════════════════════════════════════════════════════════════════════
# HELPER — WCAG 2.1 contrast math (Vectorized for high performance)
# ══════════════════════════════════════════════════════════════════════════════
def _relative_luminance_vectorized(img_array):
    c = img_array.astype(np.float32) / 255.0
    c_out = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c_out[..., 0] + 0.7152 * c_out[..., 1] + 0.0722 * c_out[..., 2]


# ══════════════════════════════════════════════════════════════════════════════
# ── Shared: downscale helper ───────────────────────────────────────────────
def _downscale_cv(img_cv, max_dim=600):
    h, w = img_cv.shape[:2]
    if max(w, h) <= max_dim:
        return img_cv
    scale = max_dim / max(w, h)
    return cv2.resize(img_cv, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

def _downscale_pil(img_pil, max_dim=800):
    w, h = img_pil.size
    if max(w, h) <= max_dim:
        return img_pil
    scale = max_dim / max(w, h)
    return img_pil.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 1 — Image Quality  (OpenCV Laplacian blur + resolution)
# ══════════════════════════════════════════════════════════════════════════════
def _check_image_quality(img_cv, w, h):
    issues = []
    small = _downscale_cv(img_cv, 600)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    lap_var = round(float(cv2.Laplacian(gray, cv2.CV_64F).var()), 1)

    if w < 1000 or h < 1000:
        issues.append({
            "category": "Image",
            "severity": "high",
            "problem": f"Low resolution: {w}×{h}px (recommended ≥ 1000×1000px).",
            "impact": "Appears pixelated on retina/4K screens and is unusable for print.",
            "suggestion": "Export at minimum 1080×1080px. Use the original high-res source file.",
            "confidence": 1.0,
        })

    if lap_var < 50:
        issues.append({
            "category": "Image",
            "severity": "high",
            "problem": f"Significant blur detected (sharpness score: {lap_var}). Image is out of focus.",
            "impact": "Blurry images fail quality checks for professional delivery and print.",
            "suggestion": "Replace with a sharper source image. Never scale up small images.",
            "confidence": 0.85,
        })
    elif lap_var < 100:
        issues.append({
            "category": "Image",
            "severity": "medium",
            "problem": f"Mild blur detected (sharpness score: {lap_var}).",
            "impact": "Reduces perceived quality on high-DPI displays.",
            "suggestion": "Apply unsharp mask or use a higher-resolution source.",
            "confidence": 0.70,
        })

    return issues, lap_var


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 2 — Layout & Alignment  (OpenCV bounding-box analysis)
# ══════════════════════════════════════════════════════════════════════════════
def _check_layout(img_cv, w, h):
    issues = []
    small = _downscale_cv(img_cv, 600)

    # Aspect ratio
    aspect = round(w / h, 2)
    fmt = "Unknown"
    if 0.99 <= aspect <= 1.01:
        fmt = "Square (1:1) — Instagram Post"
    elif 0.56 <= aspect <= 0.62:
        fmt = "Vertical (9:16) — Story / Reel"
    elif 1.70 <= aspect <= 1.80:
        fmt = "Landscape (16:9) — Banner / YouTube"
    elif 1.18 <= aspect <= 1.22:
        fmt = "Portrait (4:5) — Instagram Feed"
    else:
        fmt = f"Custom ({aspect}:1)"
        issues.append({
            "category": "Layout",
            "severity": "medium",
            "problem": f"Non-standard aspect ratio: {aspect}:1.",
            "impact": "Platforms may crop or letterbox the design, cutting off key elements.",
            "suggestion": "Resize to 1:1 (1080×1080), 9:16 (1080×1920), or 16:9 (1920×1080).",
            "confidence": 0.90,
        })

    # Vertical spacing consistency via contours (on downscaled image)
    sh, sw = small.shape[:2]
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(blurred, 30, 100)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = sw * sh * 0.001
    bboxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > min_area]

    if len(bboxes) >= 3:
        by_y = sorted(bboxes, key=lambda b: b[1])
        gaps = [
            by_y[i + 1][1] - (by_y[i][1] + by_y[i][3])
            for i in range(len(by_y) - 1)
            if by_y[i + 1][1] - (by_y[i][1] + by_y[i][3]) > 0
        ]
        if len(gaps) >= 2:
            avg = sum(gaps) / len(gaps)
            std = math.sqrt(sum((g - avg) ** 2 for g in gaps) / len(gaps))
            if avg > 5 and std / avg > 0.5:
                issues.append({
                    "category": "Layout",
                    "severity": "medium",
                    "problem": f"Inconsistent vertical spacing (avg {avg:.0f}px, deviation ±{std:.0f}px).",
                    "impact": "Uneven gaps create visual imbalance and look unprofessional.",
                    "suggestion": "Use a consistent 8px spacing scale (8, 16, 24, 32px) between all elements.",
                    "confidence": 0.65,
                })

    return issues, fmt, len(bboxes)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 3 — Color & Contrast  (WCAG 2.1)
# ══════════════════════════════════════════════════════════════════════════════
def _check_color_contrast(img_pil, w, h):
    issues = []
    
    # Fast resize for color processing to dramatically speed up analysis
    scale = min(400 / w, 400 / h)
    if scale < 1:
        thumb = img_pil.resize((int(w * scale), int(h * scale)), Image.Resampling.BILINEAR)
    else:
        thumb = img_pil
        
    arr = np.array(thumb.convert("RGB"))
    th, tw = arr.shape[:2]

    regions = {
        "top-left":     arr[:th//4, :tw//4],
        "top-right":    arr[:th//4, 3*tw//4:],
        "center":       arr[th//4:3*th//4, tw//4:3*tw//4],
        "bottom-left":  arr[3*th//4:, :tw//4],
        "bottom-right": arr[3*th//4:, 3*tw//4:],
    }

    low = []
    all_lum = []
    for name, reg in regions.items():
        if reg.size == 0:
            continue
        
        # Vectorized luminance calculation for the entire region simultaneously
        lums = _relative_luminance_vectorized(reg).flatten()
        all_lum.append(float(np.mean(lums)))
        
        hi, lo = float(np.max(lums)), float(np.min(lums))
        cr = round((hi + 0.05) / (lo + 0.05), 2)
        if cr < 3.0:
            low.append(f"{name} ({cr}:1)")

    if len(low) >= 2:
        issues.append({
            "category": "Color",
            "severity": "high",
            "problem": f"Low WCAG contrast in regions: {', '.join(low)}. Minimum required: 4.5:1.",
            "impact": "Text unreadable for low-vision users; fails WCAG 2.1 AA standard.",
            "suggestion": "Darken text or lighten background. Verify each pair with WebAIM Contrast Checker.",
            "confidence": 0.70,
        })
    elif len(low) == 1:
        issues.append({
            "category": "Color",
            "severity": "medium",
            "problem": f"Low contrast detected in {low[0]}. WCAG minimum is 4.5:1.",
            "impact": "Legibility reduced for users with low vision or bright ambient lighting.",
            "suggestion": "Adjust foreground/background color pair in that region to meet 4.5:1.",
            "confidence": 0.65,
        })

    avg_lum = sum(all_lum) / len(all_lum) if all_lum else 0
    if avg_lum > 0.85:
        issues.append({
            "category": "Color",
            "severity": "low",
            "problem": "Design is very bright/white-dominant.",
            "impact": "May blend into light-background platforms reducing visual separation.",
            "suggestion": "Add a subtle border, drop shadow, or darker section to ground the design.",
            "confidence": 0.60,
        })

    return issues, round(avg_lum, 3)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 4 & 5 — OCR: Typography + Text Extraction
# ══════════════════════════════════════════════════════════════════════════════
def _check_typography_and_extract_text(img_pil):
    issues = []
    text = ""
    heights = []

    if not TESSERACT_OK:
        return issues, text, heights

    try:
        # Downscale for OCR — Tesseract is 5-10x faster on smaller images
        ocr_img = _downscale_pil(img_pil, 800)
        data = pytesseract.image_to_data(
            ocr_img, output_type=pytesseract.Output.DICT, config="--psm 11"
        )
        words = []
        for i, t in enumerate(data["text"]):
            if t.strip() and int(data["conf"][i]) > 30:
                words.append(t.strip())
                if data["height"][i] > 5:
                    heights.append(data["height"][i])
        
        text = " ".join(words)

        distinct = len(set(heights))
        if distinct > 5:
            issues.append({
                "category": "Typography",
                "severity": "medium",
                "problem": f"{distinct} distinct text sizes detected — exceeds best-practice maximum of 3.",
                "impact": "Typographic inconsistency breaks visual rhythm and weakens brand identity.",
                "suggestion": "Restrict to 3 sizes: headline, body, caption. Use font weight for emphasis instead of new sizes.",
                "confidence": 0.65,
            })

        if heights and min(heights) < 12:
            issues.append({
                "category": "Typography",
                "severity": "high",
                "problem": f"Text detected at {min(heights)}px — below the 12px readability minimum.",
                "impact": "Unreadable on mobile screens and fails accessibility guidelines.",
                "suggestion": "Set minimum body text to 14px and captions to 12px.",
                "confidence": 0.70,
            })

        if not words:
            issues.append({
                "category": "Content",
                "severity": "medium",
                "problem": "No readable text detected. Design may rely entirely on embedded graphics.",
                "impact": "Screen readers and search engines cannot index the content.",
                "suggestion": "Ensure headline, CTA, and brand name are real text (not flattened into image).",
                "confidence": 0.50,
            })

    except Exception:
        pass

    return issues, text.strip(), heights


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 6 — CTA Detection
# ══════════════════════════════════════════════════════════════════════════════
def _check_cta(text):
    found = [kw for kw in CTA_KEYWORDS if kw in text.lower()]
    return found


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 7 — Visual Hierarchy  (heuristics)
# ══════════════════════════════════════════════════════════════════════════════
def _check_visual_hierarchy(img_cv, w, h, cta_found, has_text):
    issues = []

    if has_text and not cta_found:
        issues.append({
            "category": "CTA",
            "severity": "high",
            "problem": "No Call-to-Action detected in the design.",
            "impact": "Without a CTA, viewers have no clear next step — conversion rate drops significantly.",
            "suggestion": "Add a prominent CTA: 'Shop Now', 'Learn More', 'Get Started', 'Register', etc.",
            "confidence": 0.65,
        })

    small = _downscale_cv(img_cv, 600)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    sh = gray.shape[0]
    top = gray[: sh // 3, :]
    if float(np.std(top)) < 15:
        issues.append({
            "category": "Hierarchy",
            "severity": "medium",
            "problem": "Top third of the design has very low visual variation — no clear focal point.",
            "impact": "Viewers' eyes have no entry point; attention is unfocused.",
            "suggestion": "Place the primary headline or hero image in the top third with strong contrast.",
            "confidence": 0.60,
        })

    return issues


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 8 — Spacing & Density
# ══════════════════════════════════════════════════════════════════════════════
def _check_density(img_cv, w, h):
    issues = []
    small = _downscale_cv(img_cv, 600)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    sh, sw = gray.shape[:2]
    density = round(cv2.countNonZero(binary) / (sw * sh) * 100, 1)

    if density > 75:
        issues.append({
            "category": "Layout",
            "severity": "medium",
            "problem": f"High content density: {density}% of canvas is occupied. Design appears overcrowded.",
            "impact": "Dense layouts overwhelm viewers and dilute focus on key messages.",
            "suggestion": "Add padding/margins around elements. Remove non-essential items. Aim for ≤65% density.",
            "confidence": 0.70,
        })
    elif density < 5:
        issues.append({
            "category": "Layout",
            "severity": "low",
            "problem": f"Very low content density: {density}%. Design appears sparse.",
            "impact": "May feel incomplete or lacking visual value.",
            "suggestion": "Scale up key elements or add supporting visuals to fill the canvas purposefully.",
            "confidence": 0.60,
        })

    return issues, density


# ══════════════════════════════════════════════════════════════════════════════
# SCORING + STRENGTHS + QUICK FIXES
# ══════════════════════════════════════════════════════════════════════════════
def _score(issues):
    s = 100
    for i in issues:
        s -= {"high": 12, "medium": 6, "low": 2}.get(i["severity"], 0)
    return max(10, min(100, s))


def _strengths(fmt, w, h, lap_var, cta_found, density, has_text):
    out = []
    if w >= 1000 and h >= 1000:
        out.append(f"Resolution is adequate ({w}×{h}px) for digital use.")
    if "Custom" not in fmt and "Unknown" not in fmt:
        out.append(f"Correct platform format detected: {fmt}.")
    if lap_var >= 100:
        out.append("Image sharpness is good — no significant blur detected.")
    if cta_found:
        out.append(f"Call-to-Action present: '{', '.join(cta_found)}'.")
    if 20 <= density <= 65:
        out.append("Content density is balanced — adequate white space present.")
    if has_text:
        out.append("Text content is legible and detectable by OCR.")
    return out[:4]


def _quick_fixes(issues):
    highs = [i["suggestion"] for i in issues if i["severity"] == "high"]
    mids  = [i["suggestion"] for i in issues if i["severity"] == "medium"]
    combined = highs + mids
    return combined[:3] if combined else ["No critical fixes required. Review medium-severity items."]


def _summary(score, issues):
    highs = sum(1 for i in issues if i["severity"] == "high")
    meds  = sum(1 for i in issues if i["severity"] == "medium")
    if score >= 85:
        return f"Design meets professional quality standards with {meds} minor improvement opportunities."
    if score >= 65:
        return f"Design is functional but has {highs} high-severity and {meds} medium-severity issues requiring attention before delivery."
    return f"Design requires significant revision — {highs} critical issues detected that directly impact usability and readability."


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINT
# ══════════════════════════════════════════════════════════════════════════════
@router.post("/analyze")
async def upload_file(
    file: UploadFile = File(...),
    requirements: str = Form(...),
    guidance: str = Form(None),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        return JSONResponse(status_code=400, content={"error": "Only image files allowed"})

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(status_code=400, content={"error": "File size exceeds 10MB limit"})

    if not requirements.strip():
        return JSONResponse(status_code=400, content={"error": "Requirements are required"})

    # Save original
    ext = os.path.splitext(file.filename)[1] or ".png"
    uid = uuid.uuid4().hex[:6]
    filename = f"design_{uid}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Process images from memory (much faster)
    try:
        img_pil = Image.open(io.BytesIO(content)).convert("RGB")
        w, h = img_pil.size
        img_cv = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
        
        # Save grayscale
        gs_filename = f"grayscale_{uid}{ext}"
        gs_path = os.path.join(UPLOAD_DIR, gs_filename)
        img_pil.convert("L").save(gs_path)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Processing failed: {e}"})

    # ── Run all 8 modules IN PARALLEL ──────────────────────────────────────
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=4) as pool:
        f_quality  = pool.submit(_check_image_quality, img_cv, w, h)
        f_layout   = pool.submit(_check_layout, img_cv, w, h)
        f_color    = pool.submit(_check_color_contrast, img_pil, w, h)
        f_typo     = pool.submit(_check_typography_and_extract_text, img_pil)
        f_density  = pool.submit(_check_density, img_cv, w, h)

    q_issues, lap_var            = f_quality.result()
    l_issues, fmt, n_elements    = f_layout.result()
    c_issues, avg_lum            = f_color.result()
    t_issues, raw_text, heights  = f_typo.result()
    d_issues, density            = f_density.result()

    # These depend on OCR output, so run after
    cta_found = _check_cta(raw_text)
    h_issues  = _check_visual_hierarchy(img_cv, w, h, cta_found, bool(raw_text))

    elapsed = round(time.time() - t0, 2)

    all_issues = q_issues + l_issues + c_issues + t_issues + d_issues + h_issues

    # Cap at 10 issues, highest severity first
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_issues.sort(key=lambda x: severity_order.get(x["severity"], 3))
    all_issues = all_issues[:10]

    score = _score(all_issues)

    return {
        "status": "success",
        "saved_file": filename,
        "processed_file": gs_filename,
        "original_name": file.filename,
        "requirements": requirements,
        "guidance": guidance,
        # ── QA Report ──
        "score": score,
        "summary": _summary(score, all_issues),
        "issues": all_issues,
        "strengths": _strengths(fmt, w, h, lap_var, cta_found, density, bool(raw_text)),
        "quick_fixes": _quick_fixes(all_issues),
        # ── Meta ──
        "meta": {
            "format": fmt,
            "resolution": f"{w}×{h}px",
            "sharpness": lap_var,
            "density": f"{density}%",
            "elements_detected": n_elements,
            "text_extracted": raw_text[:300] if raw_text else "(none — install Tesseract for OCR)",
            "cta_found": cta_found,
            "tesseract_active": TESSERACT_OK,
            "analysis_time": f"{elapsed}s",
        },
    }
