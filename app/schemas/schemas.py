# -------------------------
# Pydantic СХЕМЫ
# -------------------------
import datetime
from sqlalchemy_utils import Ltree
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Boolean, ForeignKey, CheckConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from pydantic import BaseModel, EmailStr, Field, field_validator

Base = declarative_base()
# --- User ---
class UserBase(BaseModel):
    name: str
    email: EmailStr
    role: str = Field(..., pattern="^(пользователь|админ)$")

class UserCreate(UserBase):
    password: str

class UserRead(UserBase):
    id: int
    created_at: datetime.datetime

    model_config = {
        "from_attributes": True
    }

# --- Project ---
class ProjectBase(BaseModel):
    title: str
    description: Optional[str]
    status: str = Field(..., pattern="^(в работе|приостановлен|завершен)$")
    keywords: List[str]
    subject_area_id: Optional[int]
    is_public: Optional[bool] = False

class ProjectCreate(ProjectBase):
    pass

class ProjectRead(ProjectBase):
    id: int
    citation_count: Optional[int]
    created_at: datetime.datetime

    model_config = {
        "from_attributes": True
    }

# --- Report ---
# class ReportBase(BaseModel):
#     file_id: int
#     table_data: Dict[str, Any]
#     view_options: Optional[Dict[str, Any]]
#
# class ReportCreate(ReportBase):
#     pass
#
# class ReportRead(ReportBase):
#     id: int
#     created_at: datetime.datetime
#
#     model_config = {
#         "from_attributes": True
#     }

# --- SubjectArea ---
class SubjectAreaBase(BaseModel):
    name: str
    description: Optional[str]
    user_id: int
    parent_id: Optional[int]

class SubjectAreaCreate(SubjectAreaBase):
    pass

class SubjectAreaRead(SubjectAreaBase):
    id: int
    created_at: datetime.datetime
    path: Optional[str]  # воспринимаем ltree как строку

    model_config = {
        "arbitrary_types_allowed": True,
        "from_attributes": True,
    }

    # Можно добавить валидатор для приведения Ltree к строке, если нужно
    @field_validator("path", mode="before")
    def ltree_to_str(cls, v):
        return str(v) if v is not None else v

# --- ProjectConnection ---
class ProjectConnectionBase(BaseModel):
    project_id: int
    related_project_id: int

class ProjectConnectionCreate(ProjectConnectionBase):
    pass

class ProjectConnectionRead(ProjectConnectionBase):
    created_at: datetime.datetime

    model_config = {
        "from_attributes": True
    }

# --- TeamMember ---
class TeamMemberBase(BaseModel):
    project_id: int
    user_id: int
    role: str = Field(..., pattern="^(участник|куратор|ответственный)$")

class TeamMemberCreate(TeamMemberBase):
    pass

class TeamMemberRead(TeamMemberBase):
    id: int
    joined_at: datetime.datetime

    model_config = {
        "from_attributes": True
    }

# --- ProjectFile ---
class ProjectFileBase(BaseModel):
    project_id: int
    name: str
    url: str
    file_metadata: Optional[Dict[str, Any]] = {}
    uploaded_by: int
    is_public: Optional[bool] = False

class ProjectFileCreate(ProjectFileBase):
    pass

class ProjectFileRead(ProjectFileBase):
    id: int
    uploaded_at: datetime.datetime

    model_config = {
        "from_attributes": True
    }
