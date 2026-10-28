from typing import List, Dict, Any
from app.schemas.geometry import PlotGeometry
from app.schemas.project import (
    SpaceRequirement, DesignRelationships, ProjectPreferences, ConfigurableConstraints, AdjacencyPreference
)

# 1. Preset 1: Compact Urban Home (The Required 25 ft × 40 ft Demo Scenario)
PRESET_COMPACT_URBAN_25X40 = {
    "id": "compact_urban_demo",
    "name": "Compact Urban Residence (25×40 ft Demo)",
    "description": "25 ft × 40 ft (1,000 sq ft) urban residential site with 1 Living Hall, 1 Kitchen, 1 Bedroom, and 1 Internal Staircase.",
    "plot": PlotGeometry(
        width=25.0,
        length=40.0,
        total_area=1000.0,
        shape="rectangular",
        unit="ft",
        road_facing="north",
        entrance_facing="north",
        setback_front=3.0,
        setback_rear=2.0,
        setback_left=2.0,
        setback_right=2.0,
        buildable_width=21.0,
        buildable_length=35.0
    ),
    "spaces": [
        SpaceRequirement(
            id="req_living",
            room_type="living_room",
            label="Living Hall",
            quantity=1,
            preferred_width=14.0,
            preferred_length=14.0,
            min_width=11.0,
            min_length=11.0,
            is_mandatory=True,
            preferred_orientation="north"
        ),
        SpaceRequirement(
            id="req_stair",
            room_type="staircase",
            label="Internal Staircase",
            quantity=1,
            preferred_width=6.5,
            preferred_length=14.0,
            min_width=5.5,
            min_length=8.0,
            is_mandatory=True
        ),
        SpaceRequirement(
            id="req_kitchen",
            room_type="kitchen",
            label="Kitchen",
            quantity=1,
            preferred_width=11.0,
            preferred_length=9.0,
            min_width=7.0,
            min_length=8.0,
            is_mandatory=True,
            preferred_orientation="east"
        ),
        SpaceRequirement(
            id="req_bed1",
            room_type="bedroom",
            label="Master Bedroom",
            quantity=1,
            preferred_width=13.0,
            preferred_length=12.0,
            min_width=10.0,
            min_length=10.0,
            is_mandatory=True,
            preferred_orientation="south"
        ),
        SpaceRequirement(
            id="req_bath",
            room_type="bathroom",
            label="Common Bathroom",
            quantity=1,
            preferred_width=8.0,
            preferred_length=6.0,
            min_width=4.5,
            min_length=5.5,
            is_mandatory=True
        )
    ],
    "relationships": DesignRelationships(
        adjacencies=[
            AdjacencyPreference(room_a_type="kitchen", room_b_type="living_room", relationship="adjacent"),
            AdjacencyPreference(room_a_type="bathroom", room_b_type="bedroom", relationship="adjacent"),
            AdjacencyPreference(room_a_type="bathroom", room_b_type="kitchen", relationship="separated")
        ],
        privacy_levels={"living_room": "low", "bedroom": "high", "bathroom": "high"},
        entrance_room="living_room",
        accessibility_mode=False,
        natural_ventilation_priority=True
    ),
    "preferences": ProjectPreferences(
        budget_range="moderate",
        architectural_style="contemporary_warm",
        space_utilization_priority="balanced",
        wall_thickness_exterior=0.75,
        wall_thickness_interior=0.38,
        estimated_cost_per_sqft=185.0
    ),
    "constraints": ConfigurableConstraints(
        enforce_setbacks=True,
        min_corridor_width=3.0,
        min_door_clearance=2.8,
        max_aspect_ratio=2.4,
        min_aspect_ratio=0.45,
        min_habitable_area=80.0
    )
}

# 2. Preset 2: Suburban Family Residence (35 ft × 50 ft)
PRESET_FAMILY_RESIDENCE = {
    "id": "family_residence",
    "name": "Suburban Family Residence (35×50 ft)",
    "description": "35 ft × 50 ft (1,750 sq ft) multi-bedroom home with dedicated dining, 2 bedrooms, kitchen, utility, and porch.",
    "plot": PlotGeometry(
        width=35.0,
        length=50.0,
        total_area=1750.0,
        shape="rectangular",
        unit="ft",
        road_facing="north",
        entrance_facing="north",
        setback_front=4.0,
        setback_rear=3.0,
        setback_left=2.5,
        setback_right=2.5,
        buildable_width=30.0,
        buildable_length=43.0
    ),
    "spaces": [
        SpaceRequirement(id="fr_living", room_type="living_room", label="Formal Living", quantity=1, preferred_width=16.0, preferred_length=15.0, min_width=12.0, min_length=12.0),
        SpaceRequirement(id="fr_dining", room_type="dining", label="Family Dining", quantity=1, preferred_width=12.0, preferred_length=10.0, min_width=8.0, min_length=8.0),
        SpaceRequirement(id="fr_kit", room_type="kitchen", label="Island Kitchen", quantity=1, preferred_width=12.0, preferred_length=11.0, min_width=8.0, min_length=9.0),
        SpaceRequirement(id="fr_mbed", room_type="master_bedroom", label="Master Suite", quantity=1, preferred_width=15.0, preferred_length=14.0, min_width=11.0, min_length=12.0),
        SpaceRequirement(id="fr_bed2", room_type="bedroom", label="Children's Bedroom", quantity=1, preferred_width=13.0, preferred_length=12.0, min_width=10.0, min_length=10.0),
        SpaceRequirement(id="fr_bath1", room_type="bathroom", label="Master Bath", quantity=1, preferred_width=8.0, preferred_length=6.0, min_width=5.0, min_length=6.0),
        SpaceRequirement(id="fr_bath2", room_type="bathroom", label="Guest Powder Room", quantity=1, preferred_width=6.0, preferred_length=5.0, min_width=4.0, min_length=5.0),
        SpaceRequirement(id="fr_stair", room_type="staircase", label="Architectural Stairs", quantity=1, preferred_width=7.0, preferred_length=12.0, min_width=6.0, min_length=8.0)
    ],
    "relationships": DesignRelationships(
        adjacencies=[
            AdjacencyPreference(room_a_type="kitchen", room_b_type="dining", relationship="adjacent"),
            AdjacencyPreference(room_a_type="master_bedroom", room_b_type="bathroom", relationship="adjacent")
        ],
        entrance_room="living_room",
        accessibility_mode=False
    ),
    "preferences": ProjectPreferences(
        budget_range="luxury",
        architectural_style="contemporary_warm",
        space_utilization_priority="spacious_comfort",
        estimated_cost_per_sqft=220.0
    ),
    "constraints": ConfigurableConstraints(
        enforce_setbacks=True,
        min_corridor_width=3.5
    )
}

