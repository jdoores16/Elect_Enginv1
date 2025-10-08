# Overview

AI Design Engineer V7 is an AI-powered assistant for electrical engineers that generates construction drawings and documents from text or voice commands. The system produces industry-standard outputs including DXF CAD files, PDFs, Excel panel schedules, Word documentation, and packaged ZIP deliverables for electrical power system design projects.

The application provides a web-based interface with voice-to-text input, AI text-to-speech responses with wave visualization, drag-and-drop file upload, and session-based project isolation. It supports generating one-line diagrams, power plans, lighting plans, and panel schedules, with built-in OCR capabilities to convert panelboard photos into Excel schedules.

# User Preferences

Preferred communication style: Simple, everyday language.
AI response style: Short and brief by default, only providing details when prompted.

# System Architecture

## Frontend Architecture

**Technology Stack**: Vanilla JavaScript with HTML5 Canvas for visualization
- Single-page application served as static files through FastAPI
- Real-time wave visualization using Canvas API for audio feedback
- Browser-based speech recognition for voice commands (Web Speech API)
- Drag-and-drop file upload with visual feedback
- Session-based UI state management with local storage

**Design Rationale**: Chose vanilla JavaScript over frameworks to minimize dependencies and ensure the application runs reliably on Replit without complex build processes. The Canvas-based wave visualizer provides engaging visual feedback during AI speech responses without requiring heavy audio processing libraries.

## Backend Architecture

**Framework**: FastAPI (Python 3.8+)
- RESTful API endpoints for file upload, command processing, and output generation
- CORS middleware enabled for cross-origin requests
- Static file serving for frontend assets
- Async request handling for improved concurrency

**CAD Generation Pipeline**:
- **Deterministic DXF Generation**: Uses `ezdxf` library to programmatically create CAD drawings
- **Modular Generator System**: Separate modules for one-line diagrams (`one_line.py`), power plans (`power_plan.py`), and lighting plans (`lighting_plan.py`)
- **Standards-Based Rendering**: Configurable layer naming, text styles, and symbol blocks via `standards/active.json`
- **Block Import System**: Reusable symbol library with DXF block import utilities

**Design Rationale**: FastAPI provides automatic OpenAPI documentation, type validation via Pydantic, and excellent async performance. The deterministic DXF generation approach ensures reproducible outputs that can be reviewed and approved by licensed Professional Engineers before sealing, maintaining compliance with engineering standards.

## AI Integration Layer

**LLM Integration**: OpenAI API (configurable)
- Structured JSON schema enforcement for predictable outputs
- Intent parsing from natural language commands
- Command routing to appropriate CAD generators
- File context awareness (references uploaded documents in bucket)

**Design Rationale**: The system keeps AI in an advisory/planning role while CAD generation remains deterministic and rule-based. This ensures outputs are technically accurate and comply with electrical codes (NEC). AI handles ambiguous user input and converts it to structured data, but does not directly generate drawings.

**Alternative Considered**: Direct AI-to-CAD generation was rejected because it would be non-deterministic and could produce code-violating designs that risk professional liability.

## Data Storage

**File-Based Storage**: No database required
- `/bucket` directory: User-uploaded reference files (floor plans, cut sheets, photos)
- `/out` directory: Generated outputs (DXF, PDF, CSV, DOCX, ZIP)
- Session isolation via filename prefixing
- Standards configuration stored in JSON (`standards/active.json`)

**Design Rationale**: File-based storage is appropriate for this use case because:
1. Projects are self-contained deliverable packages
2. Version control works naturally with file systems
3. No complex queries or relationships required
4. Simplifies deployment on Replit and similar platforms
5. Engineers are accustomed to file-based CAD workflows

**Pros**: Simple, portable, version-control friendly, no database maintenance
**Cons**: Limited querying capability, manual cleanup required, not suitable for multi-user concurrent access

## Document Export Pipeline

**Multi-Format Export System**:
- **DXF → PDF**: Matplotlib backend renders DXF to PDF with title block annotation
- **Panel Schedules**: CSV/Excel generation with optional template support
- **Word Documentation**: Summary reports with scope, PE review notes, NEC references
- **Package Assembly**: ZIP bundling of all deliverables per session

**OCR Skill**: Tesseract-based image-to-Excel conversion for panelboard photos
- Image preprocessing (grayscale conversion)
- Pattern matching for circuit number extraction
- Template-aware Excel population

# External Dependencies

## Third-Party Services

**OpenAI API** (Optional):
- Purpose: Natural language understanding and intent parsing
- Used for: Converting voice/text commands to structured JSON
- Configuration: API key stored in environment variable `OPENAI_API_KEY`
- Note: System includes fallback keyword-based routing if AI is not configured

**Browser APIs**:
- Web Speech API: Voice-to-text transcription (client-side)
- Audio API: Wave visualization and audio playback

## Core Python Libraries

**CAD & Drawing**:
- `ezdxf` (1.3.4): DXF file creation and manipulation
- `matplotlib` (≥3.8.0): DXF-to-PDF rendering backend
- `reportlab` (≥4.0.0): PDF generation utilities

**Document Processing**:
- `python-docx` (≥1.1.0): Word document generation
- `openpyxl` (≥3.1.2): Excel file creation and template reading
- `pytesseract` (≥0.3.10): OCR text extraction
- `opencv-python` (≥4.9.0): Image preprocessing for OCR
- `Pillow` (≥10.3.0): Image manipulation

**Web Framework**:
- `fastapi` (0.115.0): Web application framework
- `uvicorn` (0.30.6): ASGI server
- `python-multipart` (0.0.9): File upload handling

**Configuration & Validation**:
- `pydantic` (2.9.2): Data validation and settings management
- `python-dotenv` (1.0.1): Environment variable loading

**Testing**:
- `pytest` (≥8.0.0): Testing framework
- `pytest-asyncio` (≥0.23.0): Async test support
- `httpx` (≥0.27.0): HTTP client for API testing

## External System Requirements

**Tesseract OCR**:
- System-level dependency for OCR functionality
- Must be installed separately and available in PATH
- Used by pytesseract Python wrapper

**Desktop CAD/BIM Tools** (User's Local Machine):
- AutoCAD/BricsCAD/DraftSight: For importing DXF, adding annotations, title blocks
- Revit with Dynamo/pyRevit: For consuming JSON task packages and automating family placement
- Note: These are not runtime dependencies but part of the intended workflow

## Integration Points

**Revit Workflow**:
- Exports JSON task packages with device locations, panel assignments, circuit data
- Intended for consumption by Dynamo/pyRevit scripts (not included in this repository)
- Enables round-trip workflow: AI generates base design → Revit for detailed modeling → Export back to JSON for audit trail

**Standards Configuration**:
- `standards/active.json`: Centralized configuration for layer names, text styles, symbol mappings
- Symbol library: DXF files in `/symbols` directory referenced by standards config
- Allows customization per firm/project standards without code changes