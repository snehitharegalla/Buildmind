from typing import List, Dict, Optional
from shapely.geometry import box
from app.schemas.geometry import FloorPlanLayout, RoomType
from app.schemas.project import DesignRelationships
from app.schemas.validation import ValidationIssue, SeverityLevel, ConstraintCategory, BoundingBox

def check_adjacencies_and_privacy(
    layout: FloorPlanLayout,
    relationships: Optional[DesignRelationships] = None
) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    unit = layout.plot.unit
    rooms = layout.rooms

    # Build room polygons and metadata
    room_boxes = {
        r.id: {
            "name": r.name,
            "type": r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type),
            "poly": box(r.x, r.y, r.x + r.width, r.y + r.length),
            "center": (r.x + r.width / 2.0, r.y + r.length / 2.0),
            "room": r
        }
        for r in rooms
    }

    # 1. Check user configured adjacency preferences (if provided)
    if relationships and relationships.adjacencies:
        for adj in relationships.adjacencies:
            type_a = adj.room_a_type
            type_b = adj.room_b_type
            rel = adj.relationship # adjacent, separated

            rooms_a = [info for info in room_boxes.values() if info["type"] == type_a]
            rooms_b = [info for info in room_boxes.values() if info["type"] == type_b]

            if rooms_a and rooms_b:
                for ra in rooms_a:
                    for rb in rooms_b:
                        dist = ra["poly"].distance(rb["poly"])
                        if rel == "adjacent" and dist > 2.0:
                            issues.append(
                                ValidationIssue(
                                    id=f"adj_missing_{ra['room'].id}_{rb['room'].id}",
                                    constraint_type=ConstraintCategory.PRIVACY_ADJACENCY,
                                    severity=SeverityLevel.WARNING,
                                    affected_rooms=[ra["name"], rb["name"]],
                                    affected_element_ids=[ra["room"].id, rb["room"].id],
                                    measured_value=f"Separation distance: {dist:.1f} {unit}",
                                    expected_condition=f"Direct adjacency (distance <= 1.0 {unit})",
                                    explanation=f"'{ra['name']}' ({type_a}) and '{rb['name']}' ({type_b}) are placed far apart despite configured adjacency preference.",
                                    suggested_correction=f"Relocate '{ra['name']}' to share a partition wall with '{rb['name']}'.",
                                    bounding_box=BoundingBox(
                                        x=ra["room"].x,
                                        y=ra["room"].y,
                                        width=ra["room"].width,
                                        length=ra["room"].length
                                    )
                                )
                            )
                        elif rel == "separated" and dist < 1.0:
                            issues.append(
                                ValidationIssue(
                                    id=f"adj_separated_{ra['room'].id}_{rb['room'].id}",
                                    constraint_type=ConstraintCategory.PRIVACY_ADJACENCY,
                                    severity=SeverityLevel.WARNING,
                                    affected_rooms=[ra["name"], rb["name"]],
                                    affected_element_ids=[ra["room"].id, rb["room"].id],
                                    measured_value=f"Sharing partition wall (distance {dist:.1f} {unit})",
                                    expected_condition="Buffer separation required",
                                    explanation=f"'{ra['name']}' and '{rb['name']}' are directly adjacent, violating acoustic/hygiene separation preference.",
                                    suggested_correction=f"Introduce a buffer space or corridor between '{ra['name']}' and '{rb['name']}'.",
                                    bounding_box=BoundingBox(
                                        x=ra["room"].x,
                                        y=ra["room"].y,
                                        width=ra["room"].width,
                                        length=ra["room"].length
                                    )
                                )
                            )

    # 2. Universal Architectural Rule: Bathroom vs Kitchen Placement & Sightlines
    bathrooms = [info for info in room_boxes.values() if info["type"] == RoomType.BATHROOM.value]
    kitchens = [info for info in room_boxes.values() if info["type"] == RoomType.KITCHEN.value]

    for bath in bathrooms:
        b_room = bath["room"]
        b_poly = bath["poly"]
        for kit in kitchens:
            k_room = kit["room"]
            k_poly = kit["poly"]
            dist = b_poly.distance(k_poly)

            # Check direct shared wall
            if dist < 0.2:
                issues.append(
                    ValidationIssue(
                        id=f"privacy_bath_kit_{b_room.id}_{k_room.id}",
                        constraint_type=ConstraintCategory.PRIVACY_ADJACENCY,
                        severity=SeverityLevel.WARNING,
                        affected_rooms=[bath["name"], kit["name"]],
                        affected_element_ids=[b_room.id, k_room.id],
                        measured_value=f"Directly adjacent partition ({dist:.1f} {unit})",
                        expected_condition="Buffer separation (corridor or vestibule)",
                        explanation=f"Bathroom '{bath['name']}' directly abuts Kitchen '{kit['name']}'. Sound, moisture, and odour transfer violate residential hygiene best practices.",
                        suggested_correction="Relocate bathroom to the private circulation corridor or adjacent to the bedroom wing.",
                        bounding_box=BoundingBox(
                            x=b_room.x,
                            y=b_room.y,
                            width=b_room.width,
                            length=b_room.length
                        )
                    )
                )

            # Check direct frontal alignment / facing open kitchen without buffer
            # E.g. Bathroom in front of kitchen (overlapping X-span and distance <= 5 ft)
            overlap_x = max(0.0, min(b_room.x + b_room.width, k_room.x + k_room.width) - max(b_room.x, k_room.x))
            if overlap_x > 3.0 and dist < 5.0 and dist >= 0.2:
                issues.append(
                    ValidationIssue(
                        id=f"facing_bath_kit_{b_room.id}_{k_room.id}",
                        constraint_type=ConstraintCategory.PRIVACY_ADJACENCY,
                        severity=SeverityLevel.WARNING,
                        affected_rooms=[bath["name"], kit["name"]],
                        affected_element_ids=[b_room.id, k_room.id],
                        measured_value=f"Direct frontal separation: {dist:.1f} {unit}",
                        expected_condition="Shielded sightline from kitchen worktop",
                        explanation=f"Bathroom '{bath['name']}' is positioned directly in front of open Kitchen '{kit['name']}', creating an uncomfortable direct sightline.",
                        suggested_correction="Reorient bathroom entrance into a private corridor or swap bathroom position behind the staircase buffer.",
                        bounding_box=BoundingBox(
                            x=b_room.x,
                            y=b_room.y,
                            width=b_room.width,
                            length=b_room.length
                        )
                    )
                )

            # Check bathroom door opening directly facing kitchen opening
            bath_doors = [o for o in layout.openings if o.room_id == b_room.id]
            for door in bath_doors:
                is_door_facing = False
                if door.wall_side == "north" and b_room.y >= (k_room.y + k_room.length - 0.5) and dist < 12.0:
                    is_door_facing = True
                elif door.wall_side == "south" and (b_room.y + b_room.length) <= (k_room.y + 0.5) and dist < 12.0:
                    is_door_facing = True
                elif door.wall_side == "east" and (b_room.x + b_room.width) <= (k_room.x + 0.5) and dist < 12.0:
                    is_door_facing = True
                elif door.wall_side == "west" and b_room.x >= (k_room.x + k_room.width - 0.5) and dist < 12.0:
                    is_door_facing = True

                if is_door_facing and dist < 12.0:
                    issues.append(
                        ValidationIssue(
                            id=f"door_exposed_bath_kit_{door.id}_{k_room.id}",
                            constraint_type=ConstraintCategory.PRIVACY_ADJACENCY,
                            severity=SeverityLevel.WARNING,
                            affected_rooms=[bath["name"], kit["name"]],
                            affected_element_ids=[door.id, b_room.id, k_room.id],
                            measured_value=f"Bathroom door on {door.wall_side} wall facing Kitchen ({dist:.1f} {unit})",
                            expected_condition="Bathroom door oriented away from kitchen food prep zones",
                            explanation=f"Bathroom doorway '{door.id}' in '{bath['name']}' is directly exposed to Kitchen '{kit['name']}' worktop without a privacy buffer.",
                            suggested_correction=f"Reorient '{bath['name']}' doorway into a private hallway or vestibule.",
                            bounding_box=BoundingBox(
                                x=b_room.x,
                                y=b_room.y,
                                width=b_room.width,
                                length=b_room.length
                            )
                        )
                    )

    return issues
