from typing import List, Set
from shapely.geometry import box
from app.schemas.geometry import FloorPlanLayout, RoomType, OpeningType
from app.schemas.validation import ValidationIssue, SeverityLevel, ConstraintCategory, BoundingBox

def check_accessibility_and_openings(
    layout: FloorPlanLayout,
    accessibility_mode: bool = False,
    min_corridor_width: float = 3.0,
    min_door_clearance: float = 2.8
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    unit = layout.plot.unit
    rooms_by_id = {r.id: r for r in layout.rooms}

    # Effective required door width
    target_door_w = 3.0 if accessibility_mode else min_door_clearance
    target_corridor_w = 3.5 if accessibility_mode else min_corridor_width

    # 1. Check Corridor dimensions
    for room in layout.rooms:
        r_type = room.room_type.value if hasattr(room.room_type, "value") else str(room.room_type)
        if r_type == RoomType.CORRIDOR.value:
            narrow_dim = min(room.width, room.length)
            if narrow_dim < target_corridor_w:
                issues.append(
                    ValidationIssue(
                        id=f"corridor_width_{room.id}",
                        constraint_type=ConstraintCategory.ACCESSIBILITY,
                        severity=SeverityLevel.ERROR if accessibility_mode else SeverityLevel.WARNING,
                        affected_rooms=[room.name],
                        affected_element_ids=[room.id],
                        measured_value=f"Width {narrow_dim:.1f} {unit}",
                        expected_condition=f">= {target_corridor_w:.1f} {unit} clear passage width",
                        explanation=f"Circulation corridor '{room.name}' restricts wheelchair/furniture passage.",
                        suggested_correction=f"Widen corridor '{room.name}' to at least {target_corridor_w:.1f} {unit}.",
                        bounding_box=BoundingBox(x=room.x, y=room.y, width=room.width, length=room.length)
                    )
                )

    # 2. Check Openings: Door clearances & placements
    rooms_with_doors: Set[str] = set()
    rooms_with_windows: Set[str] = set()

    for opening in layout.openings:
        op_type = opening.type.value if hasattr(opening.type, "value") else str(opening.type)
        room = rooms_by_id.get(opening.room_id)
        room_name = room.name if room else "Unknown Room"

        if op_type in [OpeningType.DOOR.value, OpeningType.DOUBLE_DOOR.value, OpeningType.SLIDING_DOOR.value]:
            rooms_with_doors.add(opening.room_id)
            if opening.width < target_door_w:
                issues.append(
                    ValidationIssue(
                        id=f"door_narrow_{opening.id}",
                        constraint_type=ConstraintCategory.ACCESSIBILITY,
                        severity=SeverityLevel.WARNING,
                        affected_rooms=[room_name],
                        affected_element_ids=[opening.id],
                        measured_value=f"Door width {opening.width:.1f} {unit}",
                        expected_condition=f">= {target_door_w:.1f} {unit} clear leaf width",
                        explanation=f"Door in '{room_name}' is narrower than standard accessibility clearance ({target_door_w:.1f} {unit}).",
                        suggested_correction=f"Increase door leaf opening to {target_door_w:.1f} {unit}.",
                        bounding_box=BoundingBox(x=room.x, y=room.y, width=room.width, length=room.length) if room else None
                    )
                )
        elif op_type == OpeningType.WINDOW.value:
            rooms_with_windows.add(opening.room_id)

    # 3. Check Natural Ventilation in Habitable Rooms
    habitable_types = {RoomType.BEDROOM.value, RoomType.MASTER_BEDROOM.value, RoomType.LIVING_ROOM.value, RoomType.STUDY.value}
    for room in layout.rooms:
        r_type = room.room_type.value if hasattr(room.room_type, "value") else str(room.room_type)
        if r_type in habitable_types and room.id not in rooms_with_windows:
            issues.append(
                ValidationIssue(
                    id=f"ventilation_{room.id}",
                    constraint_type=ConstraintCategory.DOOR_WINDOW_PLACEMENT,
                    severity=SeverityLevel.WARNING,
                    affected_rooms=[room.name],
                    affected_element_ids=[room.id],
                    measured_value="0 exterior windows",
                    expected_condition="At least 1 window to an exterior perimeter wall",
                    explanation=f"Habitable space '{room.name}' lacks natural fenestration/daylight access.",
                    suggested_correction=f"Place an exterior window along an outer wall for '{room.name}' to meet residential daylighting standards.",
                    bounding_box=BoundingBox(x=room.x, y=room.y, width=room.width, length=room.length)
                )
            )

    return issues
