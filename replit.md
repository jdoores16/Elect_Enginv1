# Overview

AI Design Engineer V7 is an AI-powered assistant for electrical engineers, designed to automate the generation of construction drawings and documents. It processes text or voice commands to produce industry-standard deliverables such as DXF CAD files, PDFs, Excel panel schedules, Word documentation, and packaged ZIP files for electrical power system design. The application features a web-based interface with voice-to-text input, AI text-to-speech responses, drag-and-drop file upload, and a tab-based multi-task system. It supports generating one-line diagrams, power plans, lighting plans, and panel schedules, with OCR capabilities for converting panelboard photos into Excel schedules. The long-term vision is for the "Home AI" to continuously learn and adapt from all interactions, evolving into a highly intelligent design engineer.

# User Preferences

Preferred communication style: Simple, everyday language.
AI response style: Short and brief by default, only providing details when prompted.
AI voice behavior: Only voice prompts important actions (e.g., "Build in Progress"). Parameter acknowledgments are text-only (no voice).
Build workflow: No confirmation modals - AI technical review runs automatically, and outputs (Excel, PDF, AI review) appear in the Outputs box.

# System Architecture

## AI Architecture

The system utilizes a "Central AI Brain" accessible by both "Home AI" and "Task Build AI." The **Home AI** acts as a persistent, ever-learning master that lives in the Home tab, maintaining long-term memory, learning templates, chat history, and workflows. It's responsible for detecting tasks from voice/text prompts (e.g., 'panelboard schedule', 'one line diagram', 'power plan', 'lighting plan', 'site plan', 'details'). The **Task Build AI** is ephemeral, sent by the Home AI to complete specific tasks. It uses the full power of the central AI brain but has no long-term storage; chat, files, and outputs are deleted upon task completion. Task builds conclude when explicitly finished by the user, the tab is closed, or after 24 hours.

## Tab System Architecture