# 3. Preset 3: Courtyard-Inspired Home (30 ft × 45 ft)
PRESET_COURTYARD_HOME = {
    "id": "courtyard_home",
    "name": "Courtyard-Inspired Home (30×45 ft)",
    "description": "30 ft × 45 ft (1,350 sq ft) biophilic dwelling organized around a central open-to-sky light well.",
    "plot": PlotGeometry(
        width=30.0,
        length=45.0,
        total_area=1350.0,
        shape="rectangular",
        unit="ft",
        road_facing="east",
        entrance_facing="east",
        setback_front=3.5,
        setback_rear=2.5,
        setback_left=2.0,
        setback_right=2.0,
        buildable_width=26.0,
        buildable_length=39.0
    ),
    "spaces": [
        SpaceRequirement(id="cy_living", room_type="living_room", label="Courtyard Lounge", quantity=1, preferred_width=14.0, preferred_length=14.0, min_width=11.0, min_length=11.0),
        SpaceRequirement(id="cy_court", room_type="balcony", label="Central Light Well / Court", quantity=1, preferred_width=8.0, preferred_length=8.0, min_width=6.0, min_length=6.0),
        SpaceRequirement(id="cy_kit", room_type="kitchen", label="Garden Kitchen", quantity=1, preferred_width=10.0, preferred_length=10.0, min_width=7.0, min_length=8.0),
        SpaceRequirement(id="cy_bed1", room_type="bedroom", label="Verandah Bedroom", quantity=1, preferred_width=13.0, preferred_length=12.0, min_width=10.0, min_length=10.0),
        SpaceRequirement(id="cy_bath", room_type="bathroom", label="Stone Bath", quantity=1, preferred_width=7.0, preferred_length=6.0, min_width=4.5, min_length=5.5)
    ],
    "relationships": DesignRelationships(
        adjacencies=[
            AdjacencyPreference(room_a_type="living_room", room_b_type="balcony", relationship="adjacent")
        ],
        entrance_room="living_room"
    ),
    "preferences": ProjectPreferences(
        budget_range="moderate",
        architectural_style="courtyard_vernacular",
        space_utilization_priority="spacious_comfort",
        estimated_cost_per_sqft=195.0
    ),
    "constraints": ConfigurableConstraints(
        enforce_setbacks=True
    )
}

# 4. Preset 4: Narrow-Plot Home (18 ft × 50 ft)
PRESET_NARROW_PLOT = {
    "id": "narrow_plot",
    "name": "Narrow-Plot Urban Infill (18×50 ft)",
    "description": "18 ft × 50 ft (900 sq ft) slender townhouse plan with linear circulation and skylight-focused ventilation.",
    "plot": PlotGeometry(
        width=18.0,
        length=50.0,
        total_area=900.0,
        shape="rectangular",
        unit="ft",
        road_facing="north",
        entrance_facing="north",
        setback_front=3.0,
        setback_rear=2.0,
        setback_left=1.5,
        setback_right=1.5,
        buildable_width=15.0,
        buildable_length=45.0
    ),
    "spaces": [
        SpaceRequirement(id="np_living", room_type="living_room", label="Linear Living Room", quantity=1, preferred_width=15.0, preferred_length=14.0, min_width=10.0, min_length=11.0),
        SpaceRequirement(id="np_kit", room_type="kitchen", label="Galley Kitchen", quantity=1, preferred_width=15.0, preferred_length=8.0, min_width=7.0, min_length=7.0),
        SpaceRequirement(id="np_stair", room_type="staircase", label="Straight Flight Stair", quantity=1, preferred_width=4.5, preferred_length=12.0, min_width=3.5, min_length=9.0),
        SpaceRequirement(id="np_bed", room_type="bedroom", label="Rear Sanctuary Bedroom", quantity=1, preferred_width=15.0, preferred_length=13.0, min_width=10.0, min_length=10.0),
        SpaceRequirement(id="np_bath", room_type="bathroom", label="Compact Bath", quantity=1, preferred_width=7.0, preferred_length=5.0, min_width=4.0, min_length=5.0)
    ],
    "relationships": DesignRelationships(
        entrance_room="living_room"
    ),
    "preferences": ProjectPreferences(
        budget_range="compact",
        architectural_style="modern_minimal",
        space_utilization_priority="maximum_density",
        estimated_cost_per_sqft=175.0
    ),
    "constraints": ConfigurableConstraints(
        enforce_setbacks=True,
        max_aspect_ratio=2.8
    )
}

ALL_PRESETS = [
    PRESET_COMPACT_URBAN_25X40,
    PRESET_FAMILY_RESIDENCE,
    PRESET_COURTYARD_HOME,
    PRESET_NARROW_PLOT
]
