import datetime
from sqlalchemy_utils import LtreeType
from sqlalchemy_utils import Ltree
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, ForeignKey, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel, EmailStr, Field

Base = declarative_base()

# -------------------------
# SQLAlchemy МОДЕЛИ
# -------------------------

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    role = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('пользователь', 'админ')", name='check_role'),
    )
    hashed_password = Column(String, nullable=False)


class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), nullable=False)
    keywords = Column(JSONB)
    subject_area_id = Column(Integer, ForeignKey('subject_areas.id'))
    citation_count = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('в работе', 'приостановлен', 'завершен')", name='check_status'),
    )

# class Report(Base):
#     __tablename__ = 'reports'
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     file_id = Column(Integer, ForeignKey('project_files.id'), nullable=False)
#     table_data = Column(JSONB, nullable=False)
#     view_options = Column(JSONB)
#     created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

class SubjectArea(Base):
    __tablename__ = 'subject_areas'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    parent_id = Column(Integer, ForeignKey('subject_areas.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    path = Column(LtreeType)

class ProjectConnection(Base):
    __tablename__ = 'project_connections'
    project_id = Column(Integer, ForeignKey('projects.id'), primary_key=True)
    related_project_id = Column(Integer, ForeignKey('projects.id'), primary_key=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint('project_id <> related_project_id', name='check_project_connection_diff'),
    )

class TeamMember(Base):
    __tablename__ = 'team_members'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(100), nullable=False)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("role IN ('участник', 'куратор', 'ответственный')", name='check_team_role'),
    )

class ProjectFile(Base):
    __tablename__ = 'project_files'
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(255), nullable=False)
    url = Column(Text, nullable=False)
    file_metadata = Column(JSONB, default=dict, nullable=False)
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)

