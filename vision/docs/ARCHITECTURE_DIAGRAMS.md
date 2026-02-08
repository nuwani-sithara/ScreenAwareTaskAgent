# Architecture Diagram - Generalized Vision Perception

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│                    GENERALIZED VISION PERCEPTION SYSTEM                 │
│                     (VLM-Centric Hybrid Architecture)                   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘


                                 ┌─────────────────┐
                                 │  SCREENSHOT     │
                                 │  INPUT          │
                                 └────────┬────────┘
                                          │
                        ┌─────────────────▼──────────────────┐
                        │  Perception Router                 │
                        │  (Strategy Selector)               │
                        │                                    │
                        │  Strategy = "vlm" / "yolo" / "hybrid"
                        └─┬──────────────────────┬──────────┬┘
                          │                      │          │
                  ┌───────▼───────┐    ┌────────▼──────┐   │
                  │  VLM Path     │    │  YOLO Path    │   │
                  │               │    │               │   │
                  │  Zero-shot    │    │  Fast-path    │   │
                  │  Detection    │    │  Detection    │   │
                  │               │    │               │   │
                  │ (Claude       │    │  (Optional,   │   │
                  │  GPT-4V       │    │   pre-trained)│   │
                  │  Local)       │    │               │   │
                  └───────┬───────┘    └────────┬──────┘   │
                          │                     │          │
                  ┌───────▼──────────────────────▼──────┐   │
                  │                                    │   │
                  │  VLM Response JSON                 │   │
                  │  └─ elements[]                     │   │
                  │     ├─ type                        │   │
                  │     ├─ label                       │   │
                  │     ├─ bbox                        │   │
                  │     ├─ confidence                  │   │
                  │     └─ state                       │   │
                  │                                    │   │
                  └───────┬──────────────────────────────┘  │
                          │                                  │
            ┌─────────────▼─────────────┐                   │
            │ UI Parser                 │                   │
            │                           │                   │
            │ • JSON extraction         │                   │
            │ • Bbox normalization      │                   │
            │ • Type alignment          │                   │
            │ • Error recovery          │                   │
            │                           │                   │
            └─────────────┬─────────────┘                   │
                          │                                  │
        ┌─────────────────▼──────────────────┐              │
        │  UIElements (Structured)           │              │
        │                                    │              │
        │  [UIElement]                       │              │
        │  ├─ id: str                        │              │
        │  ├─ type: str                      │              │
        │  ├─ label: str                     │              │
        │  ├─ bbox: Tuple[0-1]               │              │
        │  ├─ confidence: float              │              │
        │  └─ raw_data: dict                 │              │
        │                                    │              │
        └─────────────────┬──────────────────┘              │
                          │                                  │
        ┌─────────────────▼──────────────────────────────┐  │
        │                                               │  │
        │         GROUNDING LAYER (Refinement)         │  │
        │                                               │  │
        │  ┌─────────────────────────────────────────┐ │  │
        │  │ BBox Refiner                            │ │  │
        │  │                                         │ │  │
        │  │ • Edge detection (Canny/Sobel)         │ │  │
        │  │ • Snap to detected edges                │ │  │
        │  │ • Grid alignment                        │ │  │
        │  │ • Size validation                       │ │  │
        │  └─────────────┬───────────────────────────┘ │  │
        │                │                             │  │
        │  ┌─────────────▼───────────────────────────┐ │  │
        │  │ Overlap Resolver                        │ │  │
        │  │                                         │ │  │
        │  │ • IoU calculation                       │ │  │
        │  │ • Merge overlapping boxes               │ │  │
        │  │ • Filter nested elements                │ │  │
        │  │ • Group nearby elements                 │ │  │
        │  └─────────────┬───────────────────────────┘ │  │
        │                │                             │  │
        │  Refined Bboxes ← ← ← ← ← ← ← ← ← ← ← ← ← │  │
        │                                               │  │
        └─────────────────┬──────────────────────────────┘  │
                          │                                  │
        ┌─────────────────▼──────────────────────────────┐  │
        │                                               │  │
        │    SEMANTIC STATE BUILDER                     │  │
        │                                               │  │
        │  ┌─────────────────────────────────────────┐ │  │
        │  │ Element Classification                  │ │  │
        │  │                                         │ │  │
        │  │ role = classify(type)                   │ │  │
        │  │ ├─ action (button, link, menu_item)    │ │  │
        │  │ ├─ input (field, checkbox, radio)      │ │  │
        │  │ ├─ display (text, icon, image)         │ │  │
        │  │ └─ container (modal, dialog, menu)     │ │  │
        │  └──────────────┬──────────────────────────┘ │  │
        │                 │                            │  │
        │  ┌──────────────▼──────────────────────────┐ │  │
        │  │ Element Grouping                        │ │  │
        │  │                                         │ │  │
        │  │ groups = {                              │ │  │
        │  │   "actions": [...],   # buttons          │ │  │
        │  │   "inputs": [...],    # forms            │ │  │
        │  │   "displays": [...],  # text/images      │ │  │
        │  │ }                                         │ │  │
        │  └──────────────┬──────────────────────────┘ │  │
        │                 │                            │  │
        │  ┌──────────────▼──────────────────────────┐ │  │
        │  │ Relationship Detection                  │ │  │
        │  │                                         │ │  │
        │  │ input_pairs = [                         │ │  │
        │  │   (input_field, label),                 │ │  │
        │  │   ...                                   │ │  │
        │  │ ]                                        │ │  │
        │  └──────────────┬──────────────────────────┘ │  │
        │                 │                            │  │
        │  Semantic State                             │  │
        │  {                                          │  │
        │    "elements": [...],                       │  │
        │    "groups": {...},                         │  │
        │    "input_pairs": [...],                    │  │
        │    "interactive_elements": [...],           │  │
        │    "summary": {...}                         │  │
        │  }                                          │  │
        │                                               │  │
        └─────────────────┬──────────────────────────────┘  │
                          │                                  │
        ┌─────────────────▼──────────────────────────────┐  │
        │                                               │  │
        │        FEEDBACK LOGGER                        │  │
        │        (Weak Supervision)                     │  │
        │                                               │  │
        │  ┌─────────────────────────────────────────┐ │  │
        │  │ Event Logging                           │ │  │
        │  │                                         │ │  │
        │  │ log_detection(                          │ │  │
        │  │   image,                                │ │  │
        │  │   elements,                             │ │  │
        │  │   action,                               │ │  │
        │  │   metadata                              │ │  │
        │  │ ) → event_id                            │ │  │
        │  └──────────────┬──────────────────────────┘ │  │
        │                 │                            │  │
        │  ┌──────────────▼──────────────────────────┐ │  │
        │  │ Feedback Recording                      │ │  │
        │  │                                         │ │  │
        │  │ mark_feedback(                          │ │  │
        │  │   event_id,                             │ │  │
        │  │   success,  # True/False                │ │  │
        │  │   reason                                │ │  │
        │  │ )                                        │ │  │
        │  │                                         │ │  │
        │  │ Stores in:                              │ │  │
        │  │ ├─ data/feedback/positive/              │ │  │
        │  │ └─ data/feedback/negative/              │ │  │
        │  └──────────────┬──────────────────────────┘ │  │
        │                 │                            │  │
        │  ┌──────────────▼──────────────────────────┐ │  │
        │  │ Statistics & Analytics                  │ │  │
        │  │                                         │ │  │
        │  │ get_improvement_summary() → {           │ │  │
        │  │   "success_rate": 0.85,                 │ │  │
        │  │   "element_types": [...],               │ │  │
        │  │   "stats": {...}                        │ │  │
        │  │ }                                        │ │  │
        │  │                                         │ │  │
        │  │ export_training_dataset() →             │ │  │
        │  │   "training_dataset_*.json"             │ │  │
        │  └──────────────┬──────────────────────────┘ │  │
        │                 │                            │  │
        └─────────────────┬──────────────────────────────┘  │
                          │                                  │
                   ┌──────▼──────┐                           │
                   │  OUTPUT:    │                           │
                   │             │                           │
                   │ • State     │                           │
                   │ • Stats     │                           │
                   │ • Feedback  │                           │
                   │ • Dataset   │                           │
                   │             │                           │
                   └─────────────┘                           │
                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Component Interaction Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                   AGENT INTERACTION LOOP                        │
