import html
from typing import Optional
from app.schemas.geometry import FloorPlanLayout, RoomType, OpeningType

def export_layout_to_svg(layout: FloorPlanLayout, presentation_mode: bool = False) -> str:
    """
    Renders an architectural-grade 2D vector floor plan SVG drawing.
    Features CAD dimension ticks, room labels, door arcs, window lines, and title block.
    """
    plot = layout.plot
    scale = 20.0 # 20 pixels per foot/meter
    margin = 80.0

    svg_w = plot.width * scale + margin * 2
    svg_h = plot.length * scale + margin * 2 + 100 # Extra for title block

    # Color tokens matching BuildMind visual identity
    paper_bg = "#FBF9F5" if presentation_mode else "#FAF8F5"
    grid_stroke = "#EFECE6"
    wall_stroke = "#2C2A29"
    setback_stroke = "#D4AF37"
    dim_stroke = "#7A7265"
    text_main = "#1E1E1E"
    text_muted = "#6B655B"
    terracotta = "#C85A32"
    sage_green = "#6B8E23"

    # Material fills
    mat_fills = {
        "wood": "#F5EBE1",
        "limestone": "#F4EFE6",
        "concrete": "#ECEEEF",
        "clay": "#FCEEE9",
        "terrazzo": "#F5F3ED"
    }

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}">')
    svg.append(f'  <defs>')
    # Drafting pattern hatch
    svg.append('    <pattern id="draftGrid" width="20" height="20" patternUnits="userSpaceOnUse">')
    svg.append(f'      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="{grid_stroke}" stroke-width="0.75" />')
    svg.append('    </pattern>')
    # Marker for dimension lines
    svg.append('    <marker id="dimTick" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto">')
    svg.append(f'      <line x1="1" y1="9" x2="9" y2="1" stroke="{dim_stroke}" stroke-width="1.5" />')
    svg.append('    </marker>')
    svg.append('  </defs>')

    # Background
    svg.append(f'  <rect width="{svg_w}" height="{svg_h}" fill="{paper_bg}" />')
    svg.append(f'  <rect x="{margin}" y="{margin}" width="{plot.width * scale}" height="{plot.length * scale}" fill="url(#draftGrid)" />')

    # Plot Boundary Outer Line
    svg.append(f'  <!-- Plot Boundary -->')
    svg.append(f'  <rect x="{margin}" y="{margin}" width="{plot.width * scale}" height="{plot.length * scale}" fill="none" stroke="{wall_stroke}" stroke-width="1.5" stroke-dasharray="8,4" />')
    
    # Setback Envelope
    sb_x = margin + plot.setback_left * scale
    sb_y = margin + plot.setback_front * scale
    sb_w = (plot.width - plot.setback_left - plot.setback_right) * scale
    sb_l = (plot.length - plot.setback_front - plot.setback_rear) * scale
    svg.append(f'  <!-- Setback Envelope -->')
    svg.append(f'  <rect x="{sb_x}" y="{sb_y}" width="{sb_w}" height="{sb_l}" fill="none" stroke="{setback_stroke}" stroke-width="1.0" stroke-dasharray="4,4" opacity="0.6" />')

    # Draw Rooms
    svg.append('  <!-- Rooms -->')
    for room in layout.rooms:
        rx = margin + room.x * scale
        ry = margin + room.y * scale
        rw = room.width * scale
        rl = room.length * scale
        fill = mat_fills.get(room.material_finish or "terrazzo", "#F5F3ED")

        svg.append(f'  <g id="room_{room.id}">')
        svg.append(f'    <rect x="{rx}" y="{ry}" width="{rw}" height="{rl}" fill="{fill}" stroke="{wall_stroke}" stroke-width="2.5" />')

        # Staircase treads if room is staircase
        if "stair" in getattr(room.room_type, "value", str(room.room_type)).lower():
            tread_count = 10
            tread_step = rl / tread_count
            for t in range(1, tread_count):
                svg.append(f'    <line x1="{rx}" y1="{ry + t * tread_step}" x2="{rx + rw}" y2="{ry + t * tread_step}" stroke="{text_muted}" stroke-width="1" />')
            # Up arrow
            svg.append(f'    <line x1="{rx + rw/2}" y1="{ry + rl - 10}" x2="{rx + rw/2}" y2="{ry + 10}" stroke="{text_main}" stroke-width="1.5" />')
            svg.append(f'    <polyline points="{rx + rw/2 - 4},{ry + 16} {rx + rw/2},{ry + 10} {rx + rw/2 + 4},{ry + 16}" fill="none" stroke="{text_main}" stroke-width="1.5" />')

        # Room Text Labels
        cx = rx + rw / 2.0
        cy = ry + rl / 2.0
        svg.append(f'    <text x="{cx}" y="{cy - 8}" text-anchor="middle" font-family="Cinzel, serif, Georgia" font-size="12" font-weight="600" fill="{text_main}">{html.escape(room.name)}</text>')
        svg.append(f'    <text x="{cx}" y="{cy + 8}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="10" fill="{text_muted}">{room.width:.1f} × {room.length:.1f} {plot.unit}</text>')
        svg.append(f'    <text x="{cx}" y="{cy + 22}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="9" fill="{terracotta}">{room.area:.0f} sq {plot.unit}</text>')
        svg.append(f'  </g>')

    # Openings: Doors & Windows
    svg.append('  <!-- Openings -->')
    rooms_map = {r.id: r for r in layout.rooms}
    for op in layout.openings:
        room = rooms_map.get(op.room_id)
        if not room:
            continue
        rx = margin + room.x * scale
        ry = margin + room.y * scale
        op_w = op.width * scale
        op_off = op.offset * scale

        if op.type.value in ["door", "double_door", "sliding_door"]:
            if op.wall_side == "south":
                dx = rx + op_off
                dy = ry + room.length * scale
                svg.append(f'    <line x1="{dx}" y1="{dy}" x2="{dx + op_w}" y2="{dy}" stroke="{paper_bg}" stroke-width="4" />')
                # Door swing arc
                svg.append(f'    <path d="M {dx} {dy} A {op_w} {op_w} 0 0 0 {dx + op_w} {dy - op_w}" fill="none" stroke="{terracotta}" stroke-width="1.2" stroke-dasharray="2,2" />')
                svg.append(f'    <line x1="{dx}" y1="{dy}" x2="{dx}" y2="{dy - op_w}" stroke="{wall_stroke}" stroke-width="1.5" />')
            elif op.wall_side == "north":
                dx = rx + op_off
                dy = ry
                svg.append(f'    <line x1="{dx}" y1="{dy}" x2="{dx + op_w}" y2="{dy}" stroke="{paper_bg}" stroke-width="4" />')
                svg.append(f'    <path d="M {dx} {dy} A {op_w} {op_w} 0 0 1 {dx + op_w} {dy + op_w}" fill="none" stroke="{terracotta}" stroke-width="1.2" stroke-dasharray="2,2" />')
                svg.append(f'    <line x1="{dx}" y1="{dy}" x2="{dx}" y2="{dy + op_w}" stroke="{wall_stroke}" stroke-width="1.5" />')
        elif op.type.value == "window":
            if op.wall_side in ["north", "south"]:
                wx = rx + op_off
                wy = ry if op.wall_side == "north" else ry + room.length * scale
                svg.append(f'    <line x1="{wx}" y1="{wy}" x2="{wx + op_w}" y2="{wy}" stroke="{paper_bg}" stroke-width="4" />')
                svg.append(f'    <line x1="{wx}" y1="{wy - 2}" x2="{wx + op_w}" y2="{wy - 2}" stroke="#4A90E2" stroke-width="1.5" />')
                svg.append(f'    <line x1="{wx}" y1="{wy + 2}" x2="{wx + op_w}" y2="{wy + 2}" stroke="#4A90E2" stroke-width="1.5" />')
            elif op.wall_side in ["east", "west"]:
                wx = rx if op.wall_side == "west" else rx + room.width * scale
                wy = ry + op_off
                svg.append(f'    <line x1="{wx}" y1="{wy}" x2="{wx}" y2="{wy + op_w}" stroke="{paper_bg}" stroke-width="4" />')
                svg.append(f'    <line x1="{wx - 2}" y1="{wy}" x2="{wx - 2}" y2="{wy + op_w}" stroke="#4A90E2" stroke-width="1.5" />')
                svg.append(f'    <line x1="{wx + 2}" y1="{wy}" x2="{wx + 2}" y2="{wy + op_w}" stroke="#4A90E2" stroke-width="1.5" />')

    # Dimension Lines on outer edges
    svg.append('  <!-- Dimensions -->')
    # Top width dimension
    dim_top_y = margin - 25
    svg.append(f'  <line x1="{margin}" y1="{dim_top_y}" x2="{margin + plot.width * scale}" y2="{dim_top_y}" stroke="{dim_stroke}" stroke-width="1.2" marker-start="url(#dimTick)" marker-end="url(#dimTick)" />')
    svg.append(f'  <text x="{margin + (plot.width * scale)/2}" y="{dim_top_y - 8}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="11" font-weight="600" fill="{text_main}">{plot.width:.1f} {plot.unit}</text>')
    
    # Left height dimension
    dim_left_x = margin - 25
    svg.append(f'  <line x1="{dim_left_x}" y1="{margin}" x2="{dim_left_x}" y2="{margin + plot.length * scale}" y2="{margin + plot.length * scale}" stroke="{dim_stroke}" stroke-width="1.2" marker-start="url(#dimTick)" marker-end="url(#dimTick)" />')
    svg.append(f'  <text x="{dim_left_x - 10}" y="{margin + (plot.length * scale)/2}" text-anchor="middle" transform="rotate(-90 {dim_left_x - 10} {margin + (plot.length * scale)/2})" font-family="JetBrains Mono, monospace" font-size="11" font-weight="600" fill="{text_main}">{plot.length:.1f} {plot.unit}</text>')

    # North Arrow
    na_x = svg_w - 60
    na_y = 60
    svg.append(f'  <!-- North Arrow -->')
    svg.append(f'  <circle cx="{na_x}" cy="{na_y}" r="18" fill="none" stroke="{dim_stroke}" stroke-width="1" />')
    svg.append(f'  <polygon points="{na_x},{na_y - 14} {na_x - 5},{na_y + 6} {na_x},{na_y + 2} {na_x + 5},{na_y + 6}" fill="{terracotta}" />')
    svg.append(f'  <text x="{na_x}" y="{na_y - 18}" text-anchor="middle" font-family="JetBrains Mono, monospace" font-size="10" font-weight="bold" fill="{text_main}">N</text>')

    # Professional Architectural Title Block
    tb_y = svg_h - 85
    svg.append('  <!-- Title Block -->')
    svg.append(f'  <rect x="{margin}" y="{tb_y}" width="{plot.width * scale}" height="65" fill="#FFFFFF" stroke="{wall_stroke}" stroke-width="1.5" />')
    svg.append(f'  <text x="{margin + 15}" y="{tb_y + 22}" font-family="Cinzel, serif" font-size="14" font-weight="bold" fill="{text_main}">BUILDMIND — {layout.name.upper()}</text>')
    svg.append(f'  <text x="{margin + 15}" y="{tb_y + 42}" font-family="Inter, sans-serif" font-size="10" fill="{text_muted}">Built-Up Area: {layout.total_built_up_area:.1f} sq {plot.unit} | Carpet: {layout.carpet_area:.1f} sq {plot.unit} | Efficiency: {layout.efficiency_ratio * 100:.1f}%</text>')
    svg.append(f'  <text x="{margin + 15}" y="{tb_y + 56}" font-family="JetBrains Mono, monospace" font-size="9" fill="{text_muted}">Scale: 1:50 | Preliminary Conceptual Architectural Drawing | Generated with Constraint Validation</text>')

    svg.append('</svg>')
    return "\n".join(svg)
