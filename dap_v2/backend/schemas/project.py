"""
DAP v2.0 - Project Schemas
Pydantic schemas for project management API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# Enums
class ProjectStatus(str, Enum):
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    REVIEW = "REVIEW"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TeamRole(str, Enum):
    PARTNER = "PARTNER"
    MANAGER = "MANAGER"
    SENIOR = "SENIOR"
    STAFF = "STAFF"


# Project Type Schemas
class ProjectTypeBase(BaseModel):
    type_code: str = Field(..., max_length=20)
    type_name: str = Field(..., max_length=50)
    description: Optional[str] = None


class ProjectTypeCreate(ProjectTypeBase):
    pass


class ProjectTypeResponse(ProjectTypeBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# Project Schemas
class ProjectBase(BaseModel):
    project_code: str = Field(..., max_length=50)
    project_name: str = Field(..., max_length=200)
    project_type_id: str
    client_id: str
    fiscal_year: int
    fiscal_period: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    expected_completion_date: Optional[date] = None
    status: ProjectStatus = ProjectStatus.PLANNING
    risk_level: RiskLevel = RiskLevel.MEDIUM
    audit_scope: Optional[str] = None
    is_group_audit: bool = False
    consolidation_required: bool = False
    materiality_amount: Optional[Decimal] = None
    performance_materiality: Optional[Decimal] = None
    tc_required: bool = False
    partner_id: Optional[str] = None
    manager_id: Optional[str] = None
    senior_id: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    project_name: Optional[str] = None
    status: Optional[ProjectStatus] = None
    risk_level: Optional[RiskLevel] = None
    end_date: Optional[date] = None
    expected_completion_date: Optional[date] = None
    audit_scope: Optional[str] = None
    materiality_amount: Optional[Decimal] = None
    performance_materiality: Optional[Decimal] = None
    tc_status: Optional[str] = None
    tc_comments: Optional[str] = None
    audit_opinion: Optional[str] = None
    opinion_issued_date: Optional[date] = None
    partner_id: Optional[str] = None
    manager_id: Optional[str] = None
    senior_id: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: str
    actual_completion_date: Optional[date] = None
    tc_status: Optional[str] = None
    tc_approved_at: Optional[datetime] = None
    tc_comments: Optional[str] = None
    audit_opinion: Optional[str] = None
    opinion_issued_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    id: str
    project_code: str
    project_name: str
    fiscal_year: int
    status: str
    risk_level: str
    start_date: date
    client_name: Optional[str] = None
    project_type_name: Optional[str] = None

    class Config:
        from_attributes = True


# Audit Team Schemas
class TeamMemberBase(BaseModel):
    user_id: str
    role_in_team: TeamRole
    estimated_hours: Optional[Decimal] = None


class TeamMemberCreate(TeamMemberBase):
    pass


class TeamMemberResponse(TeamMemberBase):
    id: str
    team_id: str
    assignment_date: date
    actual_hours: Optional[Decimal] = None
    is_active: bool
    user_name: Optional[str] = None

    class Config:
        from_attributes = True


class AuditTeamBase(BaseModel):
    team_name: str = Field(..., max_length=100)
    team_code: Optional[str] = None
    description: Optional[str] = None
    is_main_team: bool = True
    entity_id: Optional[str] = None


class AuditTeamCreate(AuditTeamBase):
    members: Optional[List[TeamMemberCreate]] = None


class AuditTeamResponse(AuditTeamBase):
    id: str
    project_id: str
    created_at: datetime
    members: List[TeamMemberResponse] = []

    class Config:
        from_attributes = True


# Project Milestone Schemas
class MilestoneBase(BaseModel):
    milestone_name: str = Field(..., max_length=100)
    milestone_type: Optional[str] = None
    planned_date: Optional[date] = None
    status: str = "PENDING"
    responsible_user_id: Optional[str] = None
    deliverables: Optional[str] = None
    notes: Optional[str] = None


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    milestone_name: Optional[str] = None
    planned_date: Optional[date] = None
    actual_date: Optional[date] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class MilestoneResponse(MilestoneBase):
    id: str
    project_id: str
    actual_date: Optional[date] = None
    created_at: datetime

    class Config:
        from_attributes = True


# Statistics
class ProjectStatistics(BaseModel):
    total_projects: int
    planning: int
    in_progress: int
    review: int
    completed: int
    by_risk_level: dict
    by_project_type: dict
