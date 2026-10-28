import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from app.schemas.geometry import FloorPlanLayout
from app.schemas.validation import ValidationReport

def export_layout_to_pdf(layout: FloorPlanLayout, validation: ValidationReport) -> bytes:
    """
    Renders a print-ready architectural presentation sheet and room schedule table in PDF format.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    # Custom Architectural Styles
    title_style = ParagraphStyle(
        "ArchTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1E1E1E")
    )
    subtitle_style = ParagraphStyle(
        "ArchSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#7A7265")
    )
    section_style = ParagraphStyle(
        "ArchSection",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#C85A32")
    )
    body_style = ParagraphStyle(
        "ArchBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#2C2A29")
    )
    disclaimer_style = ParagraphStyle(
        "ArchDisclaimer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#9E9E9E")
    )

    story = []

    # Title & Metadata
    story.append(Paragraph(f"BUILDMIND ARCHITECTURAL STUDIO — {layout.name.upper()}", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Site Dimensions: {layout.plot.width:.1f} × {layout.plot.length:.1f} {layout.plot.unit} ({layout.plot.total_area:.0f} sq {layout.plot.unit})  |  "
        f"Variant: {layout.variant_type.replace('_', ' ').title()}  |  "
        f"Validation: {'PASSED (Zero Hard Conflicts)' if validation.is_valid else f'REVISIONS PENDING ({validation.error_count} conflicts)'}",
        subtitle_style
    ))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#C85A32"), spaceAfter=15))

    # Architectural Space Schedule Table
    story.append(Paragraph("ARCHITECTURAL ROOM SCHEDULE & SPECIFICATION", section_style))
    story.append(Spacer(1, 6))

    table_data = [
        ["Room Name", "Spatial Function", f"Dimensions ({layout.plot.unit})", f"Area (sq {layout.plot.unit})", "Material / Finish"]
    ]

    for r in layout.rooms:
        r_type = r.room_type.value if hasattr(r.room_type, "value") else str(r.room_type)
        table_data.append([
            r.name,
            r_type.replace("_", " ").title(),
            f"{r.width:.1f} × {r.length:.1f}",
            f"{r.area:.1f}",
            (r.material_finish or "terrazzo").title()
        ])

    # Summary Row
    table_data.append([
        "TOTAL USABLE CARPET",
        "",
        "",
        f"{layout.carpet_area:.1f}",
        ""
    ])

    sched_table = Table(table_data, colWidths=[180, 140, 130, 110, 150])
    sched_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F4EFE6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1E1E1E")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DFD9CD")),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FAF8F5")),
    ]))
    story.append(sched_table)
    story.append(Spacer(1, 15))

    # Metric & Cost Breakdown
    story.append(Paragraph("SPATIAL EFFICIENCY & PROJECTED BUDGET", section_style))
    story.append(Spacer(1, 6))

    cost_str = f"${layout.estimated_cost_min:,.0f} – ${layout.estimated_cost_max:,.0f}" if layout.estimated_cost_min > 0 else "N/A"
    metrics_data = [
        ["Plot Area", f"{layout.plot.total_area:.0f} sq {layout.plot.unit}", "Carpet Area", f"{layout.carpet_area:.1f} sq {layout.plot.unit}"],
        ["Built-Up Envelope", f"{layout.total_built_up_area:.1f} sq {layout.plot.unit}", "Circulation Ratio", f"{(1.0 - layout.efficiency_ratio) * 100:.1f}%"],
        ["Ground Coverage", f"{validation.metrics.ground_coverage_ratio * 100:.1f}%", "Estimated Cost Range*", cost_str]
    ]

    metrics_table = Table(metrics_data, colWidths=[160, 195, 160, 195])
    metrics_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DFD9CD")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#FAF8F5")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#FAF8F5")),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 15))

    # Compliance & Validation Findings
    story.append(Paragraph("COMPUTATIONAL GEOMETRY VALIDATION AUDIT", section_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"<b>Status:</b> {validation.summary}<br/>"
        f"<b>Hard Constraint Violations:</b> {validation.error_count}  |  <b>Soft Preference Warnings:</b> {validation.warning_count}",
        body_style
    ))
    story.append(Spacer(1, 15))

    # Regulatory Disclaimer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#DFD9CD"), spaceAfter=6))
    story.append(Paragraph(
        "*DISCLAIMER: All architectural layouts generated by BuildMind are preliminary conceptual designs generated "
        "for space-planning and constraint-exploration purposes. They do not constitute certified construction blueprints, "
        "structural engineering drawings, or sanctioned municipal approvals until verified by a licensed architect "
        "against local building regulations.",
        disclaimer_style
    ))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
