from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field

class RoomType(str, Enum):
    LIVING_ROOM = "living_room"
    BEDROOM = "bedroom"
    MASTER_BEDROOM = "master_bedroom"
    KITCHEN = "kitchen"
    BATHROOM = "bathroom"
    DINING = "dining"
    STAIRCASING = "staircase"
    BALCONY = "balcony"
    CORRIDOR = "corridor"
    FOYER = "foyer"
    PARKING = "parking"
    UTILITY = "utility"
    STUDY = "study"

class OpeningType(str, Enum):
    DOOR = "door"
    WINDOW = "window"
    DOUBLE_DOOR = "double_door"
    SLIDING_DOOR = "sliding_door"
    ARCHWAY = "archway"

class Point2D(BaseModel):
    x: float
    y: float

class OpeningGeometry(BaseModel):
    id: str
    type: OpeningType = OpeningType.DOOR
    room_id: str
    wall_side: str = Field(description="north, south, east, west")
    offset: float = Field(default=2.0, description="Distance from the start of the wall in units")
    width: float = Field(default=3.0, description="Opening width in units (e.g. 3.0 ft)")
    height: Optional[float] = Field(default=7.0, description="Opening height in units")
    swing_direction: Optional[str] = Field(default="inside_right", description="inside_left, inside_right, outside_left, outside_right")

class WallGeometry(BaseModel):
    id: str
    start: Point2D
    end: Point2D
    thickness: float = Field(default=0.75, description="Wall thickness in units (e.g. 0.75 ft / 9 in)")
    is_exterior: bool = False
    connected_room_ids: List[str] = Field(default_factory=list)

class RoomGeometry(BaseModel):
    id: str
    name: str
    room_type: RoomType = RoomType.LIVING_ROOM
    x: float = Field(description="Top-left X coordinate")
    y: float = Field(description="Top-left Y coordinate")
    width: float = Field(description="Room width (along X axis)")
    length: float = Field(description="Room length/depth (along Y axis)")
    area: float = Field(default=0.0, description="Calculated geometric area")
    polygon: Optional[List[Point2D]] = Field(default=None, description="Detailed coordinates if non-rectangular")
    level: int = 1
    material_finish: Optional[str] = Field(default="terrazzo", description="wood, limestone, concrete, clay, terrazzo")
    color: Optional[str] = None
    target_area: Optional[float] = None
    tags: List[str] = Field(default_factory=list)

class PlotGeometry(BaseModel):
    width: float = Field(default=25.0, description="Plot width in units (e.g. 25 ft)")
    length: float = Field(default=40.0, description="Plot length/depth in units (e.g. 40 ft)")
    total_area: float = Field(default=1000.0, description="Calculated plot area")
    shape: str = Field(default="rectangular", description="rectangular, trapezoidal, corner")
    unit: str = Field(default="ft", description="ft or m")
    road_facing: str = Field(default="north", description="north, south, east, west")
    entrance_facing: str = Field(default="north", description="north, south, east, west")
    setback_front: float = Field(default=3.0, description="Front setback")
    setback_rear: float = Field(default=2.0, description="Rear setback")
    setback_left: float = Field(default=2.0, description="Left/West setback")
    setback_right: float = Field(default=2.0, description="Right/East setback")
    buildable_width: float = Field(default=21.0)
    buildable_length: float = Field(default=35.0)

class FloorPlanLayout(BaseModel):
    id: str
    name: str = "Architectural Concept Layout"
    variant_type: str = Field(default="space_optimized", description="space_optimized, comfort_focused, budget_conscious, custom")
    version: int = 1
    plot: PlotGeometry
    rooms: List[RoomGeometry] = Field(default_factory=list)
    openings: List[OpeningGeometry] = Field(default_factory=list)
    walls: List[WallGeometry] = Field(default_factory=list)
    total_built_up_area: float = 0.0
    carpet_area: float = 0.0
    circulation_area: float = 0.0
    efficiency_ratio: float = 0.0
    estimated_cost_min: float = 0.0
    estimated_cost_max: float = 0.0
    summary_notes: str = ""
    advantages: List[str] = Field(default_factory=list)
    tradeoffs: List[str] = Field(default_factory=list)
