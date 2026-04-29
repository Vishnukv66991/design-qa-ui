# Design QA Tool — Complete Project Walkthrough

---

## 1. What Is This Project?

**Design QA Tool** is an internal quality-checking tool for designers and developers.

> Imagine a designer creates a social media banner. Before sending it to the client, someone needs to verify: Is the resolution high enough? Is the aspect ratio correct (1:1 for Instagram)? Does it follow a dark/neon theme as requested? Doing this manually is slow. This tool automates it.

### Where Would You Use This?

| Scenario | How the tool helps |
|----------|-------------------|
| Freelance designer | Verify client designs before delivery |
| Design agency | QA check before handing work to clients |
| Social media team | Ensure images meet platform specs (1:1, 9:16) |
| Dev team internal review | Automated sanity check for UI screenshots |

**It is NOT a public website.** It is a tool that runs on your own machine (or internal server). That's why it's called a "tool" — like Figma, Photoshop, VS Code. You open it, do your work, close it.

---

## 2. The Big Picture — How It's Built

```
┌─────────────────────────────────────────────────────┐
│                   YOUR BROWSER                       │
│  http://localhost:3000  (React Frontend)             │
│                                                      │
│  ┌──────────┐  ┌─────────────┐  ┌───────────────┐   │
│  │UploadBox │  │Requirements │  │  ModelGuidance│   │
│  └──────────┘  └─────────────┘  └───────────────┘   │
│           ↓ user clicks "Run Analysis"               │
│  ┌─────────────────────────────────────────────┐     │
│  │     Dashboard.jsx  →  fetch("/analyze")     │     │
│  └─────────────────────────────────────────────┘     │
└───────────────────────┬─────────────────────────────┘
                        │ HTTP POST (image + text)
                        ↓
┌─────────────────────────────────────────────────────┐
│         FastAPI BACKEND  (http://localhost:8000)     │
│                                                      │
│  main.py  →  routes/upload.py  →  analyze_image()   │
│                      ↓                               │
│           Checks resolution, aspect ratio,           │
│           brightness, saves grayscale copy           │
│                      ↓                               │
│         Returns JSON { issues: [...] }               │
└─────────────────────────────────────────────────────┘
```

**Two completely separate programs talk to each other over HTTP (like a website talks to a server).**

---

## 3. Technology Choices — Why Each Was Used

| Technology | Why it's here |
|------------|--------------|
| **React** | Builds the interactive UI. When you upload a file or see results, React updates only what changed — no page reload needed |
| **FastAPI (Python)** | Handles image processing. Python has the best image libraries (Pillow). FastAPI is fast and simple to write |
| **Pillow (PIL)** | Python library for reading and manipulating images — checks pixel dimensions, converts to grayscale |
| **concurrently** | npm package that lets one `npm start` launch both React AND FastAPI at the same time |
| **CRA Proxy** | Tells React's dev server: "if you get a request for `/analyze`, forward it to `localhost:8000`" — so the URL works on any machine |
| **Uvicorn** | The server that runs FastAPI (like Apache/Nginx but for Python async apps) |

---

## 4. File-by-File Explanation

### 📁 Root Level

#### `package.json`
The "control panel" for the entire frontend project.

```json
"proxy": "http://localhost:8000"
```
> **Why:** When React code calls `fetch("/analyze")`, the browser would try to fetch from `localhost:3000/analyze` (wrong). The proxy intercepts it and sends it to `localhost:8000/analyze` (correct backend). This is what makes the project work on any machine — no hardcoded IPs.

```json
"start": "concurrently ... \"react-scripts start\" \"node scripts/start-backend.js\""
```
> **Why:** Runs both the frontend AND backend with a single `npm start` command.

---

#### `scripts/start-backend.js`
A small helper script (Node.js) that:
1. Figures out the path to the `backend/` folder
2. Runs `uvicorn main:app --reload` inside that folder

```js
const uvicorn = spawn('uvicorn', ['main:app', '--reload', '--port', '8000'], {
  cwd: backendDir,   // ← changes into the backend folder first
  shell: true,
});
```
> **Why a separate script?** In PowerShell (Windows), `cd backend && uvicorn ...` doesn't work. A Node.js script is cross-platform — works on Windows, Mac, Linux.

---

### 📁 `backend/`

#### `backend/main.py`
The entry point for the FastAPI application.