│                                                                 │
│  ┌──────────────┐     ┌──────────────────┐                     │
│  │ Screenshot   │────▶│ Perception       │                     │
│  │ Capture      │     │ Router           │                     │
│  └──────────────┘     └────────┬─────────┘                     │
│                                 │                               │
│                        ┌────────▼─────────┐                    │
│                        │ UIElements       │                    │
│                        │ + Semantic State │                    │
│                        └────────┬─────────┘                    │
│                                 │                               │
│                     ┌───────────▼──────────────┐               │
│                     │ Agent Reasoning          │               │
│                     │                          │               │
│                     │ • Find buttons/inputs    │               │
│                     │ • Decide next action     │               │
│                     │ • Predict likely outcomes│               │
│                     └───────────┬──────────────┘               │
│                                 │                               │
│                        ┌────────▼──────────┐                   │
│                        │ Execute Action    │                   │
│                        │ (click, type, etc)│                   │
│                        └────────┬──────────┘                   │
│                                 │                               │
│                        ┌────────▼──────────┐                   │
│                        │ Action Result    │                   │
│                        │ (success/fail)    │                   │
│                        └────────┬──────────┘                   │
│                                 │                               │
│                        ┌────────▼──────────┐                   │
│                        │ Feedback Logger  │                   │
│                        │                  │                   │
│                        │ mark_feedback()  │                   │
│                        └──────────────────┘                    │
│                                 │                               │
│                    [REPEAT LOOP - Continuous Improvement]      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## VLM Providers Comparison

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│              VLM PROVIDER COMPARISON                         │
│                                                              │
├──────────────────┬─────────────┬──────────┬────────────────┤
│ Provider         │ Speed       │ Quality  │ Cost per Image │
├──────────────────┼─────────────┼──────────┼────────────────┤
│ Claude (3.5      │ 2-5 sec     │ ⭐⭐⭐⭐⭐  │ ~$0.02         │
│ Sonnet)          │             │          │                │
│                  │             │          │                │
│ GPT-4V           │ 3-8 sec     │ ⭐⭐⭐⭐   │ ~$0.03         │
│                  │             │          │                │
│ LLaVA (Local)    │ 5-15 sec*   │ ⭐⭐⭐    │ $0 (local)     │
│                  │ *depends on │          │                │
│                  │  hardware   │          │                │
│                  │             │          │                │
│ Qwen (Local)     │ 2-10 sec*   │ ⭐⭐⭐⭐  │ $0 (local)     │
└──────────────────┴─────────────┴──────────┴────────────────┘

