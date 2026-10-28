import datetime
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False, default="Untitled Architectural Project")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Specifications stored as JSON for flexibility and migration safety
    plot_spec = Column(JSON, nullable=False)
    space_requirements = Column(JSON, nullable=False)
    design_relationships = Column(JSON, nullable=False, default=dict)
    preferences = Column(JSON, nullable=False, default=dict)
    constraints = Column(JSON, nullable=False, default=dict)
    
    selected_layout_id = Column(String(36), nullable=True)
    active_version = Column(Integer, default=1)

    # Relationships
    layouts = relationship("LayoutRecord", back_populates="project", cascade="all, delete-orphan", order_by="LayoutRecord.created_at.desc()")
    revisions = relationship("RevisionRecord", back_populates="project", cascade="all, delete-orphan", order_by="RevisionRecord.iteration.asc()")

class LayoutRecord(Base):
    __tablename__ = "layouts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    version = Column(Integer, default=1)
    variant_type = Column(String(50), default="space_optimized") # space_optimized, comfort_focused, budget_conscious, custom
    name = Column(String(255), nullable=False, default="Layout Proposal")
    data = Column(JSON, nullable=False) # Full FloorPlanLayout structure
    is_favorite = Column(Boolean, default=False)
    parent_layout_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="layouts")
    revisions = relationship("RevisionRecord", back_populates="layout", cascade="all, delete-orphan")

class RevisionRecord(Base):
    __tablename__ = "revisions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id"), nullable=False)
    layout_id = Column(String(36), ForeignKey("layouts.id"), nullable=False)
    iteration = Column(Integer, default=1)
    trigger_reason = Column(String(100), default="validation_auto_repair")
    prompt_request = Column(Text, nullable=True)
    changes_made = Column(JSON, default=list)
    issues_before = Column(JSON, default=dict)
    issues_after = Column(JSON, default=dict)
    resolved_all_errors = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    project = relationship("Project", back_populates="revisions")
    layout = relationship("LayoutRecord", back_populates="revisions")
