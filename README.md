# BuildMind — Constraint-Aware Architecture Generator

BuildMind is a professional full-stack, AI-powered architectural planning studio and computational geometry platform for residential floor planning. It synthesizes preliminary CAD-compliant architectural layouts from user requirements, executes authoritative spatial validation using Python and Shapely, detects geometric conflicts (boundary breaches, setback encroachments, room polygon collisions, accessibility clearances, and dimensional thresholds), and iteratively repairs designs through an automated multi-cycle revision loop.

---

## 🏛️ Distinctive Architectural Studio Design

BuildMind features a custom visual identity inspired by high-end architectural studios, material selection ateliers, and digital drafting tables:
- **Warm Ivory & Paper White Surfaces** (`#FAF8F5`, `#FFFFFF`) for drafting canvas clarity.
- **Limestone, Sand & Beige Accents** (`#EFECE6`, `#DFD9CD`, `#F4EFE6`) for secondary interfaces.
- **Terracotta & Clay Red Accents** (`#C85A32`, `#E06D44`) for critical spatial focal points and conflict highlights.
- **Muted Olive & Sage Green Highlights** (`#6B8E23`, `#556B2F`) for successful geometric compliance badges.
- **Earthy Charcoal & Technical Ink** (`#201E1D`, `#3C3730`) for CAD annotations, dimension ticks, and title blocks.
- **Material Swatches**: White Oak Wood, Sand Limestone, Architectural Concrete, Terracotta Clay, and Polished Terrazzo.
- **Refined Typography**: Editorial architectural typography (*Cinzel*) paired with monospaced CAD measurement notation (*JetBrains Mono*).

---

## 🚀 Key Features

1. **Interactive 2D Floor Plan Canvas (SVG Drafting Table)**:
   - Dynamic CAD grid with fractional snapping (0.5 ft intervals).
   - Real-time zoom (35% to 350%) and panning with synchronized dimension axes.
   - Interactive room selection, boundary dragging, and 8-way resize handles with live dimension and area calculations.
   - Architectural symbols: Door swing arcs, exterior daylight windows, and internal staircase treads with direction arrows.
   - Ghosted Comparison Overlay mode: Visual diff comparing modified geometry against previous revisions.
   - Visual spatial violation highlighting with terracotta glow boundaries and conflict pills.

2. **Authoritative Python Geometry Engine (Shapely)**:
   - Modular spatial validation (`boundaries.py`, `overlaps.py`, `dimensions.py`, `accessibility.py`, `adjacencies.py`, `utilization.py`, `completeness.py`).
   - Boundary & Setbacks: Detects property line breaches and statutory front/rear/side setback encroachments.
   - Polygon Overlaps: Computes pairwise intersection areas and identifies exact collision coordinates.
   - Dimensions & Aspect Ratios: Enforces residential code minimums (e.g. bedrooms min 9×9 ft, bathrooms min 4.5×5.5 ft) and flags narrow tunnel proportions (>2.4:1).
   - Accessibility & Circulation: Verifies minimum passage clearances (3.0 ft, or 3.5 ft for wheelchair mode) and exterior window daylight access.
   - Space Utilization: Calculates gross built-up envelope, net usable carpet area, circulation ratio, and flags unusable residual voids.

3. **AI Generation, Deterministic Solver & Safe Auto-Fix Engine**:
   - Synthesizes 3 candidate design alternatives:
     - **Space Optimized**: High density, minimal circulation loss, open-plan living.
     - **Comfort Focused**: Acoustic buffers, private bedroom wings, formal dining.
     - **Budget Conscious**: Aligned column-beam grid, unified back-to-back plumbing wet walls.
   - **No-Regression Constraint-Aware Auto-Fix Engine**:
     - Evaluates proposed repairs on a separate candidate layout snapshot prior to committing.
     - Lexicographically ensures zero new hard-constraint violations, zero overlap area increases, and no dimensional collapse.
     - Detects cycles via layout state signatures and stops gracefully if infeasible.
     - Provides interactive "Preview Fix" banner with "Commit Fix" and "Discard", plus single-click "Undo Fix" and "Revalidate".
   - LLM Provider Abstraction: Pluggable support for Google Gemini, OpenAI GPT-4o, Anthropic Claude, and the built-in Deterministic Architectural Geometric Solver (Demo Mode).

