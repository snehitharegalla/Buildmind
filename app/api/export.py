from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.schemas.geometry import FloorPlanLayout
from app.schemas.validation import ValidationReport
from app.geometry.engine import GeometryValidationEngine
from app.export.svg_exporter import export_layout_to_svg
from app.export.pdf_exporter import export_layout_to_pdf

class ExportPayload(BaseModel):
    layout: FloorPlanLayout
    validation: Optional[ValidationReport] = None
    presentation_mode: bool = False

router = APIRouter(prefix="/export", tags=["Export"])

@router.post("/svg")
def export_svg(payload: ExportPayload):
    """Download layout as an architectural SVG blueprint."""
    svg_content = export_layout_to_svg(payload.layout, presentation_mode=payload.presentation_mode)
    return Response(
        content=svg_content,
        media_type="image/svg+xml",
        headers={"Content-Disposition": f'attachment; filename="buildmind_{payload.layout.id[:8]}.svg"'}
    )

@router.post("/pdf")
def export_pdf(payload: ExportPayload):
    """Download layout and room schedule as a print-ready presentation PDF."""
    val = payload.validation or GeometryValidationEngine.validate_layout(payload.layout)
    try:
        pdf_bytes = export_layout_to_pdf(payload.layout, val)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="buildmind_{payload.layout.id[:8]}.pdf"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@router.post("/json")
def export_json(payload: ExportPayload):
    """Export complete layout specification and validation audit report as JSON."""
    val = payload.validation or GeometryValidationEngine.validate_layout(payload.layout)
    return {
        "export_standard": "BuildMind Architecture Schema v1.0",
        "layout": payload.layout.dict(),
        "validation_report": val.dict()
    }
