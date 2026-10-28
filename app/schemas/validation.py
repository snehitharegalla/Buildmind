from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from app.schemas.geometry import FloorPlanLayout

class SeverityLevel(str, Enum):
    ERROR = "error"     # Hard constraint violation: blocks formal signoff
    WARNING = "warning" # Soft preference or sub-optimal trade-off
    INFO = "info"       # Architectural advisory or metric note

class ConstraintCategory(str, Enum):
    PLOT_BOUNDARY = "plot_boundary"
    SETBACK_VIOLATION = "setback_violation"
    ROOM_OVERLAP = "room_overlap"
    INVALID_GEOMETRY = "invalid_geometry"
    MIN_DIMENSION = "min_dimension"
    MAX_DIMENSION = "max_dimension"
    ASPECT_RATIO = "aspect_ratio"
    MISSING_ROOM = "missing_room"
    CIRCULATION = "circulation"
    ACCESSIBILITY = "accessibility"
    DOOR_WINDOW_PLACEMENT = "door_window_placement"
    PRIVACY_ADJACENCY = "privacy_adjacency"
    RESIDUAL_SPACE = "residual_space"
    SPACE_UTILIZATION = "space_utilization"

class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    length: float

class ValidationIssue(BaseModel):
    id: str
    title: Optional[str] = None
    constraint_type: ConstraintCategory
    severity: SeverityLevel
    affected_rooms: List[str] = Field(default_factory=list)
    affected_element_ids: List[str] = Field(default_factory=list)
    measured_value: str
    expected_condition: str
    explanation: str
    suggested_correction: str
    bounding_box: Optional[BoundingBox] = None
    can_auto_fix: bool = True

    @model_validator(mode="before")
    @classmethod
    def set_defaults(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("title"):
                ctype = str(data.get("constraint_type", "")).lower()
                type_titles = {
                    "room_overlap": "Room Boundary Overlap",
                    "setback_violation": "Setback Boundary Breach",
                    "plot_boundary": "Plot Boundary Exceeded",
                    "min_dimension": "Sub-Minimum Room Dimension",
                    "max_dimension": "Exceeded Room Dimension",
                    "aspect_ratio": "Unfavorable Aspect Ratio",
                    "missing_room": "Missing Required Room",
                    "privacy_adjacency": "Privacy & Separation Issue",
                    "circulation": "Circulation Access Blocked",
                    "accessibility": "Door Opening Clearance Issue",
                    "invalid_geometry": "Geometric Polygon Anomaly",
                    "residual_space": "Unusable Residual Space",
                    "space_utilization": "Space Utilization Warning",
                }
                data["title"] = type_titles.get(ctype, "Spatial Constraint Issue")
            if "can_auto_fix" not in data:
                ctype = str(data.get("constraint_type", "")).lower()
                non_fixable = {"residual_space", "space_utilization"}
                data["can_auto_fix"] = ctype not in non_fixable
        return data

class ValidationMetrics(BaseModel):
    plot_area: float
    buildable_area: float
    built_up_area: float
    carpet_area: float
    circulation_area: float
    ground_coverage_ratio: float # built_up / plot_area (0.0 - 1.0)
    carpet_to_builtup_ratio: float
    room_count: int
    openings_count: int
    hard_violations_count: int
    warning_count: int

class ValidationReport(BaseModel):
    is_valid: bool = Field(description="True if zero hard constraint errors")
    hard_constraints_passed: bool
    error_count: int
    warning_count: int
    info_count: int
    issues: List[ValidationIssue] = Field(default_factory=list)
    metrics: ValidationMetrics
    summary: str = ""
    timestamp: Optional[str] = None

class AutoFixRequest(BaseModel):
    issue_id: Optional[str] = None
    preview_only: bool = False
    max_cycles: int = 5

class AutoFixResponse(BaseModel):
    success: bool
    cycles_run: int
    resolved_issues_count: int
    remaining_issues_count: int
    fixed_layout: FloorPlanLayout
    initial_validation: ValidationReport
    final_validation: ValidationReport
    revisions_applied: List[Dict[str, Any]] = Field(default_factory=list)
    rejected_attempts: List[str] = Field(default_factory=list)
    explanation: str