4. **Contextual AI Design Copilot**:
   - Conversational studio assistant that understands site boundaries, room envelopes, and validation state.
   - Processes natural language modifications: "Widen kitchen by 2.5 ft", "Add another bedroom to rear", "Move bathroom closer", "Explain validation status".
   - Generates structured geometric modification previews with interactive diff summaries before applying.

5. **Architectural Room Schedule & Reporting**:
   - Full schedule table with dimensions, net areas, and material finish specifications.
   - Comprehensive metric breakdown: Site area, gross built-up, net carpet, ground coverage %, and projected budget range.
   - Print-ready PDF export via ReportLab, vector SVG export with title block, and JSON export.

6. **5-Step Visual Project Setup Wizard & Presets**:
   - Step 1: Site & Plot boundaries with dynamic dimensioned plot visualizer.
   - Step 2: Spatial program selector with architectural room cards.
   - Step 3: Design relationships (adjacencies, privacy levels, accessibility mode).
   - Step 4: Preferences, architectural style, and building code constraints.
   - Step 5: Polished architectural brief review and preset generator.
   - Includes 4 realistic presets: **25×40 ft Compact Urban Demo Home**, **35×50 ft Family Residence**, **30×45 ft Courtyard-Inspired Home**, and **18×50 ft Narrow Infill**.

---

## 🛠️ Project Architecture

```
buildmind ai/
├── backend/
│   ├── app/
│   │   ├── config.py              # Environment configuration & settings
│   │   ├── database.py            # SQLite / PostgreSQL SQLAlchemy database engine
│   │   ├── main.py                # FastAPI app entrypoint & demo project seeder
│   │   ├── models/                # SQLAlchemy ORM models (Project, Layout, Revision)
│   │   ├── schemas/               # Pydantic schemas (Geometry, Validation, Project, AI)
│   │   ├── geometry/              # Modular Shapely geometry validation engine
│   │   │   ├── engine.py          # Master GeometryValidationEngine orchestrator
│   │   │   ├── auto_fix.py        # Safe, non-regressive AutoFixEngine with candidate validation
│   │   │   ├── boundaries.py      # Plot boundary & statutory setback verification
│   │   │   ├── overlaps.py        # Pairwise room polygon collision checks
│   │   │   ├── dimensions.py      # Code minimums & aspect ratio proportions
│   │   │   ├── accessibility.py   # Corridor widths, door clearances & daylight
│   │   │   ├── adjacencies.py     # Room relationships & acoustic privacy
│   │   │   ├── utilization.py     # Ground coverage & dead residual voids
│   │   │   └── completeness.py    # Mandatory room completeness verification
│   │   ├── ai/                    # AI Generation, Revision & Copilot
│   │   │   ├── provider.py        # LLM Provider abstraction (Gemini, OpenAI, Demo Solver)
│   │   │   ├── demo_solver.py     # Deterministic architectural geometric solver
│   │   │   ├── layout_generator.py# Multi-variant layout generation pipeline
│   │   │   ├── revision_engine.py # Multi-cycle automated constraint repair engine
│   │   │   └── copilot.py         # Contextual conversational design assistant
│   │   ├── api/                   # REST API routes (Projects, Layouts, Gen, Val, Copilot, Export)
│   │   ├── export/                # Blueprint exporters (SVG with title block, PDF with ReportLab)
│   │   └── presets/               # Realistic presets including 25x40 demo home
│   ├── tests/                     # Comprehensive automated pytest suite (27 tests)
│   │   └── test_repair_acceptance.py # Mandatory Acceptance Tests A through H
│   └── requirements.txt           # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/            # Command Bar & Vertical Tool Rail
│   │   │   ├── canvas/            # Interactive SVG Floor Plan Canvas & Rulers
│   │   │   ├── inspector/         # Contextual Room & Site Inspector
│   │   │   ├── validation/        # Collapsible Spatial Conflict Audit Panel
│   │   │   ├── wizard/            # 5-Step Visual Project Setup Wizard
│   │   │   ├── comparison/        # Layout Alternatives Comparison Modal
│   │   │   ├── schedule/          # Architectural Room Schedule Sheet
│   │   │   ├── copilot/           # AI Design Copilot Drawer
│   │   │   ├── projects/          # Project Library Modal
│   │   │   └── export/            # Blueprint Export Modal
│   │   ├── styles/                # tokens.css (Warm ivory/terracotta tokens) & drafting.css
│   │   ├── store/                 # Project store with preview/undo/redo & autosave
│   │   ├── api/                   # API client connector
│   │   ├── types/                 # Architectural TypeScript interfaces
│   │   ├── App.tsx                # Studio main assembly
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
├── run_app.bat                    # One-click startup script for Windows
├── start_backend.bat              # Script to launch FastAPI backend
├── start_frontend.bat             # Script to launch Vite frontend
└── README.md
```

