import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_list_presets():
    response = client.get("/api/projects/presets")
    assert response.status_code == 200
    presets = response.json()
    assert len(presets) >= 4
    preset_ids = [p["id"] for p in presets]
    assert "compact_urban_demo" in preset_ids
    assert "family_residence" in preset_ids

def test_list_and_get_demo_project():
    # Verify the automatically seeded demo project
    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) >= 1
    
    demo = next((p for p in projects if p["id"] == "demo_project_25x40" or "25×40" in p["name"]), projects[0])
    demo_id = demo["id"]
    detail_res = client.get(f"/api/projects/{demo_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["plot"]["width"] == 25.0
    assert detail["plot"]["length"] == 40.0
    assert detail["selected_layout"] is not None
    assert len(detail["selected_layout"]["rooms"]) >= 4

def test_validation_endpoint():
    # Run validation on a mock layout payload
    mock_payload = {
        "layout": {
            "id": "val_test",
            "name": "Audit Test",
            "plot": {
                "width": 25.0, "length": 40.0, "total_area": 1000.0,
                "unit": "ft", "shape": "rectangular", "road_facing": "north",
                "entrance_facing": "north", "setback_front": 3.0, "setback_rear": 2.0,
                "setback_left": 2.0, "setback_right": 2.0,
                "buildable_width": 21.0, "buildable_length": 35.0
            },
            "rooms": [
                {"id": "r1", "name": "Living", "room_type": "living_room", "x": 2.0, "y": 3.0, "width": 12.0, "length": 14.0}
            ],
            "openings": [],
            "walls": []
        }
    }
    response = client.post("/api/validation/validate", json=mock_payload)
    assert response.status_code == 200
    val_report = response.json()
    assert "is_valid" in val_report
    assert "metrics" in val_report

def test_svg_export_endpoint():
    mock_payload = {
        "layout": {
            "id": "svg_test",
            "name": "SVG Export Test",
            "plot": {
                "width": 25.0, "length": 40.0, "total_area": 1000.0,
                "unit": "ft", "shape": "rectangular", "road_facing": "north",
                "entrance_facing": "north", "setback_front": 3.0, "setback_rear": 2.0,
                "setback_left": 2.0, "setback_right": 2.0,
                "buildable_width": 21.0, "buildable_length": 35.0
            },
            "rooms": [
                {"id": "r1", "name": "Living", "room_type": "living_room", "x": 2.0, "y": 3.0, "width": 12.0, "length": 14.0}
            ],
            "openings": [],
            "walls": []
        }
    }
    response = client.post("/api/export/svg", json=mock_payload)
    assert response.status_code == 200
    assert "<svg" in response.text
    assert "SVG EXPORT TEST" in response.text or "svg_test" in response.text