Recommendation:
├─ Development/Testing → Claude (best balance)
├─ Production Accuracy → Claude (best quality)
├─ Privacy Required → Local VLM (Qwen)
├─ Cost Sensitive → Local VLM or YOLO fast-path
└─ Research → Try all, compare results
```

## Data Flow Diagram

```
DETECTION FLOW:
═════════════════════════════════════════════════════════════

  Image Input
      │
      ├─────► Perception Router
      │           │
      │       ┌───┴──┬──────────┬──────────┐
      │       │      │          │          │
      │       ▼      ▼          ▼          ▼
      │     Strategy:        YOLO         VLM
      │     Decision      (if available)  (always)
      │       │              │            │
      │       └──────┬───────┴────────────┘
      │              │
      │              ▼
      │        Detection Results
      │        (raw bboxes)
      │              │
      │              ▼
      │        Grounding Layer
      │        ├─ BBox Refiner
      │        └─ Overlap Resolver
      │              │
      │              ▼
      │        Refined Bboxes
      │              │
      │              ▼
      │        Semantic State
      │        Builder
      │              │
      │              ▼
      │        Semantic State
      │        (structured)
      │              │
      │              ▼
      │        Feedback Logger
      │              │
      └─────────────►OUTPUT
                  (State + Stats)


FEEDBACK LOOP:
═════════════════════════════════════════════════════════════

  State Output
      │
      ▼
  Agent Decision
      │
      ▼
  Action Execution
      │
      ▼
  Action Result
      │
      ├─ Success? ─────────────────┐
      │                            │
      ▼                            ▼
  Log Event            Feedback Logger
      │                 │
      ├─ Success        ├─ Record Success
      │ Feedback        │
      │                 ├─ Update Stats
      └─────┬───────────┤
            │           ├─ Store in:
            │           │ data/feedback/positive/
            ▼           │
        Statistics      ▼
        Collection   Training Dataset
                     Export
