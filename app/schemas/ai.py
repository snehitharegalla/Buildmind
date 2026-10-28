from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.geometry import FloorPlanLayout, RoomGeometry, OpeningGeometry, WallGeometry
from app.schemas.validation import ValidationReport

class GenerationRequest(BaseModel):
    project_id: str
    target_variants: List[str] = Field(
        default=["space_optimized", "comfort_focused", "budget_conscious"],
        description="Candidate layout variants to produce"
    )
    user_guidance: Optional[str] = None
    max_revisions: int = 3

class LayoutCandidate(BaseModel):
    variant_type: str
    title: str
    layout: FloorPlanLayout
    validation: ValidationReport
    generation_mode: str # 'llm_api' or 'demo_geometric_solver'
    design_notes: str

class GenerationResult(BaseModel):
    project_id: str
    candidates: List[LayoutCandidate]
    primary_layout: FloorPlanLayout
    primary_validation: ValidationReport
    revision_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    generation_mode: str # 'gemini' | 'openai' | 'anthropic' | 'demo_geometric_solver'
    provider_label: str
    is_demo_mode: bool = False

class CopilotActionType(str):
    UPDATE_ROOM = "update_room"
    ADD_ROOM = "add_room"
    REMOVE_ROOM = "remove_room"
    RESIZE_ROOM = "resize_room"
    EXPLAIN_VALIDATION = "explain_validation"
    SUGGEST_IMPROVEMENTS = "suggest_improvements"
    GENERAL_QUERY = "general_query"

class ProposedDiff(BaseModel):
    action: str
    target_room_name: Optional[str] = None
    target_room_id: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    description: str

class ProposedModification(BaseModel):
    id: str
    action_type: str
    title: str
    explanation: str
    diffs: List[ProposedDiff] = Field(default_factory=list)
    preview_layout: FloorPlanLayout
    preview_validation: ValidationReport
    conflicts_detected: List[str] = Field(default_factory=list)

class CopilotChatRequest(BaseModel):
    project_id: str
    layout_id: str
    message: str
    current_layout: Optional[FloorPlanLayout] = None

class CopilotChatResponse(BaseModel):
    message_id: str
    response_text: str
    proposed_modification: Optional[ProposedModification] = None
    applied_layout: Optional[FloorPlanLayout] = None
    validation: Optional[ValidationReport] = None
    provider_label: str
