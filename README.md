# Design QA Tool

A professional image QA analysis tool. Upload a design image, describe the requirements, and get instant feedback on resolution, aspect ratio, contrast, typography, and more.

---

## Quick Start (Any Device)

**Prerequisites:** [Node.js](https://nodejs.org/) + [Python 3.9+](https://www.python.org/downloads/) installed.

```bash
git clone https://github.com/YOUR_USERNAME/design-qa-ui.git
cd design-qa-ui
npm install       # installs React deps + auto-sets up Python backend
npm start         # starts everything — open http://localhost:3000
```

That's it. **Two commands.** Works on Windows, Mac, and Linux.

> **Optional:** Install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) for text detection and CTA analysis. The tool works without it — you just won't get typography/text-related checks.

---

## What Happens Under the Hood

```
npm install
  └→ installs node_modules
  └→ [postinstall] automatically:
       └→ creates backend/venv (Python virtual environment)
       └→ pip installs fastapi, uvicorn, opencv, pillow, etc.

npm start
  └→ starts React frontend at http://localhost:3000
  └→ starts FastAPI backend at http://localhost:8000 (from the venv)
  └→ proxy in package.json connects them
```

---

## How It Works

1. Upload a design image (PNG/JPG/WEBP, max 10 MB)
2. Enter client requirements (e.g. "dark neon theme, 1:1 aspect ratio")
3. Optionally add analysis guidance
4. Click **Run Analysis**
5. Get a professional QA report with score, issues, strengths, and quick fixes

### 8 Analysis Modules

| Module | What it checks |
|--------|---------------|
| Image Quality | Blur detection, resolution |
| Layout & Alignment | Aspect ratio, spacing consistency |
| Color & Contrast | WCAG 2.1 contrast ratios |
| Typography | Font size consistency (requires Tesseract) |
| Text Extraction | OCR text detection (requires Tesseract) |
| CTA Detection | Call-to-action keyword detection |
| Visual Hierarchy | Focal point, top-third analysis |
| Spacing & Density | Overcrowding / sparse layout |

---

## Project Structure

```
design-qa-ui/
├── backend/
│   ├── main.py             ← FastAPI app entry point
│   ├── routes/upload.py    ← 8-module analysis engine
│   ├── uploads/            ← Stored images (git-ignored)
│   └── requirements.txt    ← Python dependencies
├── scripts/
│   ├── setup-backend.js    ← Auto venv + pip install (runs on npm install)
│   └── start-backend.js    ← Auto-finds uvicorn in venv (runs on npm start)
├── src/
│   ├── components/         ← React UI components
│   ├── pages/Dashboard.jsx ← Main app page
│   └── index.css           ← Dark tool theme
└── package.json            ← proxy + scripts + postinstall hook
```

---

## Individual Commands

| Command | What it does |
|---------|-------------|
| `npm start` | Starts both frontend + backend |
| `npm run start:frontend` | React only |
| `npm run start:backend` | FastAPI only |
| `npm run build` | Production build |
| `npm test` | Run tests |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, Create React App |
| Backend | FastAPI, Uvicorn |
| Image Analysis | OpenCV, Pillow, NumPy |
| OCR (optional) | Tesseract via pytesseract |
| Styling | Vanilla CSS (Dark Theme) |
| Dev Tooling | concurrently, CRA proxy |
