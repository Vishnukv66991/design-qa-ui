from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os, uuid, math, io, time, re
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image, ExifTags
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

# ── Spellcheck: optional ──────────────────────────────────────────────────
try:
    from spellchecker import SpellChecker
    _spell = SpellChecker()
    SPELL_OK = True
except Exception:
    _spell = None
    SPELL_OK = False

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_IMAGE_SIZE = 25 * 1024 * 1024
MAX_VIDEO_SIZE = 200 * 1024 * 1024
MAX_PDF_SIZE = 100 * 1024 * 1024

try:
    import pypdfium2 as pdfium
    PDFIUM_OK = True
except Exception:
    pdfium = None
    PDFIUM_OK = False

CTA_KEYWORDS = [
    "buy now", "shop now", "order now", "add to cart",
    "register", "sign up", "get started", "create account",
    "learn more", "read more", "find out more",
    "subscribe", "download", "try free", "try now",
    "contact us", "book now", "get quote", "request demo",
    "watch now", "explore", "start now",
]

MODULE_DEFS = {
    "image_quality": "Image Quality",
    "layout": "Layout & Alignment",
    "color_contrast": "Color & Contrast",
    "typography_ocr": "Typography + OCR",
    "density": "Spacing & Density",
    "image_forensics": "Image Forensics",
    "color_palette": "Color Palette",
    "edge_precision": "Edge Precision",
    "duplicates_overlaps": "Duplicate & Overlap",
    "exposure_analysis": "Exposure",
    "cta_detection": "CTA Detection",
    "visual_hierarchy": "Visual Hierarchy",
    "spelling_locale": "Spelling & Locale",
}

