from typing import List, Tuple
from shapely.geometry import box, Polygon
from app.schemas.geometry import FloorPlanLayout, RoomGeometry, PlotGeometry
from app.schemas.validation import ValidationIssue, SeverityLevel, ConstraintCategory, BoundingBox

def check_plot_and_setback_boundaries(
    layout: FloorPlanLayout,
    enforce_setbacks: bool = True
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    plot = layout.plot

    # Plot rectangle: (0, 0) to (plot.width, plot.length)
    plot_poly = box(0, 0, plot.width, plot.length)

    # Buildable area considering setbacks
    b_min_x = plot.setback_left
    b_max_x = plot.width - plot.setback_right
    b_min_y = plot.setback_front
    b_max_y = plot.length - plot.setback_rear

    # Ensure buildable coordinates make sense
    if b_max_x <= b_min_x or b_max_y <= b_min_y:
        b_poly = plot_poly
    else:
        b_poly = box(b_min_x, b_min_y, b_max_x, b_max_y)

    for room in layout.rooms:
        r_x1 = room.x
        r_y1 = room.y
        r_x2 = room.x + room.width
        r_y2 = room.y + room.length
        room_poly = box(r_x1, r_y1, r_x2, r_y2)

        # 1. Hard Check: Room outside plot boundary
        if not plot_poly.contains(room_poly):
            # Calculate breach area or extent
            breach = room_poly.difference(plot_poly)
            breach_area = breach.area
            
            # Find which edge was breached
            exceeded_edges = []
            if r_x1 < 0: exceeded_edges.append(f"Left edge by {abs(r_x1):.1f}{plot.unit}")
            if r_x2 > plot.width: exceeded_edges.append(f"Right edge by {(r_x2 - plot.width):.1f}{plot.unit}")
            if r_y1 < 0: exceeded_edges.append(f"Front edge by {abs(r_y1):.1f}{plot.unit}")
            if r_y2 > plot.length: exceeded_edges.append(f"Rear edge by {(r_y2 - plot.length):.1f}{plot.unit}")

            issues.append(
                ValidationIssue(
                    id=f"boundary_breach_{room.id}",
                    constraint_type=ConstraintCategory.PLOT_BOUNDARY,
                    severity=SeverityLevel.ERROR,
                    affected_rooms=[room.name],
                    affected_element_ids=[room.id],
                    measured_value=f"Bounds: [{r_x1:.1f}, {r_y1:.1f}] to [{r_x2:.1f}, {r_y2:.1f}] {plot.unit}. Breach: {', '.join(exceeded_edges)}",
                    expected_condition=f"Within plot boundaries (0 to {plot.width:.1f} × 0 to {plot.length:.1f} {plot.unit})",
                    explanation=f"Room '{room.name}' extends beyond the outer property boundary by {breach_area:.1f} sq {plot.unit}.",
                    suggested_correction=f"Reposition '{room.name}' inward or reduce its dimensions to fit within the {plot.width:.1f} × {plot.length:.1f} {plot.unit} plot envelope.",
                    bounding_box=BoundingBox(
                        x=max(0.0, r_x1),
                        y=max(0.0, r_y1),
                        width=room.width,
                        length=room.length
                    )
                )
            )

        # 2. Check Setbacks (Hard or Warning based on enforce_setbacks)
        elif enforce_setbacks and not b_poly.contains(room_poly):
            setback_encroachments = []
            if r_x1 < b_min_x: setback_encroachments.append(f"Left setback encroached by {(b_min_x - r_x1):.1f}{plot.unit}")
            if r_x2 > b_max_x: setback_encroachments.append(f"Right setback encroached by {(r_x2 - b_max_x):.1f}{plot.unit}")
            if r_y1 < b_min_y: setback_encroachments.append(f"Front setback encroached by {(b_min_y - r_y1):.1f}{plot.unit}")
            if r_y2 > b_max_y: setback_encroachments.append(f"Rear setback encroached by {(r_y2 - b_max_y):.1f}{plot.unit}")

            issues.append(
                ValidationIssue(
                    id=f"setback_violation_{room.id}",
                    constraint_type=ConstraintCategory.SETBACK_VIOLATION,
                    severity=SeverityLevel.ERROR if enforce_setbacks else SeverityLevel.WARNING,
                    affected_rooms=[room.name],
                    affected_element_ids=[room.id],
                    measured_value=f"{', '.join(setback_encroachments)}",
                    expected_condition=f"Front >= {plot.setback_front:.1f}{plot.unit}, Rear >= {plot.setback_rear:.1f}{plot.unit}, Sides >= {plot.setback_left:.1f}/{plot.setback_right:.1f}{plot.unit}",
                    explanation=f"Room '{room.name}' encroaches into the statutory building setback zone.",
                    suggested_correction=f"Shift '{room.name}' inside the buildable envelope ({b_min_x:.1f} to {b_max_x:.1f} X, {b_min_y:.1f} to {b_max_y:.1f} Y).",
                    bounding_box=BoundingBox(
                        x=room.x,
                        y=room.y,
                        width=room.width,
                        length=room.length
                    )
                )
            )

    return issues