```

## Processing Pipeline Stages

```
STAGE 1: IMAGE CAPTURE
────────────────────────
Input:  Screenshot image file
Output: Raw image (BGR format)
Time:   ~0 ms (file I/O)

    ↓

STAGE 2: DETECTION (VLM/YOLO)
────────────────────────────
Input:  Raw image
Output: Elements with bboxes, types, confidence
Time:   ~100-5000 ms depending on strategy
        (YOLO: 100-300ms, VLM: 2-5s, Hybrid: ~2s)

    ↓

STAGE 3: GROUNDING (REFINEMENT)
────────────────────────────
Input:  Raw detected elements
Output: Refined bboxes, merged/filtered elements
Time:   ~200-500 ms

    ↓

STAGE 4: SEMANTIC INTERPRETATION
────────────────────────────
Input:  Refined UI elements
Output: Semantic state (roles, groups, relationships)
Time:   ~50-100 ms

    ↓

STAGE 5: FEEDBACK & LOGGING
────────────────────────────
Input:  Semantic state + action result
Output: Stored feedback, statistics, datasets
Time:   ~10-50 ms


TOTAL PIPELINE TIME:
• YOLO fast-path: ~400-600 ms
• VLM path: ~2.5-5.5 seconds
• Hybrid (YOLO works): ~400-600 ms
• Hybrid (fallback to VLM): ~2.5-5.5 seconds
```

---

## Class Hierarchy

```
UIElement (dataclass)
├─ id: str
├─ type: str
├─ label: str
├─ description: str
├─ state: str
├─ bbox: Tuple[float, float, float, float]
├─ confidence: float
└─ raw_data: Optional[Dict]

UIAnalysisResult (dataclass)
├─ elements: List[UIElement]
├─ page_structure: Optional[Dict]
├─ raw_response: Optional[str]
├─ parse_successful: bool
└─ parse_error: Optional[str]

VLMClient (ABC)
├─ ClaudeVLMClient
├─ GPT4VClient
└─ LocalVLMClient

PerceptionRouter
├─ vlm_client: Optional[VLMClient]
├─ yolo_model: Optional[YOLO]
├─ bbox_refiner: BBoxRefiner
└─ overlap_resolver: OverlapResolver

SemanticStateBuilder
├─ element_roles: Dict[str, str]
└─ Methods for state building

FeedbackLogger
├─ feedback_dir: str
├─ current_session_log: List[Dict]
└─ Methods for logging & analytics
```

---

This architecture provides:
- **Flexibility** - Multiple VLM providers, strategies
- **Robustness** - Multiple fallback paths
- **Scalability** - Modular components
- **Intelligibility** - Clear data flow
- **Continuity** - Feedback loop for improvement