```python
app = FastAPI()

# CORS — allows the browser (port 3000) to talk to the server (port 8000)
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Serves the uploads/ folder as a static file directory
# So /uploads/design_abc123.png actually returns the image file
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Registers all routes from upload.py (the /analyze endpoint)
app.include_router(upload_router)
```

> **CORS** = Cross-Origin Resource Sharing. Browsers block requests from one "origin" (port 3000) to another (port 8000) by default. This middleware tells the browser: "it's OK, I allow it."

---

#### `backend/routes/upload.py`
The heart of the backend — contains two things:

**① `analyze_image(image_path, requirements)` function**

This is the QA engine. It opens the image with Pillow and runs checks:

```python
# Check 1: Resolution
if width < 1000 or height < 1000:
    issues.append("⚠️ Low resolution: ...")

# Check 2: Aspect ratio
format_type = "Unknown"          # ← always initialized (our bug fix)
if 0.99 <= aspect <= 1.01:
    format_type = "Square (1:1)"
elif 0.56 <= aspect <= 0.62:
    format_type = "Vertical (9:16)"
else:
    format_type = f"Custom ({aspect}:1)"
    issues.append("⚠️ Unusual aspect ratio...")

# Check 3: Brightness (only if requirements mention "dark" or "neon")
if "neon" in requirements.lower() or "dark" in requirements.lower():
    brightness = sum(stat.mean) / 3
    if brightness > 150:
        issues.append("⚠️ Expected dark/neon theme but image is too bright")
```

**② `POST /analyze` endpoint**

This is what runs when you click "Run Analysis":

```
Step 1: Validate the file (is it an image? under 10MB?)
Step 2: Save the original image → uploads/design_abc123.png
Step 3: Convert to grayscale → uploads/grayscale_abc123.png
Step 4: Run analyze_image() → get list of issues
Step 5: Return JSON with all results
```

---

#### `backend/requirements.txt`
Lists the Python packages needed:
```
fastapi        ← the web framework
uvicorn        ← the server that runs fastapi
python-multipart ← needed to receive file uploads in FastAPI
Pillow         ← image processing library
```
> Anyone who clones your project runs `pip install -r requirements.txt` and gets everything needed automatically.

---

### 📁 `src/` (React Frontend)

#### `src/index.js`
The very first file React runs. It mounts the entire app into the `<div id="root">` in `public/index.html`.

```js
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
```
> You never need to touch this file.

---

#### `src/App.js`
A simple pass-through. Just renders `<Dashboard />`.

```js
function App() {
  return <Dashboard />;
}
```
> **Why have App.js at all?** In bigger apps, you'd add routing here (`<Route path="/settings" ... />`). It's kept for future growth.

---

#### `src/index.css`
The design system for the whole tool. Uses **CSS Custom Properties** (variables):

```css
:root {
  --bg-base:     #0f1117;   /* darkest background */
  --bg-panel:    #1a1d27;   /* sidebar color */
  --accent:      #6c63ff;   /* purple highlight */
  --pass:        #22c55e;   /* green for ✓ items */
  --warn:        #f59e0b;   /* amber for ⚠ items */
  --fail:        #ef4444;   /* red for ❌ items */
}
```

> **Why custom properties?** Change `--accent` once and every button, border, and glow updates. No hunting through 20 files.

---

#### `src/pages/Dashboard.jsx`
The main brain of the frontend. Manages all state and ties everything together.

**State variables (React `useState`):**

| State | What it holds |
|-------|--------------|
| `file` | The image File object the user selected |
| `requirements` | The text typed in the requirements box |
| `guidance` | The optional guidance text |
| `result` | The JSON response from the backend after analysis |
| `loading` | `true` while waiting for the backend (shows spinner) |
| `error` | Any error message to show inline |
| `originalPreview` | A local URL to show the original image side-by-side in results |

**`handleAnalyze()` — the most important function:**

```
1. Validate: file selected? requirements not empty?
2. Set loading = true (spinner appears, button disables)
3. Build FormData (how you send files over HTTP)
4. fetch("/analyze") ← relative URL, proxy sends to backend
5. If response.ok = false → read the JSON error body → show real message
6. If success → setResult(data) → ResultPanel renders
7. Finally → set loading = false (spinner disappears)
```

---

#### `src/components/UploadBox.jsx`
Handles file selection and preview.

**Key: Memory Leak Fix**