---

## ⚡ Quickstart Guide

### Prerequisites
- **Python**: 3.10+
- **Node.js**: v18+ (tested on Node v24)
- **npm**: 9+

### 1. Clone or Extract the Archive
Extract the `buildmind-architectural-generator.zip` file into your desired directory:
```bash
cd "buildmind ai"
```

### 2. Backend Setup
```bash
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
*The backend automatically initializes `buildmind.db` (SQLite) and seeds the mandatory 25 ft × 40 ft demonstration home if database is newly initialized.*

### 3. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at: **`http://localhost:5173/`**

---

## 🧪 Running Automated Tests

Run the complete backend test suite covering boundary checks, polygon overlaps, dimension minimums, setback violations, automated revisions, persistence, and the complete repair acceptance suite (Scenarios A through H):
```bash
cd backend
python -m pytest
```
*Expected output: 27 passed, 0 failed in ~7 seconds.*

---

## 🔑 LLM Provider Configuration (Optional)

BuildMind is designed to run completely out-of-the-box in **Deterministic Demo Mode** using its built-in computational geometry solver—**no external API keys are required** to test all layout generation, spatial validation, iterative revisions, room editing, comparisons, and exports.

If you wish to connect an external LLM API, configure the following in `backend/.env`:
```env
# Optional external LLM API keys:
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
LLM_PROVIDER=auto # 'auto', 'gemini', 'openai', or 'demo'
```

---

## 📋 The Required 25 ft × 40 ft Demo Scenario

The application automatically loads or allows 1-click loading of the **25 ft × 40 ft Urban Home Preset**:
1. **Site Dimensions**: 25.0 ft width × 40.0 ft length (1,000 sq ft).
2. **Initial Spaces**: 1 Living Hall, 1 Internal Staircase, 1 Kitchen, 1 Master Bedroom, 1 Bathroom.
3. **Geometry Validation**: All rooms are placed within statutory setbacks (Front 3ft, Rear 2ft, Sides 2ft) and verified against minimum dimensional standards.
4. **Interactive Modifications**:
   - Select a room (e.g. Master Bedroom) on the canvas to edit width/length with real-time geometric updates and re-validation.
   - Use the **AI Design Copilot** to add a second bedroom or expand the kitchen with diff previews.
   - Open **Compare** to view the Space-Optimized vs Comfort-Focused vs Budget-Conscious layouts side-by-side.
   - Open **Schedule** for the detailed room schedule table and efficiency ratios.
   - Open **Export** to download the architectural SVG blueprint, presentation PDF sheet, or JSON specification.

---

## 📜 Regulatory Disclaimer
All architectural plans and floor layouts generated by BuildMind are preliminary conceptual designs generated for spatial planning, program exploration, and geometric constraint checking. They do not constitute certified architectural blueprints or sanctioned municipal drawings until reviewed and stamped by a licensed architect in accordance with local jurisdictional building codes.