REQUIREMENT_KEYWORDS = {
    "color_contrast": {"contrast", "wcag", "readability", "color", "accessible"},
    "typography_ocr": {"font", "typography", "text", "headline"},
    "layout": {"layout", "align", "alignment", "spacing", "grid"},
    "density": {"density", "crowded", "white space", "whitespace"},
    "cta_detection": {"cta", "button", "call to action", "shop now", "learn more"},
    "visual_hierarchy": {"hierarchy", "focus", "focal", "attention"},
    "image_quality": {"resolution", "sharp", "blur", "quality"},
}

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
        if cr < 4.5:
            low.append(f"{name} ({cr}:1)")

    if len(low) >= 2:
        issues.append({
            "category": "Color",
            "severity": "high",
            "problem": f"Low WCAG contrast in regions: {', '.join(low)}. Minimum required: 4.5:1 (AA).",
            "impact": "Text unreadable for low-vision users; fails WCAG 2.1 AA standard.",
            "suggestion": "Darken text or lighten background. Verify each pair with WebAIM Contrast Checker.",
            "confidence": 0.70,
        })
    elif len(low) == 1:
        issues.append({
            "category": "Color",
            "severity": "medium",
            "problem": f"Low contrast detected in {low[0]}. WCAG minimum is 4.5:1 (AA).",
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

    except Exception as e:
        issues.append({
            "category": "Typography",
            "severity": "medium",
            "problem": "Typography/OCR module failed during extraction.",
            "impact": "Text-based checks were incomplete for this run.",
            "suggestion": "Confirm Tesseract installation and retry with a clearer image.",
            "confidence": 0.95,
            "detected_value": str(e)[:160],
        })

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
# MODULE 9 — Advanced Image Forensics  (EXIF, Compression, Artifacts)
# ══════════════════════════════════════════════════════════════════════════════
def _check_image_forensics(img_pil, img_cv, file_path, w, h):
    issues = []
    try:
        # Check EXIF orientation (common human-missed issue)
        exif = img_pil.getexif() if hasattr(img_pil, 'getexif') else {}
        orientation_tag = None
        for tag_id, value in exif.items():
            tag_name = ExifTags.TAGS.get(tag_id, tag_id)
            if tag_name == "Orientation":
                orientation_tag = value
                break
        if orientation_tag and orientation_tag != 1:
            issues.append({
                "category": "Image",
                "severity": "medium",
                "problem": f"EXIF orientation tag is {orientation_tag} (not standard 1). Image may display rotated on some platforms.",
                "impact": "Image appears rotated differently across browsers, viewers, and social platforms.",
                "suggestion": "Normalize image orientation in photo editing software and strip EXIF data before export.",
                "confidence": 0.95,
                "detected_value": f"Orientation: {orientation_tag}",
                "expected_value": "Orientation: 1 (normal)",
            })

        # Detect JPEG compression artifacts (DCT-based, not just blur)
        small = _downscale_cv(img_cv, 600)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        # High-frequency DCT analysis for blocking artifacts
        h, w_small = gray.shape
        dct_energies = []
        for y in range(0, h - 8, 8):
            for x in range(0, w_small - 8, 8):
                block = gray[y:y+8, x:x+8].astype(np.float32)
                dct = cv2.dct(block)
                # Quantization artifacts show in high-frequency DCT coefficients
                high_freq = dct[4:, 4:].flatten()
                dct_energies.append(float(np.sum(high_freq ** 2)))
        if dct_energies:
            avg_dct = np.mean(dct_energies)
            # High DCT energy in high-freq = compression artifacts
            if avg_dct > 5000:
                issues.append({
                    "category": "Image",
                    "severity": "medium",
                    "problem": f"JPEG compression artifacts detected (DCT energy: {avg_dct:.0f}). Blocky artifacts visible.",
                    "impact": "Visible 8x8 pixel blocking artifacts degrade professional appearance, especially on gradients.",
                    "suggestion": "Re-export with quality 90+ or use PNG/WebP for images with gradients or text.",
                    "confidence": 0.80,
                    "detected_value": f"DCT high-freq energy: {avg_dct:.0f}",
                    "expected_value": "DCT high-freq energy < 3000 (minimal compression)",
                })

        # Detect color banding (posterization) in gradients
        arr = np.array(_downscale_pil(img_pil, 400))
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        # Check for duplicate adjacent values (sign of banding)
        banding_scores = []
        for channel in [r, g, b]:
            unique_ratios = []
            for y in range(0, channel.shape[0], 10):
                row = channel[y, :]
                unique = len(np.unique(row))
                unique_ratios.append(unique / len(row))
            banding_scores.append(1 - np.mean(unique_ratios))
        if np.mean(banding_scores) > 0.3:
            issues.append({
                "category": "Image",
                "severity": "low",
                "problem": "Color banding detected in gradients. Smooth gradients show visible steps between colors.",
                "impact": "Gradients appear unprofessional with visible stripes instead of smooth transitions.",
                "suggestion": "Export with higher bit depth (16-bit) or add dithering. Use PNG/WebP instead of JPEG for gradient-heavy designs.",
                "confidence": 0.70,
                "detected_value": f"Banding score: {np.mean(banding_scores):.2f}",
                "expected_value": "Banding score < 0.2 (smooth gradients)",
            })

        # Detect alpha channel issues (semi-transparent edges)
        if img_pil.mode == "RGBA":
            alpha = np.array(img_pil.split()[3])
            edge_alpha = alpha[:10, :].flatten().tolist() + alpha[-10:, :].flatten().tolist() + alpha[:, :10].flatten().tolist() + alpha[:, -10:].flatten().tolist()
            non_255 = [v for v in edge_alpha if v != 255]
            if non_255 and len(non_255) / len(edge_alpha) > 0.1:
                issues.append({
                    "category": "Image",
                    "severity": "medium",
                    "problem": "Semi-transparent edges detected on RGBA image. Edge pixels are not fully opaque.",
                    "impact": "When placed on non-white backgrounds, faint halos or unexpected transparency appears around design edges.",
                    "suggestion": "Flatten transparency: set alpha to 255 on all edge pixels, or export as RGB (no alpha) if transparency is not needed.",
                    "confidence": 0.85,
                    "detected_value": f"{len(non_255)} edge pixels with alpha < 255",
                    "expected_value": "All edge pixels alpha = 255 (fully opaque)",
                })

    except Exception as e:
        issues.append({
            "category": "Image",
            "severity": "medium",
            "problem": "Image forensics module failed.",
            "impact": "Compression/EXIF/deep artifact checks were incomplete.",
            "suggestion": "Retry with a standard PNG/JPG export and verify image integrity.",
            "confidence": 0.95,
            "detected_value": str(e)[:160],
        })
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 10 — Advanced Color Palette Analysis
# ══════════════════════════════════════════════════════════════════════════════
def _check_color_palette(img_pil, w, h):
    issues = []
    try:
        import collections
        # Quantize to 10 prominent colors
        small = img_pil.resize((150, 150), Image.Resampling.BILINEAR)
        quantized = small.quantize(colors=10, method=Image.MEDIANCUT)
        palette = quantized.getpalette()[:30]  # first 10 colors, 3 values each
        colors = []
        for i in range(10):
            r, g, b = palette[i*3], palette[i*3+1], palette[i*3+2]
            if r or g or b:
                colors.append((r, g, b))

        # Check for too many distinct colors (>15 in a small image = noisy palette)
        if len(colors) > 8:
            issues.append({
                "category": "Color",
                "severity": "low",
                "problem": f"Color palette has {len(colors)} distinct prominent colors. Recommended maximum is 5-6 for brand consistency.",
                "impact": "Too many colors create visual noise and weaken brand identity recognition.",
                "suggestion": "Reduce to a maximum of 5-6 colors: 1-2 primaries, 1-2 secondaries, 1-2 neutrals. Use tints/shades of the same hue.",
                "confidence": 0.60,
                "detected_value": f"{len(colors)} prominent colors",
                "expected_value": "≤ 6 prominent colors for brand consistency",
            })

        # Detect near-duplicate colors (humans miss this)
        near_dupes = []
        for i, c1 in enumerate(colors):
            for j, c2 in enumerate(colors[i+1:], i+1):
                dist = math.sqrt((c1[0]-c2[0])**2 + (c1[1]-c2[1])**2 + (c1[2]-c2[2])**2)
                if 5 < dist < 30:  # Very similar but not identical
                    near_dupes.append((c1, c2, round(dist, 1)))
        if near_dupes:
            examples = "; ".join([f"RGB{c1} ≈ RGB{c2} (ΔE~{d})" for c1, c2, d in near_dupes[:3]])
            issues.append({
                "category": "Color",
                "severity": "medium",
                "problem": f"{len(near_dupes)} near-duplicate color(s) detected. Colors are visually indistinguishable but defined separately.",
                "impact": "Wastes palette slots on redundant colors; causes subtle inconsistency when one variant is used in some places and the other elsewhere.",
                "suggestion": "Consolidate near-duplicate colors into a single hex value. Use opacity/tints if variation is needed.",
                "confidence": 0.75,
                "detected_value": examples,
                "expected_value": "All palette colors have ΔE > 30 (visually distinct)",
            })

        # Detect pure black (#000000) or pure white (#FFFFFF) usage
        pure_black = sum(1 for c in colors if c == (0, 0, 0))
        pure_white = sum(1 for c in colors if c == (255, 255, 255))
        if pure_black:
            issues.append({
                "category": "Color",
                "severity": "low",
                "problem": "Pure black (#000000) detected in palette. Pure black rarely exists in real-world printing/display.",
                "impact": "Pure black can appear unnaturally harsh on screens and may not print as expected (overprints).",
                "suggestion": "Use near-black like #121212 or #1a1a1a for a more natural, rich dark tone.",
                "confidence": 0.80,
                "detected_value": "#000000",
                "expected_value": "Near-black e.g. #121212 or #1a1a1a",
            })

    except Exception as e:
        issues.append({
            "category": "Color",
            "severity": "medium",
            "problem": "Color palette module failed.",
            "impact": "Palette consistency checks were incomplete.",
            "suggestion": "Retry the analysis. If issue persists, use a non-corrupted RGB image.",
            "confidence": 0.95,
            "detected_value": str(e)[:160],
        })
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 11 — Edge & Contour Precision Analysis
# ══════════════════════════════════════════════════════════════════════════════
def _check_edge_precision(img_cv, w, h):
    issues = []
    try:
        small = _downscale_cv(img_cv, 600)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # Detect jagged/aliased edges (human eyes miss this on small screens)
        edges = cv2.Canny(gray, 50, 150)
        # Count diagonal edge pixels (aliasing indicator)
        diag_kernel = np.array([[1,0],[0,1]])  # Diagonal pattern
        diag_count = cv2.filter2D(edges.astype(np.float32), -1, diag_kernel)
        aliased_pixels = int(np.sum(diag_count > 1))

        total_edge = int(np.sum(edges > 0))
        if total_edge > 0 and aliased_pixels / total_edge > 0.15:
            issues.append({
                "category": "Image",
                "severity": "medium",
                "problem": f"Aliased/jagged edges detected: {aliased_pixels} diagonal edge pixels out of {total_edge} total edges.",
                "impact": "Diagonal lines and curves appear stair-stepped (jagged) instead of smooth, especially visible on high-DPI displays.",
                "suggestion": "Enable anti-aliasing in design export settings. Use vector formats (SVG) for graphics with diagonal lines or text.",
                "confidence": 0.70,
                "detected_value": f"{aliased_pixels}/{total_edge} aliased edge pixels ({100*aliased_pixels/total_edge:.1f}%)",
                "expected_value": "< 10% diagonal edge pixels (smooth anti-aliased edges)",
            })

        # Detect thin lines (< 2px) that may disappear when scaled
        lines_kernel_h = np.ones((1, 20), np.uint8)
        lines_kernel_v = np.ones((20, 1), np.uint8)
        dilated_h = cv2.dilate(edges, lines_kernel_h, iterations=1)
        dilated_v = cv2.dilate(edges, lines_kernel_v, iterations=1)
        thin_lines_h = int(np.sum((edges > 0) & (dilated_h == 0)))
        thin_lines_v = int(np.sum((edges > 0) & (dilated_v == 0)))
        thin_total = thin_lines_h + thin_lines_v
        if thin_total > 50:
            issues.append({
                "category": "Layout",
                "severity": "medium",
                "problem": f"Very thin elements detected: ~{thin_total} edge pixels form lines < 2px thick. May disappear when scaled or printed.",
                "impact": "Thin lines (< 2px) become invisible at small display sizes or when printed at reduced scale.",
                "suggestion": "Ensure all decorative lines, borders, and strokes are at minimum 2px (preferably 3px) thick at target display size.",
                "confidence": 0.75,
                "detected_value": f"~{thin_total} sub-2px edge pixels",
                "expected_value": "All visible lines ≥ 2px thick at displayed resolution",
            })

    except Exception as e:
        issues.append({
            "category": "Image",
            "severity": "medium",
            "problem": "Edge precision module failed.",
            "impact": "Aliasing and thin-line checks were incomplete.",
            "suggestion": "Retry with a clean source export.",
            "confidence": 0.95,
            "detected_value": str(e)[:160],
        })
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 12 — Perceptual Duplicate / Overlap Detection
# ══════════════════════════════════════════════════════════════════════════════
def _check_duplicates_and_overlaps(img_cv, w, h):
    issues = []
    try:
        small = _downscale_cv(img_cv, 400)
        sh, sw = small.shape[:2]
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = sw * sh * 0.005
        bboxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > min_area]

        # Detect overlapping bounding boxes (human-missed layering issues)
        overlaps = 0
        for i in range(len(bboxes)):
            for j in range(i + 1, len(bboxes)):
                x1, y1, w1, h1 = bboxes[i]
                x2, y2, w2, h2 = bboxes[j]
                # Check intersection
                ix = max(0, min(x1+w1, x2+w2) - max(x1, x2))
                iy = max(0, min(y1+h1, y2+h2) - max(y1, y2))
                if ix > 0 and iy > 0:
                    overlap_area = ix * iy
                    area1 = w1 * h1
                    if area1 > 0 and overlap_area / area1 > 0.3:
                        overlaps += 1

        if overlaps >= 2:
            issues.append({
                "category": "Layout",
                "severity": "medium",
                "problem": f"{overlaps} overlapping elements detected. Elements may be accidentally layered or misaligned.",
                "impact": "Overlapping elements cause visual confusion and may indicate accidental duplication or z-index/layering errors in the design file.",
                "suggestion": "Review layer order in design file. Ensure elements are intentionally overlapping or adjust positioning. Check for accidentally duplicated elements.",
                "confidence": 0.65,
                "detected_value": f"{overlaps} overlapping element pairs",
                "expected_value": "0 overlapping elements (unless intentionally designed)",
            })

        # Perceptual hash for near-duplicate regions (catches copy-paste errors)
        if len(bboxes) >= 4:
            regions = []
            for bx, by, bw, bh in bboxes[:10]:
                x1 = max(0, bx)
                y1 = max(0, by)
                x2 = min(sw, x1 + bw)
                y2 = min(sh, y1 + bh)
                if x2 > x1 and y2 > y1:
                    region = gray[y1:y2, x1:x2]
                    if region.size > 100:
                        region = cv2.resize(region, (32, 32), interpolation=cv2.INTER_AREA)
                        # Simple perceptual hash: top-left vs bottom-right average
                        tl = int(np.mean(region[:16, :16]))
                        br = int(np.mean(region[16:, 16:]))
                        regions.append((bx, by, tl, br))

            dupes = 0
            for i in range(len(regions)):
                for j in range(i+1, len(regions)):
                    _, _, tl1, br1 = regions[i]
                    _, _, tl2, br2 = regions[j]
                    diff = abs(tl1 - tl2) + abs(br1 - br2)
                    if diff < 20:
                        dupes += 1
            if dupes >= 2:
                issues.append({
                    "category": "Layout",
                    "severity": "medium",
                    "problem": f"~{dupes} potentially duplicate elements detected. Visually similar elements may be copy-paste errors.",
                    "impact": "Accidentally duplicated elements cause layout inconsistencies and waste canvas space. Often missed during manual review.",
                    "suggestion": "Visually inspect duplicated regions. Remove accidental duplicates. Ensure repeated elements (like icons) are intentionally placed.",
                    "confidence": 0.55,
                    "detected_value": f"~{dupes} near-duplicate regions detected",
                    "expected_value": "No accidental duplicate elements",
                })

    except Exception as e:
        issues.append({
            "category": "Layout",
            "severity": "medium",
            "problem": "Duplicate/overlap module failed.",
            "impact": "Potential layering conflict detection was incomplete.",
            "suggestion": "Retry analysis and validate image readability.",
            "confidence": 0.95,
            "detected_value": str(e)[:160],
        })
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 13 — Advanced Typography: Spelling, Grammar, Locale
# ══════════════════════════════════════════════════════════════════════════════
def _check_spelling_and_locale(raw_text):
    issues = []
    if not raw_text or len(raw_text.strip()) < 3:
        return issues

    try:
        # Spelling check (requires pyspellchecker)
        if SPELL_OK and _spell:
            words = re.findall(r"\b[a-zA-Z]{3,}\b", raw_text)
            if words:
                # Filter out common design/tech terms that aren't in dictionary
                common_terms = {"ui", "ux", "cta", "rgb", "hex", "png", "jpg", "svg", "api",
                                "ios", "android", "webp", "figma", "sketch", "jpeg", "gif",
                                "app", "apps", "url", "urls", "seo", "https", "http", "www"}
                filtered = [w.lower() for w in words if w.lower() not in common_terms]
                if filtered:
                    misspelled = _spell.unknown(filtered)
                    # Limit to first 10 to avoid noise
                    misspelled = list(misspelled)[:10]
                    if misspelled:
                        examples = ", ".join(list(misspelled)[:5])
                        issues.append({
                            "category": "Typography",
                            "severity": "high",
                            "problem": f"Possible spelling errors detected: {examples}.",
                            "impact": "Typos in published designs damage brand credibility and appear unprofessional to clients and users.",
                            "suggestion": f"Proofread and correct the flagged words: {examples}. Run a full spell-check in the design file before export.",
                            "confidence": 0.70,
                            "detected_value": f"Misspelled: {examples}",
                            "expected_value": "All text spelled correctly per target locale dictionary",
                        })

        # Detect mixed case inconsistencies (e.g. "iPhone" vs "Iphone")
        words = re.findall(r"\b[a-zA-Z]{2,}\b", raw_text)
        case_issues = []
        seen_words = {}
        for w in words:
            lower = w.lower()
            if lower in seen_words and seen_words[lower] != w:
                case_issues.append(f"{seen_words[lower]} / {w}")
            seen_words[lower] = w
        if case_issues:
            examples = "; ".join(case_issues[:3])
            issues.append({
                "category": "Typography",
                "severity": "medium",
                "problem": f"Inconsistent capitalization detected: {examples}.",
                "impact": "Same word appearing with different capitalization looks like a typo and weakens brand consistency.",
                "suggestion": "Standardize capitalization of brand names, product names, and headings throughout the design.",
                "confidence": 0.80,
                "detected_value": examples,
                "expected_value": "Consistent capitalization for all repeated words",
            })

        # Detect repeated words (stutters: "the the", "and and")
        lower_text = raw_text.lower()
        repeats = re.findall(r"\b(\w+)\s+\1\b", lower_text)
        if repeats:
            unique_repeats = list(set(repeats))[:5]
            issues.append({
                "category": "Typography",
                "severity": "medium",
                "problem": f"Repeated/stuttered words detected: {', '.join(unique_repeats)}. Likely a typing error.",
                "impact": "Word repetitions ('the the', 'and and') are proofreading errors that damage professionalism.",
                "suggestion": f"Remove duplicate words: {' ,'.join(unique_repeats)}. Proofread text content carefully.",
                "confidence": 0.90,
                "detected_value": f"Stuttered words: {', '.join(unique_repeats)}",
                "expected_value": "No repeated adjacent words",
            })

    except Exception as e:
        issues.append({
            "category": "Typography",
            "severity": "medium",
            "problem": "Spelling/locale module failed.",
            "impact": "Typos and casing checks were incomplete.",
            "suggestion": "Retry after OCR text quality improves.",
            "confidence": 0.95,
            "detected_value": str(e)[:160],
        })
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# MODULE 14 — Brightness / Exposure Analysis (Micro-check)
# ══════════════════════════════════════════════════════════════════════════════
def _check_exposure(img_pil, requirements):
    issues = []
    try:
        arr = np.array(_downscale_pil(img_pil, 400))
        # Per-channel analysis
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        avg_r, avg_g, avg_b = float(np.mean(r)), float(np.mean(g)), float(np.mean(b))

        # Check for overexposure (any channel clipped near 255)
        clipped_pixels = int(np.sum((r > 250) | (g > 250) | (b > 250)))
        total_pixels = arr.shape[0] * arr.shape[1]
        clip_pct = (clipped_pixels / total_pixels) * 100

        if clip_pct > 5:
            issues.append({
                "category": "Image",
                "severity": "medium",
                "problem": f"Overexposed: {clip_pct:.1f}% of pixels have a channel value > 250. Highlight detail is clipped.",
                "impact": "Overexposed areas lose all texture and detail. White areas cannot be recovered in print or on other displays.",
                "suggestion": "Reduce exposure/brightness in photo editing. Recover highlight detail or re-shoot with proper exposure.",
                "confidence": 0.85,
                "detected_value": f"{clip_pct:.1f}% clipped pixels (value > 250)",
                "expected_value": "< 1% pixels with any channel > 250",
            })

        # Check for underexposure (any channel clipped near 0)
        dark_pixels = int(np.sum((r < 5) | (g < 5) | (b < 5)))
        dark_pct = (dark_pixels / total_pixels) * 100

        if dark_pct > 10:
            issues.append({
                "category": "Image",
                "severity": "medium",
                "problem": f"Underexposed: {dark_pct:.1f}% of pixels have a channel value < 5. Shadow detail is crushed.",
                "impact": "Underexposed areas appear as flat black with no visible detail, making the design feel heavy and murky.",
                "suggestion": "Increase exposure or lift shadows in photo editing. Aim for a minimum pixel value of 15-20 in shadow areas.",
                "confidence": 0.85,
                "detected_value": f"{dark_pct:.1f}% crushed shadow pixels (value < 5)",
                "expected_value": "< 3% pixels with any channel < 5",
            })

        # Check for color cast (one channel significantly different)
        avg_all = (avg_r + avg_g + avg_b) / 3
        max_deviation = max(abs(avg_r - avg_all), abs(avg_g - avg_all), abs(avg_b - avg_all))
        if max_deviation > 30:
            dominant = "Red" if avg_r == max(avg_r, avg_g, avg_b) else "Green" if avg_g == max(avg_r, avg_g, avg_b) else "Blue"
            issues.append({
                "category": "Color",
                "severity": "low",
                "problem": f"Color cast detected: {dominant} channel dominance. R={avg_r:.0f}, G={avg_g:.0f}, B={avg_b:.0f}.",
                "impact": "Unintended color cast makes whites appear tinted and affects color accuracy of all design elements.",
                "suggestion": f"Apply white balance correction to neutralize the {dominant.lower()} cast. Use a gray card reference if available.",
                "confidence": 0.70,
                "detected_value": f"R={avg_r:.0f}, G={avg_g:.0f}, B={avg_b:.0f} (Δ={max_deviation:.0f})",
                "expected_value": "Balanced channels: R≈G≈B for neutral areas (deviation < 15)",
            })

    except Exception as e:
        issues.append({
            "category": "Image",
            "severity": "medium",
            "problem": "Exposure module failed.",
            "impact": "Brightness and clipping checks were incomplete.",
            "suggestion": "Retry with a standard export profile (sRGB).",
            "confidence": 0.95,
            "detected_value": str(e)[:160],
        })
    return issues


def _parse_selected_modules(selected_modules):
    if not selected_modules or selected_modules.lower() == "all":
        return list(MODULE_DEFS.keys())
    requested = [m.strip() for m in selected_modules.split(",") if m.strip()]
    if "all" in requested:
        return list(MODULE_DEFS.keys())
    valid = [m for m in requested if m in MODULE_DEFS]
    return valid or list(MODULE_DEFS.keys())


def _requirements_coverage(requirements, selected):
    req = requirements.lower()
    asked = {}
    for module, words in REQUIREMENT_KEYWORDS.items():
        hits = [w for w in words if w in req]
        if hits:
            asked[module] = hits
    matched = [m for m in asked if m in selected]
    missing = [m for m in asked if m not in selected]
    return {
        "requested_topics": {MODULE_DEFS[k]: v for k, v in asked.items()},
        "covered_modules": [MODULE_DEFS[m] for m in matched],
        "missing_modules": [MODULE_DEFS[m] for m in missing],
    }


def _extract_video_frames(content, max_frames=3):
    tmp_name = f"video_{uuid.uuid4().hex[:8]}.tmp"
    tmp_path = os.path.join(UPLOAD_DIR, tmp_name)
    with open(tmp_path, "wb") as f:
        f.write(content)
    frames = []
    cap = cv2.VideoCapture(tmp_path)
    if not cap.isOpened():
        cap.release()
        os.remove(tmp_path)
        raise RuntimeError("Could not open video")
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    positions = [0]
    if count > 2:
        positions = [0, count // 2, max(0, count - 1)]
    for pos in positions[:max_frames]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        ok, frame = cap.read()
        if ok and frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(frame_rgb))
    cap.release()
    os.remove(tmp_path)
    if not frames:
        raise RuntimeError("No readable frames extracted")
    return frames


def _extract_pdf_pages(content, max_pages=3):
    if not PDFIUM_OK:
        raise RuntimeError("PDF support unavailable. Install pypdfium2.")
    pages = []
    pdf = pdfium.PdfDocument(io.BytesIO(content))
    total = len(pdf)
    picks = [0]
    if total > 2:
        picks = [0, total // 2, total - 1]
    for idx in picks[:max_pages]:
        page = pdf[idx]
        bitmap = page.render(scale=1.5)
        arr = bitmap.to_numpy()
        if arr.shape[2] == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGRA2RGB)
        else:
            arr = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
        pages.append(Image.fromarray(arr))
    if not pages:
        raise RuntimeError("No readable pages extracted from PDF")
    return pages


def _analyze_single_image(img_src, requirements, selected_modules, file_path, save_grayscale=False):
    img_pil = img_src.convert("RGB")
    w, h = img_pil.size
    img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)

    gs_filename = None
    if save_grayscale:
        gs_filename = f"grayscale_{uuid.uuid4().hex[:6]}.png"
        gs_path = os.path.join(UPLOAD_DIR, gs_filename)
        img_pil.convert("L").save(gs_path)

    tasks = {}
    modules_status = {}
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=8) as pool:
        if "image_quality" in selected_modules:
            tasks["image_quality"] = pool.submit(_check_image_quality, img_cv, w, h)
        if "layout" in selected_modules:
            tasks["layout"] = pool.submit(_check_layout, img_cv, w, h)
        if "color_contrast" in selected_modules:
            tasks["color_contrast"] = pool.submit(_check_color_contrast, img_pil, w, h)
        if "typography_ocr" in selected_modules:
            tasks["typography_ocr"] = pool.submit(_check_typography_and_extract_text, img_pil)
        if "density" in selected_modules:
            tasks["density"] = pool.submit(_check_density, img_cv, w, h)
        if "image_forensics" in selected_modules:
            tasks["image_forensics"] = pool.submit(_check_image_forensics, img_src, img_cv, file_path, w, h)
        if "color_palette" in selected_modules:
            tasks["color_palette"] = pool.submit(_check_color_palette, img_pil, w, h)
        if "edge_precision" in selected_modules:
            tasks["edge_precision"] = pool.submit(_check_edge_precision, img_cv, w, h)
        if "duplicates_overlaps" in selected_modules:
            tasks["duplicates_overlaps"] = pool.submit(_check_duplicates_and_overlaps, img_cv, w, h)
        if "exposure_analysis" in selected_modules:
            tasks["exposure_analysis"] = pool.submit(_check_exposure, img_pil, requirements)

    results = {}
    for module in MODULE_DEFS:
        if module not in selected_modules:
            modules_status[module] = {"status": "skipped", "reason": "not_selected"}
            continue
        if module not in tasks:
            modules_status[module] = {"status": "skipped", "reason": "no_task"}
            continue
        try:
            results[module] = tasks[module].result()
            modules_status[module] = {"status": "ok"}
        except Exception as e:
            modules_status[module] = {"status": "failed", "reason": str(e)[:160]}
            results[module] = []

    q_issues, lap_var = results.get("image_quality", ([], 0))
    l_issues, fmt, n_elements = results.get("layout", ([], "Unknown", 0))
    c_issues, avg_lum = results.get("color_contrast", ([], 0))
    t_issues, raw_text, heights = results.get("typography_ocr", ([], "", []))
    d_issues, density = results.get("density", ([], 0))
    f_issues = results.get("image_forensics", [])
    p_issues = results.get("color_palette", [])
    e_issues = results.get("edge_precision", [])
    dup_issues = results.get("duplicates_overlaps", [])
    exp_issues = results.get("exposure_analysis", [])

    if "cta_detection" in selected_modules:
        cta_found = _check_cta(raw_text)
        modules_status["cta_detection"] = {"status": "ok"}
    else:
        cta_found = []
        modules_status["cta_detection"] = {"status": "skipped", "reason": "not_selected"}

    if "visual_hierarchy" in selected_modules:
        h_issues = _check_visual_hierarchy(img_cv, w, h, cta_found, bool(raw_text))
        modules_status["visual_hierarchy"] = {"status": "ok"}
    else:
        h_issues = []
        modules_status["visual_hierarchy"] = {"status": "skipped", "reason": "not_selected"}

    if "spelling_locale" in selected_modules:
        spell_issues = _check_spelling_and_locale(raw_text)
        modules_status["spelling_locale"] = {"status": "ok"}
    else:
        spell_issues = []
        modules_status["spelling_locale"] = {"status": "skipped", "reason": "not_selected"}

    elapsed = round(time.time() - t0, 2)
    all_issues = (q_issues + l_issues + c_issues + t_issues + d_issues +
                  h_issues + f_issues + p_issues + e_issues + dup_issues +
                  exp_issues + spell_issues)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_issues.sort(key=lambda x: severity_order.get(x["severity"], 3))
    all_issues = all_issues[:15]
    score = _score(all_issues)

    return {
        "issues": all_issues,
        "score": score,
        "summary": _summary(score, all_issues),
        "strengths": _strengths(fmt, w, h, lap_var, cta_found, density, bool(raw_text)),
        "quick_fixes": _quick_fixes(all_issues),
        "processed_file": gs_filename,
        "modules_status": modules_status,
        "meta": {
            "format": fmt,
            "resolution": f"{w}×{h}px",
            "sharpness": lap_var,
            "density": f"{density}%",
            "elements_detected": n_elements,
            "text_extracted": raw_text[:300] if raw_text else "(none — install Tesseract for OCR)",
            "cta_found": cta_found,
            "tesseract_active": TESSERACT_OK,
            "spellcheck_active": SPELL_OK,
            "analysis_time": f"{elapsed}s",
        },
    }


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
    selected_modules: str = Form("all"),
):
    ctype = file.content_type or ""
    is_image = ctype.startswith("image/")
    is_video = ctype.startswith("video/")
    is_pdf = ctype == "application/pdf"
    if not (is_image or is_video or is_pdf):
        return JSONResponse(status_code=400, content={"error": "Only image/video/pdf files are allowed"})

    content = await file.read()
    max_size = MAX_IMAGE_SIZE if is_image else MAX_VIDEO_SIZE if is_video else MAX_PDF_SIZE
    if len(content) > max_size:
        return JSONResponse(status_code=400, content={"error": f"File too large. Max allowed is {max_size // (1024 * 1024)}MB"})

    if not requirements.strip():
        return JSONResponse(status_code=400, content={"error": "Requirements are required"})

    selected = _parse_selected_modules(selected_modules)
    coverage = _requirements_coverage(requirements, selected)

    ext = os.path.splitext(file.filename)[1] or (".png" if is_image else ".mp4" if is_video else ".pdf")
    uid = uuid.uuid4().hex[:6]
    filename = f"design_{uid}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        media_results = []
        if is_image:
            src_img = Image.open(io.BytesIO(content))
            media_results.append(_analyze_single_image(src_img, requirements, selected, file_path, save_grayscale=True))
        elif is_video:
            frames = _extract_video_frames(content, max_frames=3)
            for frame in frames:
                media_results.append(_analyze_single_image(frame, requirements, selected, file_path, save_grayscale=False))
        else:
            pages = _extract_pdf_pages(content, max_pages=3)
            for page in pages:
                media_results.append(_analyze_single_image(page, requirements, selected, file_path, save_grayscale=False))
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Processing failed: {e}"})

    all_issues = []
    all_strengths = []
    all_quick_fixes = []
    modules_status = {}
    processed_file = None
    all_scores = []
    meta = {}
    for idx, res in enumerate(media_results):
        all_issues.extend(res["issues"])
        all_strengths.extend(res["strengths"])
        all_quick_fixes.extend(res["quick_fixes"])
        all_scores.append(res["score"])
        if idx == 0:
            processed_file = res.get("processed_file")
            meta = res["meta"]
        for key, val in res["modules_status"].items():
            if key not in modules_status or modules_status[key]["status"] != "failed":
                modules_status[key] = val

    severity_order = {"high": 0, "medium": 1, "low": 2}
    all_issues.sort(key=lambda x: severity_order.get(x["severity"], 3))
    all_issues = all_issues[:15]
    score = round(sum(all_scores) / len(all_scores)) if all_scores else _score(all_issues)

    return {
        "status": "success",
        "saved_file": filename,
        "processed_file": processed_file,
        "original_name": file.filename,
        "content_type": ctype,
        "requirements": requirements,
        "guidance": guidance,
        "score": score,
        "summary": _summary(score, all_issues),
        "issues": all_issues,
        "strengths": list(dict.fromkeys(all_strengths))[:6],
        "quick_fixes": list(dict.fromkeys(all_quick_fixes))[:5],
        "requirements_coverage": coverage,
        "module_status": modules_status,
        "meta": {
            **meta,
            "samples_analyzed": len(media_results),
            "modules_requested": selected,
            "modules_run": [k for k, v in modules_status.items() if v.get("status") == "ok"],
            "modules_failed": [k for k, v in modules_status.items() if v.get("status") == "failed"],
        },
    }
