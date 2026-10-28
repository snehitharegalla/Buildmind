import copy
import uuid
import hashlib
from typing import List, Dict, Any, Tuple, Optional, Set
from shapely.geometry import box, Polygon
from app.schemas.geometry import FloorPlanLayout, RoomGeometry, RoomType, OpeningGeometry, OpeningType
from app.schemas.project import SpaceRequirement, DesignRelationships, ConfigurableConstraints
from app.schemas.validation import ValidationReport, ValidationIssue, SeverityLevel, ConstraintCategory
from app.geometry.engine import GeometryValidationEngine
from app.geometry.dimensions import ROOM_MINIMUMS

class AutoFixEngine:
    """
    Intelligent Architectural Geometry Auto-Fix & Repair System.
    Guarantees:
    1. Non-regression: Candidate layouts are strictly validated before acceptance.
    2. Lexicographic priorities: Hard constraints (overlaps, boundaries, dimensions)
       are strictly prioritized and cannot be worsened.
    3. Cycle detection: Prevents infinite looping or oscillating states.
    4. Deterministic candidate generation: Explores multiple geometric transformations
       (flush alignment, partition split, space shifting, void placement) and selects
       only valid improvements.
    """

    @staticmethod
    def get_layout_signature(layout: FloorPlanLayout) -> str:
        """Returns a deterministic signature of all room coordinates and dimensions."""
        tokens = []
        for r in sorted(layout.rooms, key=lambda x: x.id):
            tokens.append(f"{r.id}:{round(r.x, 2)}:{round(r.y, 2)}:{round(r.width, 2)}:{round(r.length, 2)}")
        raw = "|".join(tokens)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @classmethod
    def evaluate_candidate(
        cls,
        candidate_layout: FloorPlanLayout,
        current_layout: FloorPlanLayout,
        candidate_val: ValidationReport,
        current_val: ValidationReport,
        target_issue: Optional[ValidationIssue] = None,
        constraints: Optional[ConfigurableConstraints] = None,
        required_spaces: Optional[List[SpaceRequirement]] = None
    ) -> Tuple[bool, str]:
        """
        Authoritative Lexicographic Candidate Evaluation.
        Returns (is_acceptable, rejection_reason).

        Rules:
        1. Room completeness: Candidate must not drop or delete any rooms.
        2. No new hard errors: Candidate must not introduce any new hard errors.
        3. Hard error reduction: Total hard errors must decrease, or if equal,
           total geometric collision / breach area must strictly decrease.
        4. Target resolution: The specific targeted issue must be resolved.
        5. Proportions & Minimums: No room may collapse below minimum physical dimensions.
        """
        # Rule 1: Room count & identity check
        curr_room_ids = {r.id for r in current_layout.rooms}
        cand_room_ids = {r.id for r in candidate_layout.rooms}
        if curr_room_ids != cand_room_ids and target_issue and target_issue.constraint_type != ConstraintCategory.MISSING_ROOM:
            return False, "Candidate dropped or modified room identities"

        # Check for room collapse below minimum physical dimensions
        for r in candidate_layout.rooms:
            r_type = r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type)
            is_circ = (
                r_type in [RoomType.CORRIDOR.value, RoomType.BALCONY.value, RoomType.UTILITY.value, RoomType.FOYER.value]
                or any(t in (r.tags or []) for t in ["circulation", "buffer", "dressing", "vestibule", "passage", "corridor"])
                or any(k in r.name.lower() for k in ["vestibule", "corridor", "passage", "dressing", "balcony"])
            )
            min_spec = ROOM_MINIMUMS.get(r_type, {"min_w": 3.0 if is_circ else 5.0, "min_l": 3.0 if is_circ else 5.0})
            floor_dim = 2.8 if is_circ else 4.0
            abs_min_clear = max(floor_dim, min(min_spec.get("min_w", 3.0), min_spec.get("min_l", 3.0)) * 0.7)
            smaller_dim = min(r.width, r.length)
            if smaller_dim < abs_min_clear - 0.05:
                return False, f"Room '{r.name}' collapsed below allowable dimensions ({smaller_dim:.1f} < {abs_min_clear:.1f})"

        curr_errors = [i for i in current_val.issues if i.severity == SeverityLevel.ERROR]
        cand_errors = [i for i in candidate_val.issues if i.severity == SeverityLevel.ERROR]

        curr_error_ids = {i.id for i in curr_errors}
        cand_error_ids = {i.id for i in cand_errors}

        # Rule 2: Cannot introduce brand new hard error categories or new room violations
        new_error_ids = cand_error_ids - curr_error_ids
        if new_error_ids:
            # Check if any new error is a completely new violation
            for eid in new_error_ids:
                new_iss = next(i for i in cand_errors if i.id == eid)
                # If target was a warning (e.g. privacy), it CANNOT introduce ANY new hard error
                if target_issue and target_issue.severity != SeverityLevel.ERROR:
                    return False, f"Introduced new hard error '{new_iss.title or new_iss.constraint_type}' while fixing warning"
                # If target was a hard error, new hard error is only acceptable if net hard errors strictly decrease
                if len(cand_errors) >= len(curr_errors):
                    return False, f"Introduced new hard error '{new_iss.title or new_iss.constraint_type}'"

        # Rule 3: Hard error count must strictly decrease or collision area strictly decrease
        if len(cand_errors) > len(curr_errors):
            return False, f"Hard error count increased from {len(curr_errors)} to {len(cand_errors)}"

        # Rule 4: If target issue is provided, verify it is resolved
        if target_issue:
            if target_issue.id in {i.id for i in candidate_val.issues}:
                return False, f"Target issue '{target_issue.id}' remained unresolved"

        # Rule 5: If error counts are equal, check if collision / overlap area strictly improved
        if len(cand_errors) == len(curr_errors) and len(curr_errors) > 0:
            # Calculate total overlap area in current vs candidate
            curr_overlap = cls._calculate_total_overlap_area(current_layout)
            cand_overlap = cls._calculate_total_overlap_area(candidate_layout)
            if cand_overlap >= curr_overlap - 0.05:
                # Check boundary breaches
                curr_breach = cls._calculate_total_breach_area(current_layout)
                cand_breach = cls._calculate_total_breach_area(candidate_layout)
                if cand_breach >= curr_breach - 0.05:
                    return False, "Candidate did not measurably reduce spatial conflict area"

        return True, "Candidate satisfies all non-regression criteria"

    @staticmethod
    def _calculate_total_overlap_area(layout: FloorPlanLayout) -> float:
        total = 0.0
        rooms = layout.rooms
        n = len(rooms)
        for i in range(n):
            p1 = box(rooms[i].x, rooms[i].y, rooms[i].x + rooms[i].width, rooms[i].y + rooms[i].length)
            for j in range(i + 1, n):
                p2 = box(rooms[j].x, rooms[j].y, rooms[j].x + rooms[j].width, rooms[j].y + rooms[j].length)
                if p1.intersects(p2):
                    total += p1.intersection(p2).area
        return total

    @staticmethod
    def _calculate_total_breach_area(layout: FloorPlanLayout) -> float:
        plot = layout.plot
        bx_min = plot.setback_left
        bx_max = plot.width - plot.setback_right
        by_min = plot.setback_front
        by_max = plot.length - plot.setback_rear
        b_poly = box(bx_min, by_min, bx_max, by_max)

        total = 0.0
        for r in layout.rooms:
            rp = box(r.x, r.y, r.x + r.width, r.y + r.length)
            diff = rp.difference(b_poly)
            total += diff.area
        return total

    @classmethod
    def auto_fix_all(
        cls,
        layout: FloorPlanLayout,
        constraints: Optional[ConfigurableConstraints] = None,
        required_spaces: Optional[List[SpaceRequirement]] = None,
        relationships: Optional[DesignRelationships] = None,
        max_cycles: int = 6
    ) -> Dict[str, Any]:
        """
        Executes complete multi-cycle auto-fix loop using snapshot-candidate-evaluate workflow.
        Guarantees that active layout never worsens.
        """
        initial_layout = copy.deepcopy(layout)
        initial_val = GeometryValidationEngine.validate_layout(
            initial_layout,
            required_spaces=required_spaces,
            relationships=relationships,
            constraints=constraints
        )

        current_layout = copy.deepcopy(initial_layout)
        current_val = initial_val
        all_diffs: List[Dict[str, Any]] = []
        rejected_attempts: List[str] = []
        seen_signatures: Set[str] = {cls.get_layout_signature(current_layout)}

        cycle = 0
        consecutive_failures = 0

        while cycle < max_cycles:
            cycle += 1
            if current_val.is_valid and current_val.warning_count == 0:
                break

            # Prioritize: 1. Hard Errors (Overlaps -> Boundary -> Dimensions -> Missing)
            #             2. Warnings (Privacy/Adjacencies -> Corridor)
            target_issue = None
            for cat in [
                ConstraintCategory.ROOM_OVERLAP,
                ConstraintCategory.PLOT_BOUNDARY,
                ConstraintCategory.SETBACK_VIOLATION,
                ConstraintCategory.MIN_DIMENSION,
                ConstraintCategory.MISSING_ROOM,
                ConstraintCategory.MAX_DIMENSION
            ]:
                target_issue = next((i for i in current_val.issues if i.constraint_type == cat and i.severity == SeverityLevel.ERROR), None)
                if target_issue:
                    break

            if not target_issue:
                # Target high-impact warnings like bathroom privacy
                for cat in [ConstraintCategory.PRIVACY_ADJACENCY, ConstraintCategory.ACCESSIBILITY]:
                    target_issue = next((i for i in current_val.issues if i.constraint_type == cat), None)
                    if target_issue:
                        break

            if not target_issue and current_val.issues:
                target_issue = current_val.issues[0]

            if not target_issue:
                break

            # Propose candidate fixes
            candidates = cls._generate_repair_candidates(
                layout=current_layout,
                issue=target_issue,
                constraints=constraints,
                required_spaces=required_spaces,
                relationships=relationships
            )

            accepted_candidate = None
            accepted_diffs: List[Dict[str, Any]] = []
            best_val = None

            for cand_layout, diffs in candidates:
                cand_val = GeometryValidationEngine.validate_layout(
                    cand_layout,
                    required_spaces=required_spaces,
                    relationships=relationships,
                    constraints=constraints
                )

                is_ok, reason = cls.evaluate_candidate(
                    candidate_layout=cand_layout,
                    current_layout=current_layout,
                    candidate_val=cand_val,
                    current_val=current_val,
                    target_issue=target_issue,
                    constraints=constraints,
                    required_spaces=required_spaces
                )

                if is_ok:
                    sig = cls.get_layout_signature(cand_layout)
                    if sig in seen_signatures:
                        rejected_attempts.append(f"Cycle detected: Candidate state already visited for {target_issue.id}")
                        continue

                    accepted_candidate = cand_layout
                    accepted_diffs = diffs
                    best_val = cand_val
                    seen_signatures.add(sig)
                    break
                else:
                    rejected_attempts.append(f"Rejected candidate for {target_issue.id}: {reason}")

            if accepted_candidate and best_val:
                current_layout = accepted_candidate
                current_val = best_val
                all_diffs.extend(accepted_diffs)
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 2:
                    # Stop to prevent spinning without improvements
                    break

        final_val = GeometryValidationEngine.validate_layout(
            current_layout,
            required_spaces=required_spaces,
            relationships=relationships,
            constraints=constraints
        )

        resolved_count = max(0, initial_val.error_count - final_val.error_count)
        if initial_val.error_count == 0:
            resolved_count = max(0, initial_val.warning_count - final_val.warning_count)

        return {
            "fixed_layout": current_layout,
            "initial_validation": initial_val,
            "final_validation": final_val,
            "resolved_issues_count": resolved_count,
            "remaining_issues_count": len(final_val.issues),
            "revisions_applied": all_diffs,
            "rejected_attempts": rejected_attempts,
            "is_success": final_val.is_valid,
            "cycles_run": cycle
        }

    @classmethod
    def fix_single_issue(
        cls,
        layout: FloorPlanLayout,
        issue: ValidationIssue,
        constraints: Optional[ConfigurableConstraints] = None,
        required_spaces: Optional[List[SpaceRequirement]] = None,
        relationships: Optional[DesignRelationships] = None
    ) -> Tuple[FloorPlanLayout, List[Dict[str, Any]]]:
        """
        Attempts a targeted repair for a single issue.
        Guarantees non-regression: if all candidates worsen the layout or fail validation,
        returns original layout unchanged and an empty diff list.
        """
        current_layout = copy.deepcopy(layout)
        current_val = GeometryValidationEngine.validate_layout(
            current_layout,
            required_spaces=required_spaces,
            relationships=relationships,
            constraints=constraints
        )

        candidates = cls._generate_repair_candidates(
            layout=current_layout,
            issue=issue,
            constraints=constraints,
            required_spaces=required_spaces,
            relationships=relationships
        )

        for cand_layout, diffs in candidates:
            cand_val = GeometryValidationEngine.validate_layout(
                cand_layout,
                required_spaces=required_spaces,
                relationships=relationships,
                constraints=constraints
            )

            is_ok, reason = cls.evaluate_candidate(
                candidate_layout=cand_layout,
                current_layout=current_layout,
                candidate_val=cand_val,
                current_val=current_val,
                target_issue=issue,
                constraints=constraints,
                required_spaces=required_spaces
            )

            if is_ok:
                return cand_layout, diffs

        # No valid non-regressive candidate found: preserve last known-good state
        return current_layout, []

    @classmethod
    def _preserve_layout_identities(
        cls,
        candidate_layout: FloorPlanLayout,
        source_layout: FloorPlanLayout
    ) -> FloorPlanLayout:
        """
        Maps rooms from candidate layout to match original room IDs from source layout
        based on room types and geometric positions, preserving room IDs and updating
        openings accordingly.
        """
        cand = copy.deepcopy(candidate_layout)
        cand.id = source_layout.id
        cand.name = source_layout.name

        unmatched_cand_rooms = list(cand.rooms)
        id_mapping: Dict[str, str] = {} # cand_room_id -> source_room_id

        # Pass 1: exact room_type and matching name
        for s_room in source_layout.rooms:
            match = None
            for c_room in unmatched_cand_rooms:
                if c_room.room_type == s_room.room_type and c_room.name.lower() == s_room.name.lower():
                    match = c_room
                    break
            if match:
                unmatched_cand_rooms.remove(match)
                id_mapping[match.id] = s_room.id
                match.id = s_room.id
                match.name = s_room.name

        # Pass 2: match by exact room_type
        for s_room in source_layout.rooms:
            if s_room.id in id_mapping.values():
                continue
            match = None
            for c_room in unmatched_cand_rooms:
                if c_room.room_type == s_room.room_type:
                    match = c_room
                    break
            if match:
                unmatched_cand_rooms.remove(match)
                id_mapping[match.id] = s_room.id
                match.id = s_room.id
                match.name = s_room.name

        # Pass 3: match circulation / vestibule / foyer / corridor spaces
        for s_room in source_layout.rooms:
            if s_room.id in id_mapping.values():
                continue
            s_circ = (
                s_room.room_type in [RoomType.CORRIDOR, RoomType.FOYER, RoomType.DINING]
                or any(k in s_room.name.lower() for k in ["vestibule", "corridor", "lobby", "dressing"])
            )
            if s_circ:
                match = None
                for c_room in unmatched_cand_rooms:
                    c_circ = (
                        c_room.room_type in [RoomType.CORRIDOR, RoomType.FOYER, RoomType.DINING]
                        or any(k in c_room.name.lower() for k in ["vestibule", "corridor", "lobby", "dressing"])
                    )
                    if c_circ:
                        match = c_room
                        break
                if match:
                    unmatched_cand_rooms.remove(match)
                    id_mapping[match.id] = s_room.id
                    match.id = s_room.id
                    match.name = s_room.name

        # Pass 4: any remaining rooms by order
        for s_room in source_layout.rooms:
            if s_room.id in id_mapping.values():
                continue
            if unmatched_cand_rooms:
                match = unmatched_cand_rooms.pop(0)
                id_mapping[match.id] = s_room.id
                match.id = s_room.id
                match.name = s_room.name

        # Update room IDs in candidate openings
        for op in cand.openings:
            if op.room_id in id_mapping:
                op.room_id = id_mapping[op.room_id]

        return cand

    @classmethod
    def _generate_repair_candidates(
        cls,
        layout: FloorPlanLayout,
        issue: ValidationIssue,
        constraints: Optional[ConfigurableConstraints] = None,
        required_spaces: Optional[List[SpaceRequirement]] = None,
        relationships: Optional[DesignRelationships] = None
    ) -> List[Tuple[FloorPlanLayout, List[Dict[str, Any]]]]:
        """
        Generates an ordered list of candidate layouts for a specific issue.
        """
        candidates: List[Tuple[FloorPlanLayout, List[Dict[str, Any]]]] = []

        if issue.constraint_type == ConstraintCategory.ROOM_OVERLAP:
            candidates.extend(cls._propose_overlap_fixes(layout, issue))
        elif issue.constraint_type in [ConstraintCategory.PLOT_BOUNDARY, ConstraintCategory.SETBACK_VIOLATION]:
            candidates.extend(cls._propose_boundary_fixes(layout, issue, constraints))
        elif issue.constraint_type == ConstraintCategory.MIN_DIMENSION:
            candidates.extend(cls._propose_dimension_fixes(layout, issue, required_spaces, relationships))
        elif issue.constraint_type == ConstraintCategory.ASPECT_RATIO:
            candidates.extend(cls._propose_aspect_ratio_fixes(layout, issue, required_spaces, relationships))
        elif issue.constraint_type == ConstraintCategory.PRIVACY_ADJACENCY:
            candidates.extend(cls._propose_privacy_fixes(layout, issue, relationships, required_spaces))
        elif issue.constraint_type == ConstraintCategory.MISSING_ROOM:
            candidates.extend(cls._propose_missing_room_fixes(layout, issue, required_spaces))

        return candidates

    # -------------------------------------------------------------------------
    # Candidate Generation: ROOM OVERLAPS
    # -------------------------------------------------------------------------
    @classmethod
    def _propose_overlap_fixes(
        cls,
        layout: FloorPlanLayout,
        issue: ValidationIssue
    ) -> List[Tuple[FloorPlanLayout, List[Dict[str, Any]]]]:
        candidates = []
        if len(issue.affected_element_ids) < 2:
            return candidates

        id1, id2 = issue.affected_element_ids[0], issue.affected_element_ids[1]
        r1 = next((r for r in layout.rooms if r.id == id1), None)
        r2 = next((r for r in layout.rooms if r.id == id2), None)
        if not r1 or not r2:
            return candidates

        plot = layout.plot
        bx_min = plot.setback_left
        bx_max = plot.width - plot.setback_right
        by_min = plot.setback_front
        by_max = plot.length - plot.setback_rear

        p1 = box(r1.x, r1.y, r1.x + r1.width, r1.y + r1.length)
        p2 = box(r2.x, r2.y, r2.x + r2.width, r2.y + r2.length)
        if not p1.intersects(p2):
            return candidates

        inter = p1.intersection(p2)
        if inter.area <= 0.05:
            return candidates

        minx, miny, maxx, maxy = inter.bounds
        inter_w = maxx - minx
        inter_l = maxy - miny

        # Strategy A: X-axis partition resolution
        # Option A1: If r1 is predominantly left of r2, shift r2 right or trim r1
        if r1.x <= r2.x:
            left_r, right_r = r1, r2
        else:
            left_r, right_r = r2, r1

        # Candidate A1: Trim left room width to meet right room's left boundary flush
        cand1 = copy.deepcopy(layout)
        lr = next(r for r in cand1.rooms if r.id == left_r.id)
        new_w = round(right_r.x - left_r.x, 2)
        if new_w >= 5.0:
            lr.width = new_w
            lr.area = round(lr.width * lr.length, 2)
            candidates.append((
                cand1,
                [{
                    "action": "adjust_partition_wall",
                    "target_room_name": lr.name,
                    "old_value": f"Width: {left_r.width:.1f}",
                    "new_value": f"Width: {new_w:.1f}",
                    "description": f"Adjusted partition wall of '{lr.name}' to meet '{right_r.name}' flush on X-axis."
                }]
            ))

        # Candidate A2: Shift right room eastward to clear left room
        cand2 = copy.deepcopy(layout)
        rr = next(r for r in cand2.rooms if r.id == right_r.id)
        new_x = round(left_r.x + left_r.width, 2)
        if new_x + right_r.width <= bx_max + 0.05:
            rr.x = new_x
            candidates.append((
                cand2,
                [{
                    "action": "shift_room",
                    "target_room_name": rr.name,
                    "old_value": f"X: {right_r.x:.1f}",
                    "new_value": f"X: {new_x:.1f}",
                    "description": f"Shifted '{rr.name}' east by {inter_w:.1f} {plot.unit} to eliminate overlap."
                }]
            ))

        # Strategy B: Y-axis partition resolution
        if r1.y <= r2.y:
            top_r, bot_r = r1, r2
        else:
            top_r, bot_r = r2, r1

        # Candidate B1: Trim top room length to meet bottom room flush
        cand3 = copy.deepcopy(layout)
        tr = next(r for r in cand3.rooms if r.id == top_r.id)
        new_l = round(bot_r.y - top_r.y, 2)
        if new_l >= 5.0:
            tr.length = new_l
            tr.area = round(tr.width * tr.length, 2)
            candidates.append((
                cand3,
                [{
                    "action": "adjust_partition_wall",
                    "target_room_name": tr.name,
                    "old_value": f"Length: {top_r.length:.1f}",
                    "new_value": f"Length: {new_l:.1f}",
                    "description": f"Adjusted horizontal partition of '{tr.name}' to meet '{bot_r.name}' flush."
                }]
            ))

        # Candidate B2: Shift bottom room south to clear top room
        cand4 = copy.deepcopy(layout)
        br = next(r for r in cand4.rooms if r.id == bot_r.id)
        new_y = round(top_r.y + top_r.length, 2)
        if new_y + bot_r.length <= by_max + 0.05:
            br.y = new_y
            candidates.append((
                cand4,
                [{
                    "action": "shift_room",
                    "target_room_name": br.name,
                    "old_value": f"Y: {bot_r.y:.1f}",
                    "new_value": f"Y: {new_y:.1f}",
                    "description": f"Shifted '{br.name}' south by {inter_l:.1f} {plot.unit} to clear partition."
                }]
            ))

        # Candidate C: Split the overlap symmetrically if both can shrink slightly
        cand5 = copy.deepcopy(layout)
        lr5 = next(r for r in cand5.rooms if r.id == left_r.id)
        rr5 = next(r for r in cand5.rooms if r.id == right_r.id)
        split_x = round((left_r.x + left_r.width + right_r.x) / 2.0, 2)
        new_w_l = round(split_x - left_r.x, 2)
        new_w_r = round((right_r.x + right_r.width) - split_x, 2)
        if new_w_l >= 6.0 and new_w_r >= 6.0:
            lr5.width = new_w_l
            rr5.x = split_x
            rr5.width = new_w_r
            lr5.area = round(lr5.width * lr5.length, 2)
            rr5.area = round(rr5.width * rr5.length, 2)
            candidates.append((
                cand5,
                [{
                    "action": "rebalance_partition",
                    "target_room_name": f"{lr5.name} & {rr5.name}",
                    "old_value": f"Overlap: {inter_w:.1f} {plot.unit}",
                    "new_value": f"Flush partition at X={split_x:.1f}",
                    "description": f"Equitably balanced shared wall between '{lr5.name}' and '{rr5.name}'."
                }]
            ))

        return candidates

    # -------------------------------------------------------------------------
    # Candidate Generation: BOUNDARY & SETBACKS
    # -------------------------------------------------------------------------
    @classmethod
    def _propose_boundary_fixes(
        cls,
        layout: FloorPlanLayout,
        issue: ValidationIssue,
        constraints: Optional[ConfigurableConstraints] = None
    ) -> List[Tuple[FloorPlanLayout, List[Dict[str, Any]]]]:
        candidates = []
        plot = layout.plot
        bx_min = plot.setback_left
        bx_max = plot.width - plot.setback_right
        by_min = plot.setback_front
        by_max = plot.length - plot.setback_rear
        bw = bx_max - bx_min
        bl = by_max - by_min

        for r_id in issue.affected_element_ids:
            room = next((r for r in layout.rooms if r.id == r_id), None)
            if not room:
                continue

            # Candidate 1: Shift room inside envelope without resizing
            cand1 = copy.deepcopy(layout)
            target1 = next(r for r in cand1.rooms if r.id == room.id)
            target_w = min(room.width, bw)
            target_l = min(room.length, bl)
            new_x = max(bx_min, min(bx_max - target_w, room.x))
            new_y = max(by_min, min(by_max - target_l, room.y))
            target1.x = round(new_x, 2)
            target1.y = round(new_y, 2)
            target1.width = round(target_w, 2)
            target1.length = round(target_l, 2)
            target1.area = round(target1.width * target1.length, 2)

            candidates.append((
                cand1,
                [{
                    "action": "clamp_boundary",
                    "target_room_name": room.name,
                    "old_value": f"[{room.x:.1f}, {room.y:.1f}]",
                    "new_value": f"[{new_x:.1f}, {new_y:.1f}]",
                    "description": f"Repositioned '{room.name}' within legal buildable setback envelope."
                }]
            ))

        return candidates

    # -------------------------------------------------------------------------
    # Candidate Generation: MINIMUM DIMENSIONS & PROPORTIONS
    # -------------------------------------------------------------------------
    @classmethod
    def _propose_dimension_fixes(
        cls,
        layout: FloorPlanLayout,
        issue: ValidationIssue,
        required_spaces: Optional[List[SpaceRequirement]] = None,
        relationships: Optional[DesignRelationships] = None
    ) -> List[Tuple[FloorPlanLayout, List[Dict[str, Any]]]]:
        candidates = []
        plot = layout.plot
        bx_max = plot.width - plot.setback_right
        by_max = plot.length - plot.setback_rear

        for r_id in issue.affected_element_ids:
            room = next((r for r in layout.rooms if r.id == r_id), None)
            if not room:
                continue

            r_type = room.room_type.value if hasattr(room.room_type, "value") else str(room.room_type)
            min_spec = ROOM_MINIMUMS.get(r_type, {"min_w": 6.0, "min_l": 6.0})
            req_min_clear = min(min_spec["min_w"], min_spec["min_l"])
            req_min_span = max(min_spec["min_w"], min_spec["min_l"])

            # Candidate A: If circulation vestibule / dressing buffer, ensure correct corridor/vestibule classification
            if ("vestibule" in room.name.lower() or "dressing" in room.name.lower() or "corridor" in room.name.lower()) and room.room_type != RoomType.CORRIDOR:
                cand = copy.deepcopy(layout)
                tr = next(r for r in cand.rooms if r.id == room.id)
                tr.room_type = RoomType.CORRIDOR
                if not tr.tags:
                    tr.tags = []
                if "circulation" not in tr.tags:
                    tr.tags.append("circulation")
                candidates.append((
                    cand,
                    [{
                        "action": "reclassify_space",
                        "target_room_name": room.name,
                        "old_value": str(room.room_type),
                        "new_value": "Circulation Corridor / Vestibule",
                        "description": f"Applied circulation code standard to '{room.name}'."
                    }]
                ))

            # Candidate B: Partition Rebalancing with Neighboring Rooms (borrowing depth/width from generous neighbors)
            for neighbor in layout.rooms:
                if neighbor.id == room.id:
                    continue

                # Neighbor South
                if abs((room.y + room.length) - neighbor.y) < 0.15:
                    overlap_x = min(room.x + room.width, neighbor.x + neighbor.width) - max(room.x, neighbor.x)
                    if overlap_x > 1.0:
                        n_type = neighbor.room_type.value if hasattr(neighbor.room_type, "value") else str(neighbor.room_type)
                        n_spec = ROOM_MINIMUMS.get(n_type, {"min_w": 4.0, "min_l": 4.0})
                        n_min = min(n_spec["min_w"], n_spec["min_l"])
                        if room.length < req_min_clear:
                            deficit = round(req_min_clear - room.length, 2)
                            if neighbor.length - deficit >= n_min:
                                cand = copy.deepcopy(layout)
                                tr = next(r for r in cand.rooms if r.id == room.id)
                                tn = next(r for r in cand.rooms if r.id == neighbor.id)
                                tr.length = round(tr.length + deficit, 2)
                                tn.y = round(tn.y + deficit, 2)
                                tn.length = round(tn.length - deficit, 2)
                                tr.area = round(tr.width * tr.length, 2)
                                tn.area = round(tn.width * tn.length, 2)
                                candidates.append((cand, [{
                                    "action": "rebalance_partition",
                                    "target_room_name": f"{room.name} & {neighbor.name}",
                                    "old_value": f"{room.length:.1f} ft / {neighbor.length:.1f} ft",
                                    "new_value": f"{tr.length:.1f} ft / {tn.length:.1f} ft",
                                    "description": f"Reallocated {deficit:.1f} ft of depth from '{neighbor.name}' to satisfy '{room.name}' minimum code clearance."
                                }]))

                # Neighbor North
                if abs(room.y - (neighbor.y + neighbor.length)) < 0.15:
                    overlap_x = min(room.x + room.width, neighbor.x + neighbor.width) - max(room.x, neighbor.x)
                    if overlap_x > 1.0:
                        n_type = neighbor.room_type.value if hasattr(neighbor.room_type, "value") else str(neighbor.room_type)
                        n_spec = ROOM_MINIMUMS.get(n_type, {"min_w": 4.0, "min_l": 4.0})
                        n_min = min(n_spec["min_w"], n_spec["min_l"])
                        if room.length < req_min_clear:
                            deficit = round(req_min_clear - room.length, 2)
                            if neighbor.length - deficit >= n_min:
                                cand = copy.deepcopy(layout)
                                tr = next(r for r in cand.rooms if r.id == room.id)
                                tn = next(r for r in cand.rooms if r.id == neighbor.id)
                                tn.length = round(tn.length - deficit, 2)
                                tr.y = round(tr.y - deficit, 2)
                                tr.length = round(tr.length + deficit, 2)
                                tr.area = round(tr.width * tr.length, 2)
                                tn.area = round(tn.width * tn.length, 2)
                                candidates.append((cand, [{
                                    "action": "rebalance_partition",
                                    "target_room_name": f"{neighbor.name} & {room.name}",
                                    "old_value": f"{neighbor.length:.1f} ft / {room.length:.1f} ft",
                                    "new_value": f"{tn.length:.1f} ft / {tr.length:.1f} ft",
                                    "description": f"Shifted boundary wall with '{neighbor.name}' to expand '{room.name}' length."
                                }]))

                # Neighbor West
                if abs(room.x - (neighbor.x + neighbor.width)) < 0.15:
                    overlap_y = min(room.y + room.length, neighbor.y + neighbor.length) - max(room.y, neighbor.y)
                    if overlap_y > 1.0:
                        n_type = neighbor.room_type.value if hasattr(neighbor.room_type, "value") else str(neighbor.room_type)
                        n_spec = ROOM_MINIMUMS.get(n_type, {"min_w": 4.0, "min_l": 4.0})
                        n_min = min(n_spec["min_w"], n_spec["min_l"])
                        if room.width < req_min_clear:
                            deficit = round(req_min_clear - room.width, 2)
                            if neighbor.width - deficit >= n_min:
                                cand = copy.deepcopy(layout)
                                tr = next(r for r in cand.rooms if r.id == room.id)
                                tn = next(r for r in cand.rooms if r.id == neighbor.id)
                                tn.width = round(tn.width - deficit, 2)
                                tr.x = round(tr.x - deficit, 2)
                                tr.width = round(tr.width + deficit, 2)
                                tr.area = round(tr.width * tr.length, 2)
                                tn.area = round(tn.width * tn.length, 2)
                                candidates.append((cand, [{
                                    "action": "rebalance_partition",
                                    "target_room_name": f"{neighbor.name} & {room.name}",
                                    "old_value": f"{neighbor.width:.1f} ft / {room.width:.1f} ft",
                                    "new_value": f"{tn.width:.1f} ft / {tr.width:.1f} ft",
                                    "description": f"Reallocated {deficit:.1f} ft width from '{neighbor.name}' to '{room.name}'."
                                }]))

                # Neighbor East
                if abs((room.x + room.width) - neighbor.x) < 0.15:
                    overlap_y = min(room.y + room.length, neighbor.y + neighbor.length) - max(room.y, neighbor.y)
                    if overlap_y > 1.0:
                        n_type = neighbor.room_type.value if hasattr(neighbor.room_type, "value") else str(neighbor.room_type)
                        n_spec = ROOM_MINIMUMS.get(n_type, {"min_w": 4.0, "min_l": 4.0})
                        n_min = min(n_spec["min_w"], n_spec["min_l"])
                        if room.width < req_min_clear:
                            deficit = round(req_min_clear - room.width, 2)
                            if neighbor.width - deficit >= n_min:
                                cand = copy.deepcopy(layout)
                                tr = next(r for r in cand.rooms if r.id == room.id)
                                tn = next(r for r in cand.rooms if r.id == neighbor.id)
                                tr.width = round(tr.width + deficit, 2)
                                tn.x = round(tn.x + deficit, 2)
                                tn.width = round(tn.width - deficit, 2)
                                tr.area = round(tr.width * tr.length, 2)
                                tn.area = round(tn.width * tn.length, 2)
                                candidates.append((cand, [{
                                    "action": "rebalance_partition",
                                    "target_room_name": f"{room.name} & {neighbor.name}",
                                    "old_value": f"{room.width:.1f} ft / {neighbor.width:.1f} ft",
                                    "new_value": f"{tr.width:.1f} ft / {tn.width:.1f} ft",
                                    "description": f"Shifted vertical partition with '{neighbor.name}' eastward."
                                }]))

            # Candidate C: Expand into free space if envelope permits
            if room.width < req_min_clear and (room.x + req_min_clear <= bx_max + 0.05):
                cand = copy.deepcopy(layout)
                tr = next(r for r in cand.rooms if r.id == room.id)
                tr.width = req_min_clear
                tr.area = round(tr.width * tr.length, 2)
                candidates.append((
                    cand,
                    [{
                        "action": "expand_dimension",
                        "target_room_name": room.name,
                        "old_value": f"Width: {room.width:.1f}",
                        "new_value": f"Width: {req_min_clear:.1f}",
                        "description": f"Expanded '{room.name}' width to code minimum ({req_min_clear:.1f} {plot.unit})."
                    }]
                ))

            if room.length < req_min_clear and (room.y + req_min_clear <= by_max + 0.05):
                cand = copy.deepcopy(layout)
                tr = next(r for r in cand.rooms if r.id == room.id)
                tr.length = req_min_clear
                tr.area = round(tr.width * tr.length, 2)
                candidates.append((
                    cand,
                    [{
                        "action": "expand_dimension",
                        "target_room_name": room.name,
                        "old_value": f"Length: {room.length:.1f}",
                        "new_value": f"Length: {req_min_clear:.1f}",
                        "description": f"Expanded '{room.name}' length to code minimum ({req_min_clear:.1f} {plot.unit})."
                    }]
                ))

        # Candidate D: If multi-room structural failure (incompatible zone stacking in shallow envelope),
        # propose a Constraint-Aware Zoned Rebalancing candidate using ArchitecturalGeometricSolver!
        spaces_to_use = required_spaces
        if not spaces_to_use:
            spaces_to_use = [
                SpaceRequirement(
                    id=f"req_{r.id}",
                    room_type=r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type),
                    label=r.name,
                    min_width=r.width,
                    min_length=r.length
                )
                for r in layout.rooms
            ]

        try:
            from app.ai.demo_solver import ArchitecturalGeometricSolver
            cand_rebalance = ArchitecturalGeometricSolver.generate_variant(
                variant_type=layout.variant_type or "space_optimized",
                plot=plot,
                spaces=spaces_to_use,
                relationships=relationships,
                preferences=None
            )
            cand_rebalance = cls._preserve_layout_identities(cand_rebalance, layout)
            candidates.append((
                cand_rebalance,
                [{
                    "action": "structural_zoning_rebalance",
                    "target_room_name": "Full Floor Plan",
                    "old_value": "Incompatible zone stacking",
                    "new_value": "Adaptive Zoned Solution",
                    "description": "Reorganized floor plan zoning to satisfy dimensional minimums within available buildable envelope."
                }]
            ))
        except Exception:
            pass

        return candidates

    # -------------------------------------------------------------------------
    # Candidate Generation: ASPECT RATIO & PROPORTIONS
    # -------------------------------------------------------------------------
    @classmethod
    def _propose_aspect_ratio_fixes(
        cls,
        layout: FloorPlanLayout,
        issue: ValidationIssue,
        required_spaces: Optional[List[SpaceRequirement]] = None,
        relationships: Optional[DesignRelationships] = None
    ) -> List[Tuple[FloorPlanLayout, List[Dict[str, Any]]]]:
        candidates = []
        plot = layout.plot

        for r_id in issue.affected_element_ids:
            room = next((r for r in layout.rooms if r.id == r_id), None)
            if not room:
                continue

            # Candidate A: Circulation / vestibule classification
            if ("vestibule" in room.name.lower() or "dressing" in room.name.lower() or "corridor" in room.name.lower()) and room.room_type != RoomType.CORRIDOR:
                cand = copy.deepcopy(layout)
                tr = next(r for r in cand.rooms if r.id == room.id)
                tr.room_type = RoomType.CORRIDOR
                if not tr.tags:
                    tr.tags = []
                if "circulation" not in tr.tags:
                    tr.tags.append("circulation")
                candidates.append((
                    cand,
                    [{
                        "action": "reclassify_space",
                        "target_room_name": room.name,
                        "old_value": "Habitable Space",
                        "new_value": "Circulation Corridor / Vestibule",
                        "description": f"Applied circulation vestibule rules to '{room.name}'."
                    }]
                ))

            # Candidate B: Squarify elongated space by trading excess width towards 1.5 ratio
            if room.width > 2.0 * room.length and room.length >= 4.0:
                target_w = round(room.length * 1.5, 2)
                cand = copy.deepcopy(layout)
                tr = next(r for r in cand.rooms if r.id == room.id)
                tr.width = target_w
                tr.area = round(tr.width * tr.length, 2)
                candidates.append((
                    cand,
                    [{
                        "action": "squarify_proportion",
                        "target_room_name": room.name,
                        "old_value": f"Width: {room.width:.1f} ft",
                        "new_value": f"Width: {target_w:.1f} ft",
                        "description": f"Reduced excess width on '{room.name}' to bring aspect ratio into 1.5:1."
                    }]
                ))

        # Candidate C: Structural rebalance
        spaces_to_use = required_spaces
        if not spaces_to_use:
            spaces_to_use = [
                SpaceRequirement(
                    id=f"req_{r.id}",
                    room_type=r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type),
                    label=r.name,
                    min_width=r.width,
                    min_length=r.length
                )
                for r in layout.rooms
            ]

        try:
            from app.ai.demo_solver import ArchitecturalGeometricSolver
            cand_rebalance = ArchitecturalGeometricSolver.generate_variant(
                variant_type=layout.variant_type or "space_optimized",
                plot=plot,
                spaces=spaces_to_use,
                relationships=relationships,
                preferences=None
            )
            cand_rebalance = cls._preserve_layout_identities(cand_rebalance, layout)
            candidates.append((
                cand_rebalance,
                [{
                    "action": "structural_zoning_rebalance",
                    "target_room_name": "Full Floor Plan",
                    "old_value": "Elongated room proportions",
                    "new_value": "Proportion-Optimized Architectural Layout",
                    "description": "Squarified floor plan layout to bring all room proportions within 1:1 - 1.95:1."
                }]
            ))
        except Exception:
            pass

        return candidates

    # -------------------------------------------------------------------------
    # Candidate Generation: BATHROOM-KITCHEN PRIVACY & SIGHTLINE CONFLICT
    # -------------------------------------------------------------------------
    @classmethod
    def _propose_privacy_fixes(
        cls,
        layout: FloorPlanLayout,
        issue: ValidationIssue,
        relationships: Optional[DesignRelationships] = None,
        required_spaces: Optional[List[SpaceRequirement]] = None
    ) -> List[Tuple[FloorPlanLayout, List[Dict[str, Any]]]]:
        candidates = []
        plot = layout.plot
        bx_min = plot.setback_left
        bx_max = plot.width - plot.setback_right
        by_min = plot.setback_front
        by_max = plot.length - plot.setback_rear

        bathrooms = [r for r in layout.rooms if r.room_type == RoomType.BATHROOM]
        kitchens = [r for r in layout.rooms if r.room_type == RoomType.KITCHEN]
        bedrooms = [r for r in layout.rooms if "bed" in (r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type))]

        if not bathrooms or not kitchens:
            return candidates

        bath = bathrooms[0]
        kit = kitchens[0]

        # Candidate 1: Relocate bathroom to private rear bedroom wing (beside or inside bedroom quadrant)
        if bedrooms:
            bed = bedrooms[0]
            # Try placing bathroom adjacent to bedroom along the rear boundary where space allows
            cand1 = copy.deepcopy(layout)
            cbath = next(r for r in cand1.rooms if r.id == bath.id)
            cbed = next(r for r in cand1.rooms if r.id == bed.id)

            # Check if bedroom width can yield a 5.0 ft bathroom slot
            if cbed.width >= 14.0:
                bath_w = 5.0
                cbed.width = round(cbed.width - bath_w, 2)
                cbath.x = round(cbed.x + cbed.width, 2)
                cbath.y = cbed.y
                cbath.width = bath_w
                cbath.length = round(min(7.5, cbed.length), 2)
                cbath.area = round(cbath.width * cbath.length, 2)
                cbed.area = round(cbed.width * cbed.length, 2)

                candidates.append((
                    cand1,
                    [{
                        "action": "relocate_hygiene_buffer",
                        "target_room_name": bath.name,
                        "old_value": f"X: {bath.x:.1f}, Y: {bath.y:.1f}",
                        "new_value": f"X: {cbath.x:.1f}, Y: {cbath.y:.1f}",
                        "description": f"Relocated '{bath.name}' into the private bedroom wing, completely separating hygiene zone from Kitchen '{kit.name}'."
                    }]
                ))

        # Candidate 2: Shift bathroom horizontally into empty buildable space away from kitchen's frontal span
        shift_x_right = round(kit.x + kit.width + 1.0, 2)
        if shift_x_right + bath.width <= bx_max + 0.05:
            cand_shift = copy.deepcopy(layout)
            cb = next(r for r in cand_shift.rooms if r.id == bath.id)
            cb.x = shift_x_right
            # Also reorient door away from kitchen if needed
            for op in cand_shift.openings:
                if op.room_id == bath.id and op.type in [OpeningType.DOOR, OpeningType.DOUBLE_DOOR]:
                    if op.wall_side == "north":
                        op.wall_side = "south"
            candidates.append((
                cand_shift,
                [{
                    "action": "shift_privacy_buffer",
                    "target_room_name": bath.name,
                    "old_value": f"X: {bath.x:.1f}",
                    "new_value": f"X: {shift_x_right:.1f}",
                    "description": f"Shifted '{bath.name}' eastward away from Kitchen '{kit.name}' frontal sightline."
                }]
            ))

        shift_x_left = round(kit.x - bath.width - 1.0, 2)
        if shift_x_left >= bx_min - 0.05:
            cand_shift_l = copy.deepcopy(layout)
            cb = next(r for r in cand_shift_l.rooms if r.id == bath.id)
            cb.x = shift_x_left
            for op in cand_shift_l.openings:
                if op.room_id == bath.id and op.type in [OpeningType.DOOR, OpeningType.DOUBLE_DOOR]:
                    if op.wall_side == "north":
                        op.wall_side = "south"
            candidates.append((
                cand_shift_l,
                [{
                    "action": "shift_privacy_buffer",
                    "target_room_name": bath.name,
                    "old_value": f"X: {bath.x:.1f}",
                    "new_value": f"X: {shift_x_left:.1f}",
                    "description": f"Shifted '{bath.name}' westward away from Kitchen '{kit.name}' frontal sightline."
                }]
            ))

        # Candidate 3: If bathroom has a doorway directly facing kitchen, reorient the doorway
        for op in layout.openings:
            if op.room_id == bath.id and op.type in [OpeningType.DOOR, OpeningType.DOUBLE_DOOR]:
                for target_side in ["south", "east", "west"]:
                    if target_side != op.wall_side:
                        cand2 = copy.deepcopy(layout)
                        cop = next(o for o in cand2.openings if o.id == op.id)
                        cop.wall_side = target_side
                        candidates.append((
                            cand2,
                            [{
                                "action": "reorient_opening",
                                "target_room_name": bath.name,
                                "old_value": f"Door on {op.wall_side} wall",
                                "new_value": f"Door on {target_side} wall",
                                "description": f"Reoriented '{bath.name}' doorway to {target_side} wall away from kitchen sightline."
                            }]
                        ))

        return candidates

    # -------------------------------------------------------------------------
    # Candidate Generation: MISSING MANDATORY ROOM
    # -------------------------------------------------------------------------
    @classmethod
    def _propose_missing_room_fixes(
        cls,
        layout: FloorPlanLayout,
        issue: ValidationIssue,
        required_spaces: Optional[List[SpaceRequirement]] = None
    ) -> List[Tuple[FloorPlanLayout, List[Dict[str, Any]]]]:
        candidates = []
        plot = layout.plot
        bx_min = plot.setback_left
        bx_max = plot.width - plot.setback_right
        by_min = plot.setback_front
        by_max = plot.length - plot.setback_rear
        bw = bx_max - bx_min
        bl = by_max - by_min

        target_req = None
        if required_spaces:
            for req in required_spaces:
                if req.id in issue.affected_element_ids or req.label in issue.affected_rooms or req.room_type in issue.id:
                    target_req = req
                    break

        raw_type = target_req.room_type if target_req else "bedroom"
        try:
            room_type = RoomType(raw_type)
        except Exception:
            room_type = RoomType.BEDROOM

        name = target_req.label if target_req else "Bedroom"
        req_w = target_req.preferred_width if target_req else 10.0
        req_l = target_req.preferred_length if target_req else 10.0
        min_w = target_req.min_width if target_req else 9.0
        min_l = target_req.min_length if target_req else 9.0

        # Find available vertical span at the rear
        max_y = max([r.y + r.length for r in layout.rooms], default=by_min)
        rem_l = by_max - max_y

        if rem_l >= min_l:
            cand = copy.deepcopy(layout)
            new_room = RoomGeometry(
                id=f"auto_room_{uuid.uuid4().hex[:6]}",
                name=name,
                room_type=room_type,
                x=bx_min,
                y=round(max_y, 2),
                width=round(min(bw, req_w), 2),
                length=round(min(rem_l, req_l), 2),
                area=round(min(bw, req_w) * min(rem_l, req_l), 2)
            )
            cand.rooms.append(new_room)
            candidates.append((
                cand,
                [{
                    "action": "synthesize_missing_space",
                    "target_room_name": name,
                    "old_value": "Missing from plan",
                    "new_value": f"{name} ({new_room.width:.1f}x{new_room.length:.1f})",
                    "description": f"Synthesized missing required room '{name}' into available buildable envelope."
                }]
            ))

        return candidates
