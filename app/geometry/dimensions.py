from typing import List, Dict
from app.schemas.geometry import FloorPlanLayout, RoomGeometry, RoomType
from app.schemas.validation import ValidationIssue, SeverityLevel, ConstraintCategory, BoundingBox

ROOM_MINIMUMS: Dict[str, Dict[str, float]] = {
    RoomType.BEDROOM.value: {"min_w": 9.0, "min_l": 9.0, "min_area": 81.0},
    RoomType.MASTER_BEDROOM.value: {"min_w": 10.0, "min_l": 11.0, "min_area": 110.0},
    RoomType.LIVING_ROOM.value: {"min_w": 10.0, "min_l": 11.0, "min_area": 115.0},
    RoomType.KITCHEN.value: {"min_w": 5.5, "min_l": 7.0, "min_area": 42.0},
    RoomType.BATHROOM.value: {"min_w": 4.0, "min_l": 4.5, "min_area": 20.0},
    RoomType.DINING.value: {"min_w": 7.5, "min_l": 8.0, "min_area": 60.0},
    RoomType.STAIRCASING.value: {"min_w": 5.5, "min_l": 7.0, "min_area": 40.0},
    RoomType.CORRIDOR.value: {"min_w": 3.0, "min_l": 3.0, "min_area": 12.0},
    RoomType.BALCONY.value: {"min_w": 3.0, "min_l": 4.0, "min_area": 15.0},
    RoomType.FOYER.value: {"min_w": 4.0, "min_l": 4.0, "min_area": 16.0},
    RoomType.UTILITY.value: {"min_w": 3.5, "min_l": 4.0, "min_area": 15.0},
    RoomType.PARKING.value: {"min_w": 9.0, "min_l": 15.0, "min_area": 140.0},
}

def check_room_dimensions_and_proportions(
    layout: FloorPlanLayout,
    max_aspect_ratio: float = 2.4,
    min_aspect_ratio: float = 0.42
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    unit = layout.plot.unit

    for room in layout.rooms:
        r_type = room.room_type.value if hasattr(room.room_type, "value") else str(room.room_type)
        min_spec = ROOM_MINIMUMS.get(r_type, {"min_w": 6.0, "min_l": 6.0, "min_area": 36.0})

        # Calculate actual geometric area
        actual_area = room.width * room.length
        smaller_dim = min(room.width, room.length)
        larger_dim = max(room.width, room.length)

        # 1. Orientation-invariant Minimum Dimension & Area Check (Hard Error)
        # Architectural codes evaluate clear width (smaller dimension), span (larger dimension), and net area
        req_min_clear = min(min_spec["min_w"], min_spec["min_l"])
        req_min_span = max(min_spec["min_w"], min_spec["min_l"])
        req_min_area = min_spec.get("min_area", req_min_clear * req_min_span)

        failed_dim = []
        if smaller_dim < req_min_clear - 0.05:
            failed_dim.append(f"Clear width {smaller_dim:.1f}{unit} < min {req_min_clear:.1f}{unit}")
        if larger_dim < req_min_span - 0.05:
            failed_dim.append(f"Span {larger_dim:.1f}{unit} < min {req_min_span:.1f}{unit}")
        if actual_area < req_min_area - 0.05:
            failed_dim.append(f"Area {actual_area:.1f} sq {unit} < min {req_min_area:.1f} sq {unit}")

        if failed_dim:
            issues.append(
                ValidationIssue(
                    id=f"dim_min_{room.id}",
                    constraint_type=ConstraintCategory.MIN_DIMENSION,
                    severity=SeverityLevel.ERROR,
                    affected_rooms=[room.name],
                    affected_element_ids=[room.id],
                    measured_value=f"{room.width:.1f} × {room.length:.1f} {unit} ({actual_area:.1f} sq {unit})",
                    expected_condition=f"Minimum {req_min_clear:.1f} × {req_min_span:.1f} {unit} (Area >= {req_min_area:.1f} sq {unit})",
                    explanation=f"'{room.name}' fails standard residential architectural code for {r_type.replace('_', ' ')}. {', '.join(failed_dim)}.",
                    suggested_correction=f"Expand '{room.name}' to at least {req_min_clear:.1f} × {req_min_span:.1f} {unit} to ensure functional clearance.",
                    bounding_box=BoundingBox(
                        x=room.x,
                        y=room.y,
                        width=room.width,
                        length=room.length
                    )
                )
            )

        # 2. Aspect Ratio Proportion Check (Warning for Habitable Spaces)
        # Corridors, vestibules, balconies, and utility passages naturally require elongated proportions
        is_circulation_or_utility = (
            r_type in [RoomType.CORRIDOR.value, RoomType.BALCONY.value, RoomType.UTILITY.value, RoomType.PARKING.value]
            or any(tag in (room.tags or []) for tag in ["circulation", "buffer", "vestibule", "corridor", "utility", "passage"])
            or "vestibule" in room.name.lower()
            or "corridor" in room.name.lower()
            or "passage" in room.name.lower()
        )
        if room.width > 0 and room.length > 0 and not is_circulation_or_utility:
            ratio = room.width / room.length
            if ratio > max_aspect_ratio or ratio < min_aspect_ratio:
                norm_ratio = larger_dim / smaller_dim
                issues.append(
                    ValidationIssue(
                        id=f"aspect_ratio_{room.id}",
                        constraint_type=ConstraintCategory.ASPECT_RATIO,
                        severity=SeverityLevel.WARNING,
                        affected_rooms=[room.name],
                        affected_element_ids=[room.id],
                        measured_value=f"Aspect ratio {norm_ratio:.2f}:1 ({room.width:.1f} × {room.length:.1f} {unit})",
                        expected_condition=f"Proportion between 1:1 and {max_aspect_ratio:.1f}:1 for habitable spaces",
                        explanation=f"'{room.name}' is excessively elongated/tunnel-shaped, resulting in inefficient furniture arrangement and poor natural lighting distribution.",
                        suggested_correction=f"Squarify '{room.name}' to bring the aspect ratio closer to 1.2:1 - 1.5:1.",
                        bounding_box=BoundingBox(
                            x=room.x,
                            y=room.y,
                            width=room.width,
                            length=room.length
                        )
                    )
                )

        # 3. Maximum Dimension Check (Hard Error if room exceeds plot)
        if room.width > layout.plot.width or room.length > layout.plot.length:
            issues.append(
                ValidationIssue(
                    id=f"dim_max_{room.id}",
                    constraint_type=ConstraintCategory.MAX_DIMENSION,
                    severity=SeverityLevel.ERROR,
                    affected_rooms=[room.name],
                    affected_element_ids=[room.id],
                    measured_value=f"{room.width:.1f} × {room.length:.1f} {unit}",
                    expected_condition=f"<= Plot dimensions ({layout.plot.width:.1f} × {layout.plot.length:.1f} {unit})",
                    explanation=f"Room '{room.name}' spans larger than the entire site.",
                    suggested_correction=f"Reduce '{room.name}' dimensions to fit within building boundaries.",
                    bounding_box=BoundingBox(
                        x=room.x,
                        y=room.y,
                        width=room.width,
                        length=room.length
                    )
                )
            )

    return issues
