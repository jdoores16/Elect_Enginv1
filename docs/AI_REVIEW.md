# AI Electrical Engineering Review

## Overview

The system now includes an **advisory-only** AI technical review powered by OpenAI that analyzes panel schedules for electrical engineering correctness, safety, and NEC code compliance.

## Key Features

### Technical Focus (NOT Formatting)
The AI review analyzes **electrical engineering** aspects only:
- ✅ System type identification (DELTA vs WYE)
- ✅ Grounding analysis (grounded vs ungrounded)
- ✅ Neutral conductor requirements
- ✅ Phase balance calculations
- ✅ Conductor sizing validation (NEC Tables)
- ✅ KVA calculations and conversions
- ✅ MCB vs Main Bus Amps checks
- ✅ Phase load distribution
- ✅ Panel location and environmental considerations
- ✅ Material and enclosure recommendations (NEMA ratings)
- ✅ NEC code compliance

### What It Does NOT Review
- ❌ Formatting or aesthetics
- ❌ Template structure
- ❌ Font sizes or colors
- ❌ Visual layout
- ❌ Document appearance

## Advisory-Only Architecture

**CRITICAL**: The AI review **NEVER blocks builds**. It operates as follows:

1. **Build Always Completes**: Excel and PDF files are generated regardless of review results
2. **Review Included**: AI analysis is included as additional files in the ZIP
3. **User Decision**: User reviews findings and decides whether to update and rebuild
4. **Graceful Failure**: If OpenAI API fails, build proceeds with a note that review is unavailable

## Output Files

When a panel schedule is built, the ZIP contains:

1. **`panel_[NAME]_[VOLTAGE].xlsx`** - Excel panel schedule
2. **`panel_[NAME]_[VOLTAGE].pdf`** - PDF panel schedule
3. **`panel_[NAME]_[VOLTAGE]_AI_REVIEW.json`** - Machine-readable review (full data)
4. **`panel_[NAME]_[VOLTAGE]_AI_REVIEW.txt`** - Human-readable review summary

### Review TXT Format Example

```
================================================================================
AI ELECTRICAL ENGINEERING REVIEW (ADVISORY ONLY)
================================================================================

Panel: PP-1
Review Status: ⚠️ ISSUES FOUND

SUMMARY:
The panel schedule shows a 3-phase WYE grounded system with adequate conductor
sizing for the 800A main bus. Phase balance is within acceptable limits at 12%
imbalance. However, the neutral conductor appears undersized for the connected
load per NEC 220.61.

SYSTEM ANALYSIS:
  System Type: 3PH WYE, GROUNDED (480Y/277V indicates wye configuration)
  Grounding: Solidly grounded system with equipment ground
  Phase Balance: 12% imbalance (acceptable, under 20% limit)
  Conductor Adequacy: Phase conductors adequate, neutral undersized
  Panel Usage: Industrial HVAC equipment - requires weather-resistant enclosure
  Kva Calculation: 145.2 kVA total connected load

⚠️ WARNINGS:
  • Neutral conductor #1/0 may be undersized for 145kVA load
  • Outdoor location requires NEMA 3R minimum enclosure rating
  • Phase C loading at 92% of bus capacity - consider load distribution

💡 RECOMMENDATIONS:
  • Increase neutral conductor to #2/0 per NEC 220.61
  • Specify NEMA 3R or 4X enclosure for outdoor installation
  • Consider redistributing Phase C loads to improve balance
  • Add surge protection device (SPD) for equipment protection

DETAILED REVIEW:
✓ System type correctly identified as WYE from voltage notation
   Notes: 480Y/277V notation indicates grounded wye system
✗ Neutral conductor sizing inadequate
   Notes: #1/0 neutral insufficient for 145kVA load, recommend #2/0
✓ Phase conductor sizing adequate for main bus ampacity
   Notes: #4/0 CU conductors rated for 800A at 75°C
...

================================================================================
NOTE: This review is advisory only. Build files are generated regardless.
Review findings and update your design as needed, then rebuild.
================================================================================
```

## API Usage

### Endpoint: `/panel/export/zip`

**Parameters:**
- `skip_ai_review` (bool, optional): Set to `true` to skip AI review (default: `false`)

**Example:**
```bash
# With AI review (default)
POST /panel/export/zip
{ "ir": {...panel data...} }

# Skip AI review
POST /panel/export/zip?skip_ai_review=true
{ "ir": {...panel data...} }
```

## Configuration

Set the OpenAI API key via environment variable:
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini  # Optional, defaults to gpt-4o-mini
```

If the API key is not set, the review step is automatically skipped and the build proceeds normally.

## Workflow

1. **User initiates build** → System validates IR and generates Excel/PDF
2. **AI review runs** (if OpenAI configured) → Technical analysis performed
3. **Review files created** → JSON and TXT files generated
4. **ZIP created** → All files (Excel, PDF, reviews) bundled
5. **User downloads ZIP** → Reviews findings
6. **User updates design** (if needed) → Makes changes based on recommendations
7. **User rebuilds** → Repeat process with updated parameters

## Error Handling

If the AI review fails for any reason:
- Build continues normally
- Excel and PDF are still generated
- ZIP is created without review files
- Warning logged for debugging

This ensures maximum reliability - builds never fail due to AI issues.

## Integration with Existing Checklists

The system maintains two review mechanisms:

1. **Deterministic Preflight** (`/api/preflight/gpt`): Fast, rule-based checks
2. **AI Technical Review** (new): Deep LLM-powered electrical engineering analysis

Both are advisory only and work together to provide comprehensive feedback.
