"""
DAP v2.0 - Project Management API Routes
RESTful API for audit project management (中普模式)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date

import sys
sys.path.append('..')

from models import get_db, Project, ProjectType, AuditTeam, TeamMember, ProjectMilestone, Client
from schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse,
    ProjectTypeCreate, ProjectTypeResponse,
    AuditTeamCreate, AuditTeamResponse,
    MilestoneCreate, MilestoneUpdate, MilestoneResponse,
    ProjectStatistics
)

router = APIRouter(prefix="/api/v2/projects", tags=["Projects"])


# ==================== Project Types ====================

@router.get("/types", response_model=List[ProjectTypeResponse])
def get_project_types(db: Session = Depends(get_db)):
    """获取所有项目类型"""
    return db.query(ProjectType).all()


@router.post("/types", response_model=ProjectTypeResponse, status_code=201)
def create_project_type(data: ProjectTypeCreate, db: Session = Depends(get_db)):
    """创建项目类型"""
    existing = db.query(ProjectType).filter(ProjectType.type_code == data.type_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project type code already exists")

    project_type = ProjectType(**data.model_dump())
    db.add(project_type)
    db.commit()
    db.refresh(project_type)
    return project_type


# ==================== Projects CRUD ====================

@router.get("", response_model=List[ProjectListResponse])
def list_projects(
    status: Optional[str] = None,
    fiscal_year: Optional[int] = None,
    client_id: Optional[str] = None,
    project_type_id: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    获取项目列表
    支持筛选: 状态、年度、客户、项目类型
    支持搜索: 项目编号、项目名称
    """
    query = db.query(
        Project.id,
        Project.project_code,
        Project.project_name,
        Project.fiscal_year,
        Project.status,
        Project.risk_level,
        Project.start_date,
        Client.client_name,
        ProjectType.type_name.label("project_type_name")
    ).outerjoin(Client, Project.client_id == Client.id
    ).outerjoin(ProjectType, Project.project_type_id == ProjectType.id)

    # 筛选
    if status:
        query = query.filter(Project.status == status)
    if fiscal_year:
        query = query.filter(Project.fiscal_year == fiscal_year)
    if client_id:
        query = query.filter(Project.client_id == client_id)
    if project_type_id:
        query = query.filter(Project.project_type_id == project_type_id)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Project.project_code.ilike(search_pattern)) |
            (Project.project_name.ilike(search_pattern))
        )

    # 排序和分页
    query = query.order_by(Project.created_at.desc())
    projects = query.offset(skip).limit(limit).all()

    return [ProjectListResponse(
        id=p.id,
        project_code=p.project_code,
        project_name=p.project_name,
        fiscal_year=p.fiscal_year,
        status=p.status,
        risk_level=p.risk_level,
        start_date=p.start_date,
        client_name=p.client_name,
        project_type_name=p.project_type_name
    ) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    """创建新项目"""
    # 检查项目编号唯一性
    existing = db.query(Project).filter(Project.project_code == data.project_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Project code already exists")

    # 检查项目类型是否存在
    project_type = db.query(ProjectType).filter(ProjectType.id == data.project_type_id).first()
    if not project_type:
        raise HTTPException(status_code=404, detail="Project type not found")

    # 检查客户是否存在
    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    project = Project(**data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    """获取项目详情"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, data: ProjectUpdate, db: Session = Depends(get_db)):
    """更新项目信息"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """删除项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()


# ==================== Project Statistics ====================

@router.get("/stats/summary", response_model=ProjectStatistics)
def get_project_statistics(
    fiscal_year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """获取项目统计信息"""
    query = db.query(Project)
    if fiscal_year:
        query = query.filter(Project.fiscal_year == fiscal_year)

    projects = query.all()
    total = len(projects)

    # 按状态统计
    status_counts = {
        "PLANNING": 0, "IN_PROGRESS": 0, "REVIEW": 0, "COMPLETED": 0
    }
    risk_counts = {}
    type_counts = {}

    for p in projects:
        if p.status in status_counts:
            status_counts[p.status] += 1
        risk_counts[p.risk_level] = risk_counts.get(p.risk_level, 0) + 1

    # 按项目类型统计
    type_stats = db.query(
        ProjectType.type_name,
        func.count(Project.id)
    ).outerjoin(Project, Project.project_type_id == ProjectType.id
    ).group_by(ProjectType.type_name).all()

    type_counts = {t[0]: t[1] for t in type_stats if t[0]}

    return ProjectStatistics(
        total_projects=total,
        planning=status_counts["PLANNING"],
        in_progress=status_counts["IN_PROGRESS"],
        review=status_counts["REVIEW"],
        completed=status_counts["COMPLETED"],
        by_risk_level=risk_counts,
        by_project_type=type_counts
    )


# ==================== Audit Teams ====================

@router.get("/{project_id}/teams", response_model=List[AuditTeamResponse])
def get_project_teams(project_id: str, db: Session = Depends(get_db)):
    """获取项目审计组列表"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project.teams


@router.post("/{project_id}/teams", response_model=AuditTeamResponse, status_code=201)
def create_audit_team(project_id: str, data: AuditTeamCreate, db: Session = Depends(get_db)):
    """创建审计组"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    team_data = data.model_dump(exclude={"members"})
    team = AuditTeam(project_id=project_id, **team_data)
    db.add(team)
    db.flush()

    # 添加成员
    if data.members:
        for member_data in data.members:
            member = TeamMember(team_id=team.id, **member_data.model_dump())
            db.add(member)

    db.commit()
    db.refresh(team)
    return team


# ==================== Milestones ====================

@router.get("/{project_id}/milestones", response_model=List[MilestoneResponse])
def get_project_milestones(project_id: str, db: Session = Depends(get_db)):
    """获取项目里程碑列表"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project.milestones


@router.post("/{project_id}/milestones", response_model=MilestoneResponse, status_code=201)
def create_milestone(project_id: str, data: MilestoneCreate, db: Session = Depends(get_db)):
    """创建项目里程碑"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    milestone = ProjectMilestone(project_id=project_id, **data.model_dump())
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return milestone


@router.put("/{project_id}/milestones/{milestone_id}", response_model=MilestoneResponse)
def update_milestone(
    project_id: str,
    milestone_id: str,
    data: MilestoneUpdate,
    db: Session = Depends(get_db)
):
    """更新里程碑"""
    milestone = db.query(ProjectMilestone).filter(
        ProjectMilestone.id == milestone_id,
        ProjectMilestone.project_id == project_id
    ).first()

    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(milestone, field, value)

    db.commit()
    db.refresh(milestone)
    return milestone
