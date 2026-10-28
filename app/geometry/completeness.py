from typing import List
from collections import Counter
from app.schemas.geometry import FloorPlanLayout
from app.schemas.project import SpaceRequirement
from app.schemas.validation import ValidationIssue, SeverityLevel, ConstraintCategory

def check_required_rooms_completeness(
    layout: FloorPlanLayout,
    required_spaces: List[SpaceRequirement]
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    
    if not required_spaces:
        return issues

    # Count actual rooms by room_type
    actual_counts = Counter(
        r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type)
        for r in layout.rooms
    )

    for req in required_spaces:
        if not req.is_mandatory:
            continue

        r_type = req.room_type
        needed_qty = req.quantity
        if r_type == "bedroom":
            present_qty = actual_counts.get("bedroom", 0) + actual_counts.get("master_bedroom", 0)
        else:
            present_qty = actual_counts.get(r_type, 0)

        if present_qty < needed_qty:
            missing_qty = needed_qty - present_qty
            issues.append(
                ValidationIssue(
                    id=f"missing_room_{req.id}_{r_type}",
                    constraint_type=ConstraintCategory.MISSING_ROOM,
                    severity=SeverityLevel.ERROR,
                    affected_rooms=[req.label],
                    affected_element_ids=[req.id],
                    measured_value=f"Present: {present_qty} | Required: {needed_qty}",
                    expected_condition=f"{needed_qty} × {req.label} ({r_type}) present in layout",
                    explanation=f"Required architectural program '{req.label}' is missing {missing_qty} space(s) from the floor plan.",
                    suggested_correction=f"Allocate space for {missing_qty} additional '{req.label}' within the buildable envelope.",
                    bounding_box=None
                )
            )

    return issues
