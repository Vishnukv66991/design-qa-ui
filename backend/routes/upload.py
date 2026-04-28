from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
import uuid
from PIL import Image, ImageStat

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

def analyze_image(image_path: str, requirements: str) -> list:
    """Image QA checks for requirements"""
    issues = []
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            
            # Resolution check
            if width < 1000 or height < 1000:
                issues.append(f"⚠️ Low resolution: {width}x{height}px (recommended ≥1000x1000)")
            
            # Aspect ratio check
            aspect = round(width / height, 2)
            if 0.99 <= aspect <= 1.01:
                format_type = "Square (1:1) - Instagram Post"
            elif 0.56 <= aspect <= 0.62:
                format_type = "Vertical (9:16) - Instagram Story"
            else:
                issues.append(f"⚠️ Unusual aspect ratio: {aspect} (common: 1:1 or 9:16)")
            
            # Brightness/theme check
            if img.mode == 'RGB':
                stat = ImageStat.Stat(img)
                brightness = sum(stat.mean) / 3
                if "neon" in requirements.lower() or "dark" in requirements.lower():
                    if brightness > 150:
                        issues.append("⚠️ Expected dark/neon theme but image is too bright")
            
            issues.append(f"✓ Format: {format_type}")
            issues.append(f"✓ Size: {width}x{height}px")
    except Exception as e:
        issues.append(f"❌ Analysis failed: {str(e)}")
    return issues

@router.post("/analyze")
async def upload_file(
    file: UploadFile = File(...),
    requirements: str = Form(...),
    guidance: str = Form(None)
):
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        return JSONResponse(status_code=400, content={"error": "Only image files allowed"})
    
    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        return JSONResponse(status_code=400, content={"error": "File size exceeds 10MB limit"})
    
    # Validate requirements
    if not requirements.strip():
        return JSONResponse(status_code=400, content={"error": "Requirements are required"})
    
    # Save as uploads/design123.png (6-char unique ID)
    file_ext = os.path.splitext(file.filename)[1] or ".png"
    unique_id = uuid.uuid4().hex[:6]  # e.g., 1a2b3c
    filename = f"design_{unique_id}{file_ext}"  # e.g., design_1a2b3c.png
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Save original image
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Convert to grayscale
    processed_filename = f"grayscale_{unique_id}{file_ext}"
    processed_path = os.path.join(UPLOAD_DIR, processed_filename)
    try:
        Image.open(file_path).convert("L").save(processed_path)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Processing failed: {str(e)}"})
    
    # Analyze image
    issues = analyze_image(file_path, requirements)
    
    # Return response
    return {
        "status": "success",
        "message": "File uploaded and analyzed successfully",
        "saved_file": filename,  # e.g., design_1a2b3c.png
        "processed_file": processed_filename,
        "original_name": file.filename,
        "requirements": requirements,
        "guidance": guidance,
        "issues": issues or ["✓ No major issues found"]
    }