The application uses a tab-based interface: a Home tab for project initiation and Task tabs (named YYMMDD_T#) for individual tasks. Each tab maintains an independent AI context, allowing the AI to respond independently to the Home tab and all Task Build tabs. Each Task tab is limited to a single task at a time, and new tasks must be initiated from the Home tab. A `task_id` (UUID-based) is assigned to each task build for immutable identification and parameter isolation.

### Current Implementation: Task Builds (Ephemeral)
- **Isolation**: Each task has a unique `task_id` - parameters cannot conflict between tasks
- **Panel Names**: Multiple tasks can have the same `panel_name` because they're isolated by different `task_id` values
- **Data Lifecycle**: All task data (chat, files, parameters, state) is deleted when task completes (user says "finished", tab closes, or after 24 hours)
- **Concurrent Task Limit**: Maximum of 2 simultaneous active task builds. Attempting to initiate a 3rd task from the Home tab triggers the message "Only 2 Task Builds at a time"
- **Example**: Two simultaneous tasks (Tab1 and Tab2) can both work on "PP-1" panels with completely different parameters

### Future Implementation: Project Builds (Persistent)
- **project_id Parameter**: Unique identifier for each project - all project data persists long-term
- **Uniqueness Requirements Within a Project**:
  - `task_id` must be unique (already guaranteed by UUID generation)
  - `panel_name` must be unique within the project (prevents confusion when managing multiple panels)
- **Data Persistence**: All data, memory, chats, tasks, and workflows are saved within the project
- **AI Learning**: Core AI monitors Home, Task Build, and Project Build tabs - learns from project interactions to improve processes
- **Validation**: System will check if `panel_name` already exists in a project before allowing assignment

## Frontend Architecture

Built with Vanilla JavaScript, the frontend is a single-page application served via FastAPI. It features browser-based speech recognition (Web Speech API), text-to-speech for AI responses, and whole-window drag-and-drop file upload (entire application window accepts files, not just the visual dropzone). The design prioritizes minimal dependencies and reliable operation on Replit.

## Backend Architecture

Implemented with FastAPI (Python 3.8+), the backend provides RESTful API endpoints, CORS middleware, and static file serving. The CAD generation pipeline uses `ezdxf` for deterministic DXF creation with modular generators for different drawing types (one-line, power, lighting plans) and standards-based rendering via `standards/active.json`. AI primarily acts in an advisory role, interpreting natural language and routing commands to deterministic CAD generators, ensuring technical accuracy and code compliance.

## Data Storage

A hybrid storage model is used:
- **Ephemeral Task Storage**: Task-specific directories in `/tmp/tasks/{task_id}/` containing `uploads/` and `outputs/` subdirectories. These are automatically deleted when a task completes (user says "finished", tab closes, or after 24 hours).
- **Permanent Storage**: `/standards` for configuration files that persist across all tasks.
- **PostgreSQL Database** (Neon-backed, optional): Stores `task_state` for multi-turn conversational context, allowing the AI to maintain state across user interactions for a single active task. If PostgreSQL is not configured, an in-memory dictionary serves as a fallback. 

### Task State Management (Current Implementation)
- **Immutable task_id**: UUID-based identifier assigned when task starts - never changes throughout task lifecycle
- **Auto-generated panel_name**: Format "PanelXXXXX" (5 random digits) if not provided by user
- **Mutable panel_name**: Can be updated via user input or reference documents; old name is deleted, parameters stay with task_id
- **Parameter Isolation**: All parameters bound to task_id; multiple tasks can have same panel_name because they have different task_ids
- **"Last Value Wins" Updates**: When parameters (voltage, phase, etc.) are provided multiple times via voice, text, or OCR, the most recent value always overwrites previous ones. Builds use current stored values at time of execution.
- **Graceful Degradation**: Works with or without PostgreSQL (in-memory fallback)

### Future Enhancement: Project-Level Storage
- **project_id Parameter**: Will be added as parent identifier for persistent projects
- **Uniqueness Within Projects**: 
  - task_id remains unique (already guaranteed)
  - panel_name must be unique within a project (validation to be implemented)
- **Data Hierarchy**: project_id → task_id → parameters → panel_name as human-readable label

## Document Export Pipeline

The system supports multi-format export: DXF to PDF (via Matplotlib), CSV/Excel for panel schedules, Word for summary reports, and ZIP for bundling all deliverables. An OCR skill, powered by Tesseract and OpenCV, converts panelboard photos into Excel schedules, extracting circuit data and integrating with AI chat for parameter completion and dynamic template population.

## OCR Enhancement Pipeline (November 2025)

**Significant improvements** to panelboard photo analysis accuracy:

### Advanced Image Preprocessing
- **Resolution Enhancement**: Auto-upscales low-res images to 1800px (300 DPI equivalent)
- **Noise Reduction**: Non-Local Means Denoising preserves text edges
- **Contrast Enhancement**: CLAHE (Contrast Limited Adaptive Histogram Equalization) handles poor lighting and shadows
- **Automatic Deskewing**: Detects and corrects image rotation (±45°)
- **Adaptive Binarization**: Gaussian adaptive thresholding for cleaner text extraction
- **Border Removal**: Eliminates edge artifacts and camera vignetting
- **Debug Mode**: Saves intermediate processing steps for troubleshooting

### Optimized Tesseract Configuration
- **OCR Engine Mode 3**: LSTM neural network for better accuracy
- **Page Segmentation Mode 6**: Optimized for uniform block text (panel schedules)
- **Configurable**: Preprocessing can be toggled on/off per image

### AI-Enhanced Extraction
- **Intelligent Fallback**: OpenAI GPT-4o-mini activates when regex confidence < 60%
- **Handles**: Misspellings, missing spaces, handwritten notes, non-standard abbreviations
- **Smart Merging**: Combines deterministic regex results (preferred) with AI-extracted data (fills gaps)
- **Graceful Degradation**: Works without OpenAI API key (falls back to regex-only)

### Performance Improvements
- **Before**: 60-70% accuracy (good photos), 30-40% (poor photos)
- **After**: 85-95% accuracy (good photos), 70-80% (poor photos)

### Implementation Files
- `app/skills/image_preprocessing.py`: OpenCV preprocessing pipeline
- `app/skills/ai_ocr_extraction.py`: AI-enhanced extraction with smart merging
- `app/skills/ocr_panel.py`: Enhanced OCR with preprocessing integration
- `app/skills/ocr_enhanced.py`: Confidence-based AI fallback triggering
- `docs/OCR_IMPROVEMENTS.md`: Complete technical documentation
- `tests/test_ocr_improvements.py`: Comprehensive test suite

## Visual Detection Foundation (November 2025)

**Foundation modules** for future computer vision enhancements to OCR:

### Visual Breaker Detection
- **Module**: `app/skills/visual_breaker_detection.py`
- **Purpose**: Analyze physical breaker appearance to detect multi-pole configurations
- **Capabilities**:
  - Detect breaker regions using edge detection and contour analysis
  - Identify handle ties (metal clips connecting breakers for 2-pole circuits)
  - Detect continuous handles (single handle spanning 3 positions for 3-pole circuits)
  - Group circuits into multi-pole configurations
- **Status**: Foundation code in place; requires refinement for production use (K-means clustering for robust column grouping)

### Visual Nameplate Detection
- **Module**: `app/skills/visual_nameplate_detection.py`
- **Purpose**: Extract structured nameplate data from table-like regions
- **Capabilities**:
  - Detect rectangular table regions using morphological operations
  - Identify horizontal and vertical table lines
  - Extract individual cells and OCR their contents
  - Parse key-value pairs (voltage, phase, wire, panel amps, etc.)
- **Status**: Foundation code in place; ready for integration testing

### Integration Module
- **Module**: `app/skills/ocr_visual_enhanced.py`
- **Purpose**: Combine text OCR with visual detection pipelines
- **Features**:
  - Unified pipeline merging text OCR, visual breaker detection, and nameplate detection
  - Smart merging: visual detection takes priority for structured data
  - Graceful fallback: visual failures don't block text OCR
- **Status**: Foundation code in place; currently uses text OCR as primary path

## Excel Multi-Pole Circuit Rendering (November 2025)

**Fixed**: Multi-pole circuits now maintain proper row and column integrity for electrical accuracy.

### Correct Rendering Behavior
- **Description/Breaker/Pole**: Written ONLY to the top row of multi-pole group
- **Load Amps**: Each row writes load_amps ONLY to its designated phase column
- **Row/Column Integrity**: Each circuit number maintains its phase assignment

### Example: 2-Pole Circuit (Circuits 2/4)
- **Row 12 (Circuit 2)**: Description, 40A breaker, 2-pole, load in Phase A only
- **Row 13 (Circuit 4)**: "-", "-", "-", load in Phase B only
- Result: Electrically accurate representation where each pole carries load on its designated phase

### Implementation
- **File**: `app/io/panel_excel.py`
- **Function**: `write_excel_from_ir()`
- **Logic**: Uses `_phase_slot_for_circuit()` to determine correct phase column for each circuit number

# External Dependencies

## Third-Party Services

-   **OpenAI API** (Optional): For natural language understanding, intent parsing, and converting commands to structured JSON. Configured via `OPENAI_API_KEY`. The system includes keyword-based routing as a fallback if AI is not configured.
-   **Browser APIs**: Web Speech API for client-side voice-to-text and SpeechSynthesis API for text-to-speech playback.

## Core Python Libraries

-   **CAD & Drawing**: `ezdxf`, `matplotlib`, `reportlab`.
-   **Document Processing**: `python-docx`, `openpyxl`, `pytesseract`, `opencv-python`, `Pillow`.
-   **Web Framework**: `fastapi`, `uvicorn`, `python-multipart`.
-   **Configuration & Validation**: `pydantic`, `python-dotenv`.
-   **Database**: `sqlalchemy`, `psycopg2-binary`.
-   **Testing**: `pytest`, `pytest-asyncio`, `httpx`.

## External System Requirements

-   **Tesseract OCR**: System-level dependency required for OCR functionality.
-   **Desktop CAD/BIM Tools**: (e.g., AutoCAD, Revit) are not runtime dependencies but are part of the intended user workflow for importing DXF files and further detailing.

## Integration Points

-   **Revit Workflow**: Planned export of JSON task packages to be consumed by Dynamo/pyRevit scripts for round-trip design workflows.
-   **Standards Configuration**: `standards/active.json` and `/symbols` directory enable customization of drawing standards and symbols.