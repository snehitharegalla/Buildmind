from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.geometry import PlotGeometry, FloorPlanLayout, RoomGeometry
from app.schemas.validation import ValidationReport

class SpaceRequirement(BaseModel):
    id: str
    room_type: str = "bedroom"
    label: str = "Bedroom"
    quantity: int = 1
    preferred_width: float = 12.0
    preferred_length: float = 12.0
    min_width: float = 9.0
    min_length: float = 9.0
    is_mandatory: bool = True
    level: int = 1
    preferred_orientation: Optional[str] = None # north, south, east, west

class AdjacencyPreference(BaseModel):
    room_a_type: str
    room_b_type: str
    relationship: str = "adjacent" # adjacent, separated, connected_by_door

class DesignRelationships(BaseModel):
    adjacencies: List[AdjacencyPreference] = Field(default_factory=list)
    privacy_levels: Dict[str, str] = Field(default_factory=dict) # e.g. {"bedroom": "high", "living_room": "low"}
    entrance_room: str = "living_room"
    accessibility_mode: bool = False
    natural_ventilation_priority: bool = True

class ProjectPreferences(BaseModel):
    budget_range: str = "moderate" # compact, moderate, luxury
    architectural_style: str = "contemporary_warm" # modern_minimal, contemporary_warm, courtyard_vernacular, brutalist_raw
    space_utilization_priority: str = "balanced" # maximum_density, balanced, spacious_comfort
    wall_thickness_exterior: float = 0.75 # 9 inches
    wall_thickness_interior: float = 0.38 # 4.5 inches
    estimated_cost_per_sqft: float = 180.0

class ConfigurableConstraints(BaseModel):
    enforce_setbacks: bool = True
    min_corridor_width: float = 3.0
    min_door_clearance: float = 2.8
    max_aspect_ratio: float = 2.4
    min_aspect_ratio: float = 0.45
    min_habitable_area: float = 70.0 # sqft

class ProjectCreate(BaseModel):
    name: str = "New Architecture Project"
    description: Optional[str] = "Preliminary residential design"
    plot: PlotGeometry
    spaces: List[SpaceRequirement]
    relationships: DesignRelationships = Field(default_factory=DesignRelationships)
    preferences: ProjectPreferences = Field(default_factory=ProjectPreferences)
    constraints: ConfigurableConstraints = Field(default_factory=ConfigurableConstraints)
    preset_name: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    plot: Optional[PlotGeometry] = None
    spaces: Optional[List[SpaceRequirement]] = None
    relationships: Optional[DesignRelationships] = None
    preferences: Optional[ProjectPreferences] = None
    constraints: Optional[ConfigurableConstraints] = None
    selected_layout_id: Optional[str] = None

class RevisionSummary(BaseModel):
    id: str
    iteration: int
    trigger_reason: str
    prompt_request: Optional[str]
    changes_made: List[str]
    resolved_all_errors: bool
    created_at: datetime

class LayoutSummary(BaseModel):
    id: str
    version: int
    name: str
    variant_type: str
    total_built_up_area: float
    carpet_area: float
    efficiency_ratio: float
    is_favorite: bool
    created_at: datetime

class ProjectSummaryResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    plot_width: float
    plot_length: float
    total_area: float
    unit: str
    layout_count: int
    selected_layout_id: Optional[str]
    room_count: int = 0
    preview_rooms: List[Dict[str, Any]] = Field(default_factory=list)

class ProjectDetailResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    plot: PlotGeometry
    spaces: List[SpaceRequirement]
    relationships: DesignRelationships
    preferences: ProjectPreferences
    constraints: ConfigurableConstraints
    selected_layout: Optional[FloorPlanLayout] = None
    layouts: List[FloorPlanLayout] = Field(default_factory=list)
    revisions: List[RevisionSummary] = Field(default_factory=list)
