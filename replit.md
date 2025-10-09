# Overview

AI Design Engineer V7 is an AI-powered assistant for electrical engineers that generates construction drawings and documents from text or voice commands. The system produces industry-standard outputs including DXF CAD files, PDFs, Excel panel schedules, Word documentation, and packaged ZIP deliverables for electrical power system design projects.

The application provides a web-based interface with voice-to-text input, AI text-to-speech responses with wave visualization, drag-and-drop file upload, and tab-based multi-task system. It supports generating one-line diagrams, power plans, lighting plans, and panel schedules, with built-in OCR capabilities to convert panelboard photos into Excel schedules.

## AI Architecture

**Central AI Brain**: Both Home and Task Build AIs pull knowledge and processing power from the same central intelligence.

**Persistent AI (Home Screen)** - The Ever-Learning Master:
- The true design engineer being trained and taught
- Lives in the Home tab permanently
- Learns, adapts, and grows from all interactions
- Tracks templates, chat history, and learned workflows
- Maintains long-term memory and knowledge
- **Does everything the app is designed to do** - responds to queries, generates drawings, processes files, etc.
- Detects tasks from voice/text prompts by identifying keywords:
  - 'panelboard schedule' - uses OCR from uploaded photos and interactive chat to complete all fields
  - 'one line diagram' - creates one-line diagrams
  - 'power plan' - builds power distribution plans
  - 'lighting plan' - designs lighting layouts
  - 'site plan' - produces site electrical plans
  - 'details' - generates construction details

**Task Build AI** - Temporary Worker:
- Sent off by the Home AI to complete a specific task
- Has the **full power** of the central AI brain to complete tasks
- Works with current templates, workflows, and learned patterns from the master
- Task Builds are completely ephemeral - temporary workspaces with zero long-term storage
- Chat conversations are NOT saved
- Uploaded files are NOT saved  
- Generated outputs are NOT saved
- Workflow learning is NOT retained
- Nothing remains from the task when it ends

**Automatic Deletion Triggers** - Task build ends and all data is deleted when:
1. User says "finished" (explicit completion)
2. Tab is closed/exited (user navigates away)
3. 24 hours pass from task build start (automatic expiry)

**Tab System Architecture:**
- Home tab: Welcome screen with "What can I build for you?" and three options (Task Build, Create New Project Build, Open Project Build)
- Task tabs: Date-based naming (YYMMDD_T#) with auto-incrementing daily counters
- Independent AI context: Each tab has unique session ID for "divided brain" operation
- AI responds independently to Home tab and all Task Build tabs

**Project Builds (Future Feature)**:
- Projects are where data will be saved and stored long-term
- Unlike Task Builds, Project Builds persist chat, files, outputs, and workflow learning
- Accessible via "Create New Project Build" and "Open Project Build" buttons (currently disabled)

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

**Hybrid Storage Model**: File-based + PostgreSQL for conversational state

**File-Based Storage**:
- `/bucket` directory: User-uploaded reference files (floor plans, cut sheets, photos)
- `/out` directory: Generated outputs (DXF, PDF, CSV, DOCX, ZIP)
- Session isolation via filename prefixing
- Standards configuration stored in JSON (`standards/active.json`)

**PostgreSQL Database** (Neon-backed, optional):
- `task_state` table: Tracks active tasks per session for multi-turn conversations
- Enables AI to maintain context across multiple user responses
- Example flow: User says "build panelboard schedule" → AI asks "how many circuits?" → User says "42" → AI stays on task and confirms readiness
- Valid circuit range: 18-84 circuits (must be even number) to support template with up to 84-circuit capacity
- Task cleared when user says "finished", "done", "cancel", or "new task"
- **Graceful Degradation**: If DATABASE_URL is not set, task state uses an in-memory dictionary fallback (persists only within server lifetime, lost on restart)
- **In-Memory Fallback**: All confirmation and state management features work identically with or without PostgreSQL

**Design Rationale**: 
- File-based storage remains primary for deliverable packages (self-contained, version-control friendly, CAD workflow compatible)
- Database added specifically for conversational state management to enable multi-turn task parameter collection
- Keeps database schema minimal (single table) to maintain simplicity while solving the task persistence problem

**Task State Management**:
- Each session can have one active task at a time
- Parameters (like `number_of_ckts` for panel schedules) accumulate from user responses
- AI remains focused on active task until user explicitly says "finished"
- Prevents AI from switching tasks mid-conversation when user provides requested parameters

## Document Export Pipeline

**Multi-Format Export System**:
- **DXF → PDF**: Matplotlib backend renders DXF to PDF with title block annotation
- **Panel Schedules**: CSV/Excel generation with optional template support
- **Word Documentation**: Summary reports with scope, PE review notes, NEC references
- **Package Assembly**: ZIP bundling of all deliverables per session

**OCR Skill with AI-Assisted Completion**: Tesseract-based image-to-Excel conversion for panelboard photos
- Image preprocessing (grayscale conversion)
- Pattern matching for circuit data extraction (1-42)
- Extracts 4 parameters per circuit: Description, Load, Breaker Poles (1/2/3), Breaker Amps (NEC standard sizes)
- Circuit layout: Odd circuits in columns A-F, even circuits in columns J-O, starting at row 12 (row 11 = headers)
- Template-aware Excel population with odd/even circuit layout
- **Dynamic Template Parameter Extraction**: System reads Excel template at task start
  - Extracts parameter labels from A2-A9 (left side) and N2-N9 (right side)
  - Shows user what fields are required (e.g., "Template requires: VOLTAGE, PHASE, WIRE...")
  - Values are populated in B2-B9 (left values) and O2-O9 (right values)
  - Supports custom user-uploaded templates with different field configurations
- **AI Chat Completion**: AI extracts ALL panel parameters from text/voice input:
  - Panel name (e.g., "panel name is PP-TEST1" → extracts "PP-TEST1")
  - Number of circuits (e.g., "42 circuits" → extracts 42)
  - Other specifications (voltage, phase, amperes, etc.)
- Combines OCR automation with interactive conversation for complete, accurate panel schedules
- User input parameters override OCR data when provided

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

**Database**:
- `sqlalchemy` (2.0.x): SQL toolkit and ORM for PostgreSQL
- `psycopg2-binary` (2.9.x): PostgreSQL database adapter

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