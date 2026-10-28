from typing import List
from shapely.geometry import box
from app.schemas.geometry import FloorPlanLayout, RoomGeometry
from app.schemas.validation import ValidationIssue, SeverityLevel, ConstraintCategory, BoundingBox

def check_room_overlaps(layout: FloorPlanLayout) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    rooms = layout.rooms
    n = len(rooms)
    plot_unit = layout.plot.unit

    # Check pairwise room overlaps
    for i in range(n):
        r1 = rooms[i]
        poly1 = box(r1.x, r1.y, r1.x + r1.width, r1.y + r1.length)

        for j in range(i + 1, n):
            r2 = rooms[j]
            poly2 = box(r2.x, r2.y, r2.x + r2.width, r2.y + r2.length)

            if poly1.intersects(poly2):
                intersection = poly1.intersection(poly2)
                overlap_area = intersection.area

                # Threshold to ignore touching wall edges (floating point tolerance)
                if overlap_area > 0.1:
                    minx, miny, maxx, maxy = intersection.bounds
                    issues.append(
                        ValidationIssue(
                            id=f"overlap_{r1.id}_{r2.id}",
                            constraint_type=ConstraintCategory.ROOM_OVERLAP,
                            severity=SeverityLevel.ERROR,
                            affected_rooms=[r1.name, r2.name],
                            affected_element_ids=[r1.id, r2.id],
                            measured_value=f"Intersection area: {overlap_area:.2f} sq {plot_unit} ({maxx - minx:.1f} × {maxy - miny:.1f} {plot_unit})",
                            expected_condition="0 sq units overlap (disjoint partition walls)",
                            explanation=f"Collision detected between '{r1.name}' and '{r2.name}'. Two physical functional rooms cannot occupy the same spatial envelope.",
                            suggested_correction=f"Adjust boundary between '{r1.name}' and '{r2.name}' so their partition wall meets flush without overlapping polygons.",
                            bounding_box=BoundingBox(
                                x=minx,
                                y=miny,
                                width=maxx - minx,
                                length=maxy - miny
                            )
                        )
                    )

    return issues
