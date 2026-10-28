from typing import List, Dict, Any, Optional
from shapely.geometry import box
from app.schemas.geometry import FloorPlanLayout, RoomType
from app.schemas.project import DesignRelationships, SpaceRequirement

class LayoutQualityEvaluator:
    """
    Evaluates architectural layout quality, adjacency satisfaction, privacy buffering,
    circulation efficiency, and daylight access.
    Distinguishes hard constraint validity from soft design quality scores.
    """

    @classmethod
    def evaluate_layout(
        cls,
        layout: FloorPlanLayout,
        relationships: Optional[DesignRelationships] = None,
        required_spaces: Optional[List[SpaceRequirement]] = None
    ) -> Dict[str, Any]:
        plot = layout.plot
        rooms = layout.rooms
        bx_start = plot.setback_left
        bx_end = plot.width - plot.setback_right
        by_start = plot.setback_front
        by_end = plot.length - plot.setback_rear
        bw = max(10.0, bx_end - bx_start)
        bl = max(10.0, by_end - by_start)

        room_polys = {
            r.id: {
                "name": r.name,
                "type": r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type),
                "poly": box(r.x, r.y, r.x + r.width, r.y + r.length),
                "room": r
            }
            for r in rooms
        }

        # 1. Hard Constraints Check (Overlaps & Boundary)
        hard_valid = True
        overlap_count = 0
        boundary_breaches = 0

        room_list = list(room_polys.values())
        n = len(room_list)
        for i in range(n):
            r1 = room_list[i]["room"]
            poly1 = room_list[i]["poly"]

            # Boundary check
            if r1.x < bx_start - 0.1 or (r1.x + r1.width) > bx_end + 0.1 or \
               r1.y < by_start - 0.1 or (r1.y + r1.length) > by_end + 0.1:
                boundary_breaches += 1
                hard_valid = False

            for j in range(i + 1, n):
                poly2 = room_list[j]["poly"]
                if poly1.intersects(poly2):
                    inter = poly1.intersection(poly2)
                    if inter.area > 0.05:
                        overlap_count += 1
                        hard_valid = False

        # 2. Adjacency & Privacy Score (0 - 100)
        privacy_points = 100
        privacy_notes: List[str] = []

        kitchens = [info for info in room_list if info["type"] == RoomType.KITCHEN.value]
        bathrooms = [info for info in room_list if info["type"] == RoomType.BATHROOM.value]
        bedrooms = [info for info in room_list if "bed" in info["type"]]
        living_rooms = [info for info in room_list if "living" in info["type"]]

        # Check Bathroom - Kitchen Proximity & Orientation
        for bath in bathrooms:
            for kit in kitchens:
                dist = bath["poly"].distance(kit["poly"])
                # Case A: Direct abutting partition wall
                if dist < 0.2:
                    privacy_points -= 25
                    privacy_notes.append(f"Bathroom '{bath['name']}' directly abuts Kitchen '{kit['name']}' without sound/odour buffer.")
                # Case B: Facing kitchen or in direct front sightline (< 4 ft separation)
                elif dist < 4.0:
                    privacy_points -= 15
                    privacy_notes.append(f"Bathroom '{bath['name']}' is in close proximity ({dist:.1f} ft) to Kitchen worktop.")

                # Case C: Check bathroom door facing kitchen opening
                b_room = bath["room"]
                k_room = kit["room"]
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
                        privacy_points -= 20
                        privacy_notes.append(f"Bathroom doorway in '{b_room.name}' directly opens towards Kitchen '{k_room.name}'.")

        # Check Bedroom Privacy (should be buffered from front entry)
        for bed in bedrooms:
            r = bed["room"]
            if r.y < by_start + bl * 0.25:
                # Bedroom too close to front road entrance
                privacy_points -= 15
                privacy_notes.append(f"'{bed['name']}' is placed in the front entry zone rather than private rear.")

        # Check Living Room Entry Accessibility
        for liv in living_rooms:
            r = liv["room"]
            if r.y <= by_start + 4.0:
                # Living room at front entrance
                pass
            else:
                privacy_points -= 10
                privacy_notes.append(f"'{liv['name']}' is pushed back from front entrance.")

        privacy_score = max(0, min(100, privacy_points))

        # 3. Daylight & Ventilation Access Score (0 - 100)
        # Habitable rooms must touch at least one exterior wall
        habitable = kitchens + bedrooms + living_rooms
        exterior_compliant = 0
        for info in habitable:
            r = info["room"]
            touches_exterior = (
                abs(r.x - bx_start) < 0.2 or
                abs((r.x + r.width) - bx_end) < 0.2 or
                abs(r.y - by_start) < 0.2 or
                abs((r.y + r.length) - by_end) < 0.2
            )
            if touches_exterior:
                exterior_compliant += 1
            else:
                privacy_notes.append(f"Habitable room '{info['name']}' lacks direct exterior wall for natural daylight.")

        daylight_score = round((exterior_compliant / len(habitable) * 100) if habitable else 100, 1)

        # 4. Proportions & Aspect Ratio Score (0 - 100)
        aspect_points = 100
        for info in room_list:
            r = info["room"]
            ratio = max(r.width, r.length) / max(0.1, min(r.width, r.length))
            if ratio > 2.2:
                aspect_points -= 15
                privacy_notes.append(f"Room '{r.name}' has narrow tunnel proportions (ratio {ratio:.1f}:1).")
        proportions_score = max(20, min(100, aspect_points))

        # 5. Circulation & Space Efficiency Score (0 - 100)
        total_built_up = sum(r.area for r in rooms)
        carpet_area = sum(r.area for r in rooms if r.room_type not in [RoomType.STAIRCASING, RoomType.CORRIDOR, RoomType.FOYER])
        carpet_ratio = (carpet_area / total_built_up) if total_built_up > 0 else 0.85
        # Ideal residential carpet efficiency is 84% - 92%
        if carpet_ratio >= 0.85 and carpet_ratio <= 0.94:
            efficiency_score = 95.0
        elif carpet_ratio < 0.75:
            efficiency_score = 65.0
            privacy_notes.append("Excessive circulation and hallway space reducing usable room area.")
        else:
            efficiency_score = 85.0

        # 6. Overall Quality Score
        if not hard_valid:
            overall_score = round(min(35.0, (privacy_score + daylight_score + proportions_score) / 9.0), 1)
        else:
            overall_score = round(
                privacy_score * 0.35 +
                daylight_score * 0.25 +
                efficiency_score * 0.20 +
                proportions_score * 0.20,
                1
            )

        return {
            "hard_constraints_passed": hard_valid,
            "overall_quality_score": overall_score,
            "privacy_score": privacy_score,
            "daylight_score": daylight_score,
            "efficiency_score": efficiency_score,
            "proportions_score": proportions_score,
            "overlap_count": overlap_count,
            "boundary_breaches": boundary_breaches,
            "notes": privacy_notes
        }
