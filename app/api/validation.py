from fastapi import APIRouter, Body, HTTPException
from typing import Optional
from app.schemas.geometry import FloorPlanLayout
from app.schemas.project import SpaceRequirement, DesignRelationships, ConfigurableConstraints
from app.schemas.validation import ValidationReport, AutoFixResponse
from app.geometry.engine import GeometryValidationEngine
from app.geometry.auto_fix import AutoFixEngine
from pydantic import BaseModel

class ValidateRequest(BaseModel):
    layout: FloorPlanLayout
    required_spaces: Optional[list[SpaceRequirement]] = None
    relationships: Optional[DesignRelationships] = None
    constraints: Optional[ConfigurableConstraints] = None

class AutoFixStandaloneRequest(BaseModel):
    layout: FloorPlanLayout
    issue_id: Optional[str] = None
    max_cycles: int = 5
    required_spaces: Optional[list[SpaceRequirement]] = None
    relationships: Optional[DesignRelationships] = None
    constraints: Optional[ConfigurableConstraints] = None

router = APIRouter(prefix="/validation", tags=["Validation"])

@router.post("/validate", response_model=ValidationReport)
def validate_floor_plan(payload: ValidateRequest):
    """
    Authoritative computational geometry validation endpoint.
    Executes Shapely spatial checks: plot boundaries, setbacks, polygon overlaps,
    minimum room dimensions, aspect ratios, accessibility, and space utilization.
    """
    return GeometryValidationEngine.validate_layout(
        layout=payload.layout,
        required_spaces=payload.required_spaces,
        relationships=payload.relationships,
        constraints=payload.constraints
    )

@router.post("/auto-fix", response_model=AutoFixResponse)
def auto_fix_in_memory(payload: AutoFixStandaloneRequest):
    """
    Standalone in-memory Auto-Fix endpoint.
    Applies deterministic repair transformations and revalidation loops.
    """
    if payload.issue_id:
        initial_val = GeometryValidationEngine.validate_layout(
            payload.layout,
            required_spaces=payload.required_spaces,
            relationships=payload.relationships,
            constraints=payload.constraints
        )
        target_issue = next((iss for iss in initial_val.issues if iss.id == payload.issue_id), None)
        if not target_issue:
            raise HTTPException(status_code=404, detail=f"Validation issue '{payload.issue_id}' not found in layout")

        fixed_layout, diffs = AutoFixEngine.fix_single_issue(
            layout=payload.layout,
            issue=target_issue,
            constraints=payload.constraints,
            required_spaces=payload.required_spaces,
            relationships=payload.relationships
        )
        final_val = GeometryValidationEngine.validate_layout(
            fixed_layout,
            required_spaces=payload.required_spaces,
            relationships=payload.relationships,
            constraints=payload.constraints
        )
        is_resolved = len(diffs) > 0 and not any(iss.id == payload.issue_id for iss in final_val.issues)
        success = is_resolved and final_val.error_count <= initial_val.error_count
        resolved_count = 1 if is_resolved else 0
        explanation = (
            f"Applied targeted repair for '{target_issue.title or target_issue.constraint_type}'."
            if success
            else f"Could not safely repair '{target_issue.title or target_issue.constraint_type}' without violating other spatial constraints. Active layout preserved."
        )
        return AutoFixResponse(
            success=success,
            cycles_run=1,
            resolved_issues_count=resolved_count,
            remaining_issues_count=len(final_val.issues),
            fixed_layout=fixed_layout,
            initial_validation=initial_val,
            final_validation=final_val,
            revisions_applied=diffs,
            rejected_attempts=[] if success else [explanation],
            explanation=explanation
        )
    else:
        result = AutoFixEngine.auto_fix_all(
            layout=payload.layout,
            constraints=payload.constraints,
            required_spaces=payload.required_spaces,
            relationships=payload.relationships,
            max_cycles=payload.max_cycles
        )
        return AutoFixResponse(
            success=result["is_success"] or result["resolved_issues_count"] > 0,
            cycles_run=result["cycles_run"],
            resolved_issues_count=result["resolved_issues_count"],
            remaining_issues_count=result["remaining_issues_count"],
            fixed_layout=result["fixed_layout"],
            initial_validation=result["initial_validation"],
            final_validation=result["final_validation"],
            revisions_applied=result["revisions_applied"],
            rejected_attempts=result.get("rejected_attempts", []),
            explanation=f"Auto-Fix All executed {result['cycles_run']} iteration cycles. Resolved {result['resolved_issues_count']} issues. {result['remaining_issues_count']} issues remaining."
        )