```js
const previewUrlRef = useRef(null);   // stores the current object URL

// When component unmounts OR new file chosen:
if (previewUrlRef.current) {
  URL.revokeObjectURL(previewUrlRef.current);  // ← release memory
}
```

> `URL.createObjectURL(file)` creates a temporary URL like `blob:http://localhost:3000/abc-123`. Every time you call it, the browser reserves memory. If you never `revokeObjectURL`, those reservations pile up forever — that's the memory leak. Our fix releases each old URL before creating a new one.

**Drag-and-drop support:**
```js
onDrop={(e) => {
  e.preventDefault();         // stop browser from opening the file
  processFile(e.dataTransfer.files[0]);  // process the dropped file
}}
```

---

#### `src/components/RequirementsInput.jsx`
A simple controlled textarea. "Controlled" means React owns the value:

```jsx
<textarea
  value={value}              // React controls what's shown
  onChange={(e) => setValue(e.target.value)}  // updates when user types
/>
```

> **Why controlled?** So `Dashboard.jsx` can read `requirements` at any time and send it to the backend.

---

#### `src/components/ModelGuidance.jsx`
Same pattern as RequirementsInput, but optional. Lets you tell the analyzer to "focus on" something specific (like typography).

---

#### `src/components/ResultPanel.jsx`
Displays the JSON returned by the backend.

**Issue color coding:**
```js
function getIssueClass(issue) {
  if (issue.startsWith("✓") || issue.startsWith("✅")) return "issue-item--pass";  // green
  if (issue.startsWith("⚠"))                           return "issue-item--warn";  // amber
  if (issue.startsWith("❌"))                           return "issue-item--fail";  // red
}
```

> The backend prefixes each issue with an emoji. The frontend reads that emoji to decide which color to use.

**Image URL fix:**
```jsx
// ❌ OLD — hardcoded, breaks on other machines:
<img src={`http://127.0.0.1:8000/uploads/${result.processed_file}`} />

// ✅ NEW — relative URL, works everywhere:
<img src={`/uploads/${result.processed_file}`} />
```

---

## 5. The Complete Data Flow — Step by Step

```
USER selects image + types requirements + clicks "Run Analysis"
        │
        ▼
Dashboard.jsx: handleAnalyze()
  → builds FormData { file, requirements, guidance }
  → fetch("/analyze", { method: "POST", body: formData })
        │
        │  (CRA proxy in package.json forwards this to localhost:8000)
        │
        ▼
FastAPI: POST /analyze  (backend/routes/upload.py)
  → validates file type (must be image/)
  → validates file size (must be < 10MB)
  → validates requirements (must not be empty)
  → saves file as uploads/design_abc123.png
  → converts to grayscale → uploads/grayscale_abc123.png
  → calls analyze_image():
      • checks resolution (width/height ≥ 1000px?)
      • checks aspect ratio (1:1? 9:16? custom?)
      • checks brightness (dark theme requirement met?)
  → returns JSON:
      {
        status: "success",
        original_name: "my-design.png",
        saved_file: "design_abc123.png",
        processed_file: "grayscale_abc123.png",
        issues: ["✓ Format: Square (1:1)", "⚠️ Low resolution: 800x800px"]
      }
        │
        ▼
Dashboard.jsx: setResult(data)
        │
        ▼
ResultPanel.jsx renders:
  → File info (name, saved as, status)
  → Requirements shown
  → Color-coded issue list
  → Side-by-side: Original | Grayscale image
```

---

## 6. Summary Table — Every File's Job

| File | Layer | Job |
|------|-------|-----|
| `package.json` | Config | Proxy, scripts, dependencies |
| `scripts/start-backend.js` | Dev tool | Starts FastAPI cross-platform |
| `backend/main.py` | Backend | App setup, CORS, static files |
| `backend/routes/upload.py` | Backend | Image upload + QA analysis |
| `backend/requirements.txt` | Config | Python package list |
| `src/index.js` | Frontend | Mounts React app |
| `src/App.js` | Frontend | Root component |
| `src/index.css` | Frontend | Design system (dark theme) |
| `src/pages/Dashboard.jsx` | Frontend | State, API calls, layout |
| `src/components/UploadBox.jsx` | Frontend | File picker + preview |
| `src/components/RequirementsInput.jsx` | Frontend | Text input for requirements |
| `src/components/ModelGuidance.jsx` | Frontend | Optional guidance text |
| `src/components/ResultPanel.jsx` | Frontend | Renders analysis results |
