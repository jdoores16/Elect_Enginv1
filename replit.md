# Overview

AI Design Engineer V7 is an AI-powered assistant for electrical engineers, automating the generation of construction drawings and documents from text or voice commands. It produces industry-standard deliverables like DXF CAD files, PDFs, Excel panel schedules, Word documentation, and packaged ZIP files. The application features a web-based interface with voice-to-text input, AI text-to-speech responses, drag-and-drop file upload, and a tab-based multi-task system. It supports generating one-line diagrams, power plans, lighting plans, and panel schedules, with OCR capabilities for converting panelboard photos into Excel schedules. The long-term vision is for the "Home AI" to continuously learn and adapt, evolving into a highly intelligent design engineer.

# User Preferences

Preferred communication style: Simple, everyday language.
AI response style: Short and brief by default, only providing details when prompted.
AI voice behavior: Only voice prompts important actions (e.g., "Build in Progress"). Parameter acknowledgments are text-only (no voice).
Build workflow: No confirmation modals - AI technical review runs automatically, and outputs (Excel, PDF, AI review) appear in the Outputs box.

# System Architecture

## AI Architecture

The system uses a "Central AI Brain" supporting both "Home AI" and "Task Build AI." **Home AI** is a persistent master in the Home tab, managing long-term memory, learning templates, chat history, and workflows, and detecting tasks from user prompts. **Task Build AI** is ephemeral, sent by Home AI to complete specific tasks. It uses the central AI brain but has no long-term storage; its data is deleted upon task completion or tab closure.

## Tab System Architecture

The application employs a tab-based interface: a Home tab for project initiation and Task tabs (named YYMMDD_T#) for individual tasks. Each tab maintains an independent AI context. Task tabs are limited to one task at a time, and new tasks must be initiated from the Home tab. A UUID-based `task_id` ensures immutable identification and parameter isolation for each task. Task builds are ephemeral, with all data deleted upon completion or after 24 hours.

## Frontend Architecture

Built with Vanilla JavaScript, the frontend is a single-page application served via FastAPI. It features browser-based speech recognition (Web Speech API), text-to-speech for AI responses, and whole-window drag-and-drop file upload, prioritizing minimal dependencies and reliability.

## Backend Architecture

Implemented with FastAPI (Python 3.8+), the backend provides RESTful API endpoints and static file serving. The CAD generation pipeline uses `ezdxf` for deterministic DXF creation with modular generators and standards-based rendering. AI primarily interprets natural language and routes commands to deterministic CAD generators, ensuring technical accuracy and code compliance.

## Data Storage

A hybrid storage model is used:
- **Ephemeral Task Storage**: Task-specific directories in `/tmp/tasks/{task_id}/` for uploads and outputs, automatically deleted upon task completion.
- **Permanent Storage**: `/standards` for persistent configuration files.
- **PostgreSQL Database** (Neon-backed, optional): Stores `task_state` for multi-turn conversational context, maintaining state across user interactions for a single active task. An in-memory dictionary serves as a fallback if PostgreSQL is not configured.
- **Confidence-Based Parameter Tracking**: `PanelParameterStore` tracks confidence for all panel parameters to prevent lower-quality data from overwriting higher-quality information, using method weights (AI_VISION: 0.85, MANUAL: 0.70, TEXT_OCR: 0.60).

## Document Export Pipeline

The system supports multi-format export: DXF to PDF, CSV/Excel for panel schedules, Word for reports, and ZIP for bundling deliverables. An OCR skill, powered by Tesseract and OpenCV, converts panelboard photos into Excel schedules, extracting circuit data and integrating with AI chat for parameter completion and dynamic template population. This includes advanced image preprocessing, optimized Tesseract configuration, and AI-enhanced extraction with GPT-4o-mini as a fallback for improved accuracy. Foundation modules for visual breaker detection and visual nameplate detection are in place for future computer vision enhancements.

## Excel Multi-Pole Circuit Rendering

Multi-pole circuits now maintain proper row and column integrity in Excel exports. Description/Breaker/Pole information is written only to the top row of a multi-pole group, while Load Amps are written only to the designated phase column for each row, ensuring electrically accurate representation.

## Load Type Classification

Every pole space with load_amps requires a load_type classification. Valid load types are:
- **LTG**: Lighting loads
- **RCP**: Receptacle loads  
- **MTR**: Motor loads
- **C**: Continuous loads
- **NC**: Non-Continuous loads

The variable list Excel includes a "Load Type" column that shows "NA" (Not Applicable) for all parameters except Load Amps rows, which display the actual load type code. Load type is tracked through the confidence-based aggregation system and flows from OCR/AI Vision extraction through to Excel output.

# External Dependencies

## Third-Party Services

-   **OpenAI API** (Optional): For natural language understanding, intent parsing, and converting commands to structured JSON. Keyword-based routing is a fallback if not configured.
-   **Browser APIs**: Web Speech API for voice-to-text and SpeechSynthesis API for text-to-speech.

## Core Python Libraries

-   **CAD & Drawing**: `ezdxf`, `matplotlib`, `reportlab`.
-   **Document Processing**: `python-docx`, `openpyxl`, `pytesseract`, `opencv-python`, `Pillow`.
-   **Web Framework**: `fastapi`, `uvicorn`, `python-multipart`.
-   **Configuration & Validation**: `pydantic`, `python-dotenv`.
-   **Database**: `sqlalchemy`, `psycopg2-binary`.

## External System Requirements

-   **Tesseract OCR**: System-level dependency for OCR functionality.

## Integration Points

-   **Standards Configuration**: `standards/active.json` and `/symbols` directory for customizable drawing standards and symbols.