from sqlalchemy_utils import Ltree
from sqlalchemy import text
from app.minio_client import delete_file


from app.models import (
    Project, SubjectArea, ProjectConnection,
    TeamMember, ProjectFile
)
# Report
# ReportCreate
from app.schemas import (
    ProjectCreate, SubjectAreaCreate,
    ProjectConnectionCreate, TeamMemberCreate, ProjectFileCreate
)

# --- User CRUD ---

from sqlalchemy.orm import Session
from typing import List, Optional
import bcrypt
from fastapi import HTTPException, status
from app.models import User
from app.schemas import UserCreate


# --- User CRUD ---

def get_user(db: Session, user_id: int) -> Optional[User]:
    try:
        return db.query(User).filter(User.id == user_id).first()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения пользователя: {str(e)}"
        ) from e


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    try:
        return db.query(User).filter(User.email == email).first()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка поиска пользователя по email: {str(e)}"
        ) from e


def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    try:
        return db.query(User).offset(skip).limit(limit).all()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения списка пользователей: {str(e)}"
        ) from e


def create_user(db: Session, user: UserCreate) -> User:
    try:
        # Проверяем существование пользователя
        existing_user = get_user_by_email(db, user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пользователь с таким email уже существует"
            )

        # Хешируем пароль
        hashed_password = bcrypt.hashpw(user.password.encode('utf-8'), bcrypt.gensalt())

        db_user = User(
            name=user.name,
            email=user.email,
            role=user.role,
            hashed_password=hashed_password.decode('utf-8')
        )

        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    except HTTPException:
        # Перебрасываем уже созданные HTTP исключения
        db.rollback()
        raise
    except Exception as e:
        # Откатываем транзакцию при любой другой ошибке
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания пользователя: {str(e)}"
        ) from e


def delete_user(db: Session, user_id: int) -> None:
    try:
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )

        db.delete(user)
        db.commit()

    except HTTPException:
        # Перебрасываем HTTP исключения (404, 400 и т.д.)
        db.rollback()
        raise
    except Exception as e:
        # Откатываем при любых других ошибках
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления пользователя: {str(e)}"
        ) from e


# Дополнительная функция для обновления пользователя
def update_user(db: Session, user_id: int, user_data: dict) -> User:
    try:
        user = get_user(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пользователь не найден"
            )

        # Если обновляется email, проверяем уникальность
        if 'email' in user_data and user_data['email'] != user.email:
            existing_user = get_user_by_email(db, user_data['email'])
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Пользователь с таким email уже существует"
                )

        # Если обновляется пароль, хешируем его
        if 'password' in user_data:
            hashed_password = bcrypt.hashpw(user_data['password'].encode('utf-8'), bcrypt.gensalt())
            user_data['hashed_password'] = hashed_password.decode('utf-8')
            del user_data['password']  # Удаляем plain text пароль

        # Обновляем поля
        for key, value in user_data.items():
            if hasattr(user, key):
                setattr(user, key, value)

        db.commit()
        db.refresh(user)
        return user

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления пользователя: {str(e)}"
        ) from e

# --- Project CRUD ---

def get_project(db: Session, project_id: int) -> Optional[Project]:
    try:
        return db.query(Project).filter(Project.id == project_id).first()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения проекта: {str(e)}"
        ) from e


def get_projects(db: Session, skip: int = 0, limit: int = 100) -> List[Project]:
    try:
        return db.query(Project).offset(skip).limit(limit).all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка проектов: {str(e)}"
        ) from e


def create_project(db: Session, project: ProjectCreate) -> Project:
    try:
        db_project = Project(
            title=project.title,
            description=project.description,
            status=project.status,
            keywords=project.keywords,
            subject_area_id=project.subject_area_id,
            is_public=project.is_public
        )

        db.add(db_project)
        db.commit()
        db.refresh(db_project)
        return db_project

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания проекта: {str(e)}"
        ) from e


def update_project(db: Session, project_id: int, project_data: dict) -> Project:
    try:
        project = get_project(db, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Проект не найден"
            )

        for key, value in project_data.items():
            if hasattr(project, key):
                setattr(project, key, value)

        db.commit()
        db.refresh(project)
        return project

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления проекта: {str(e)}"
        ) from e


def delete_project(db: Session, project_id: int) -> None:
    try:
        project = get_project(db, project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Проект не найден"
            )

        db.delete(project)
        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления проекта: {str(e)}"
        ) from e


# --- Report CRUD ---
#
# def get_report(db: Session, report_id: int) -> Optional[Report]:
#     return db.query(Report).filter(Report.id == report_id).first()
#
# def get_reports(db: Session, skip: int = 0, limit: int = 100) -> List[Report]:
#     return db.query(Report).offset(skip).limit(limit).all()
#
# def create_report(db: Session, report: ReportCreate) -> Report:
#     db_report = Report(
#         file_id=report.file_id,
#         table_data=report.table_data,
#         view_options=report.view_options
#     )
#     db.add(db_report)
#     db.commit()
#     db.refresh(db_report)
#     return db_report
#
# def delete_report(db: Session, report_id: int) -> None:
#     report = get_report(db, report_id)
#     if not report:
#         raise HTTPException(status_code=404, detail="Отчет не найден")
#     db.delete(report)
#     db.commit()

# --- SubjectArea CRUD ---

def get_subject_area(db: Session, subject_area_id: int) -> Optional[SubjectArea]:
    try:
        return db.query(SubjectArea).filter(SubjectArea.id == subject_area_id).first()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения предметной области: {str(e)}"
        ) from e


def get_subject_areas(db: Session, skip: int = 0, limit: int = 100) -> List[SubjectArea]:
    try:
        return db.query(SubjectArea).offset(skip).limit(limit).all()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения списка предметных областей: {str(e)}"
        ) from e


def create_subject_area(db: Session, subject_area: SubjectAreaCreate) -> SubjectArea:
    try:
        # Проверяем parent_id - если 0, устанавливаем None
        parent_id = subject_area.parent_id
        if parent_id == 0:
            parent_id = None

        # Проверяем что parent_id существует (если не None)
        if parent_id is not None:
            parent = db.query(SubjectArea).filter(SubjectArea.id == parent_id).first()
            if parent is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Родительская категория с ID {parent_id} не найдена"
                )

        db_subject_area = SubjectArea(
            name=subject_area.name,
            description=subject_area.description,
            user_id=subject_area.user_id,
            parent_id=parent_id  # используем исправленное значение
        )

        db.add(db_subject_area)
        db.commit()
        db.refresh(db_subject_area)

        # Обновляем путь после получения ID
        if db_subject_area.parent_id is None:
            db_subject_area.path = Ltree(str(db_subject_area.id))
        else:
            parent = db.query(SubjectArea).filter(SubjectArea.id == db_subject_area.parent_id).first()
            db_subject_area.path = parent.path + Ltree(str(db_subject_area.id))

        db.commit()
        db.refresh(db_subject_area)
        return db_subject_area

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания предметной области: {str(e)}"
        ) from e


def update_subject_area(db: Session, subject_area_id: int, data: dict) -> SubjectArea:
    try:
        subject_area = db.query(SubjectArea).filter(SubjectArea.id == subject_area_id).first()
        if not subject_area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Предметная область не найдена"
            )

        # Проверка циклических ссылок
        if 'parent_id' in data and data['parent_id']:
            if data['parent_id'] == subject_area.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Нельзя сделать элемент родителем самого себя"
                )

            new_parent = db.query(SubjectArea).filter(SubjectArea.id == data['parent_id']).first()
            if not new_parent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Родительская область не найдена"
                )

        # Сохраняем старые значения
        old_path = subject_area.path
        old_parent_id = subject_area.parent_id

        # Обновляем простые поля
        for key, value in data.items():
            if hasattr(subject_area, key) and key not in ['parent_id', 'path']:
                setattr(subject_area, key, value)

        # Обрабатываем изменение parent_id
        if 'parent_id' in data:
            new_parent_id = data['parent_id']
            subject_area.parent_id = new_parent_id

            # Вычисляем новый путь
            if new_parent_id is None:
                subject_area.path = Ltree(str(subject_area.id))
            else:
                new_parent = db.query(SubjectArea).filter(SubjectArea.id == new_parent_id).first()
                if not new_parent:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Новый родитель не найден"
                    )
                subject_area.path = Ltree(
                    f"{new_parent.path}.{subject_area.id}" if new_parent.path else str(subject_area.id)
                )

            db.flush()

            # Обновляем пути всех потомков, если изменился parent_id
            if old_path and subject_area.path != old_path:
                update_query = text("""
                    UPDATE subject_areas 
                    SET path = CAST(:new_root AS ltree) || subpath(path, nlevel(CAST(:old_root AS ltree)))
                    WHERE path <@ CAST(:old_root AS ltree) AND id != :exclude_id
                """)

                db.execute(
                    update_query,
                    {
                        "new_root": str(subject_area.path),
                        "old_root": str(old_path),
                        "exclude_id": subject_area.id
                    }
                )

        db.commit()
        db.refresh(subject_area)
        return subject_area

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении предметной области: {str(e)}"
        ) from e


def delete_subject_area(db: Session, subject_area_id: int) -> None:
    try:
        subject_area = get_subject_area(db, subject_area_id)
        if not subject_area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Предметная область не найдена"
            )

        # Проверяем, есть ли дочерние элементы
        child_count = db.query(SubjectArea).filter(SubjectArea.parent_id == subject_area_id).count()
        if child_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Невозможно удалить предметную область с дочерними элементами"
            )

        # Проверяем, используется ли в проектах
        project_count = db.query(Project).filter(Project.subject_area_id == subject_area_id).count()
        if project_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Невозможно удалить предметную область, используемую в проектах"
            )

        db.delete(subject_area)
        db.commit()

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления предметной области: {str(e)}"
        ) from e

# --- ProjectConnection CRUD ---

def get_project_connection(db: Session, project_id: int, related_project_id: int) -> Optional[ProjectConnection]:
    try:
        return db.query(ProjectConnection).filter(
            ProjectConnection.project_id == project_id,
            ProjectConnection.related_project_id == related_project_id
        ).first()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def get_project_connections(db: Session, project_id: int) -> List[ProjectConnection]:
    try:
        return db.query(ProjectConnection).filter(ProjectConnection.project_id == project_id).all()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def create_project_connection(db: Session, pc: ProjectConnectionCreate) -> ProjectConnection:
    try:
        if pc.project_id == pc.related_project_id:
            raise HTTPException(status_code=400, detail="Проект не может быть связан сам с собой")
        existing = get_project_connection(db, pc.project_id, pc.related_project_id)
        if existing:
            raise HTTPException(status_code=400, detail="Связь уже существует")
        db_pc = ProjectConnection(
            project_id=pc.project_id,
            related_project_id=pc.related_project_id
        )
        db.add(db_pc)
        db.commit()
        db.refresh(db_pc)
        return db_pc
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def delete_project_connection(db: Session, project_id: int, related_project_id: int) -> None:
    try:
        pc = get_project_connection(db, project_id, related_project_id)
        if not pc:
            raise HTTPException(status_code=404, detail="Связь проекта не найдена")
        db.delete(pc)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e


# --- TeamMember CRUD ---

def get_team_member(db: Session, team_member_id: int) -> Optional[TeamMember]:
    try:
        return db.query(TeamMember).filter(TeamMember.id == team_member_id).first()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def get_team_members(db: Session, project_id: Optional[int] = None) -> List[TeamMember]:
    try:
        query = db.query(TeamMember)
        if project_id is not None:
            query = query.filter(TeamMember.project_id == project_id)
        return query.all()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def create_team_member(db: Session, tm: TeamMemberCreate) -> TeamMember:
    try:
        db_tm = TeamMember(
            project_id=tm.project_id,
            user_id=tm.user_id,
            role=tm.role
        )
        db.add(db_tm)
        db.commit()
        db.refresh(db_tm)
        return db_tm
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def update_team_member(db: Session, team_member_id: int, data: dict) -> TeamMember:
    try:
        tm = get_team_member(db, team_member_id)
        if not tm:
            raise HTTPException(status_code=404, detail="Участник команды не найден")
        for key, value in data.items():
            setattr(tm, key, value)
        db.commit()
        db.refresh(tm)
        return tm
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def delete_team_member(db: Session, team_member_id: int) -> None:
    try:
        tm = get_team_member(db, team_member_id)
        if not tm:
            raise HTTPException(status_code=404, detail="Участник команды не найден")
        db.delete(tm)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

# --- ProjectFile CRUD ---

def get_project_file(db: Session, file_id: int) -> Optional[ProjectFile]:
    try:
        return db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def get_project_files(db: Session, project_id: Optional[int] = None) -> List[ProjectFile]:
    try:
        query = db.query(ProjectFile)
        if project_id is not None:
            query = query.filter(ProjectFile.project_id == project_id)
        return query.all()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def create_project_file(db: Session, pf: ProjectFileCreate) -> ProjectFile:
    try:
        db_pf = ProjectFile(
            project_id=pf.project_id,
            name=pf.name,
            url=pf.url,
            file_metadata=pf.file_metadata,
            uploaded_by=pf.uploaded_by,
            is_public=pf.is_public
        )
        db.add(db_pf)
        db.commit()
        db.refresh(db_pf)
        return db_pf
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def update_project_file(db: Session, file_id: int, data: dict) -> ProjectFile:
    try:
        pf = get_project_file(db, file_id)
        if not pf:
            raise HTTPException(status_code=404, detail="Файл проекта не найден")
        for key, value in data.items():
            setattr(pf, key, value)
        db.commit()
        db.refresh(pf)
        return pf
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

def delete_project_file(db: Session, file_id: int) -> None:
    try:
        pf = get_project_file(db, file_id)
        if not pf:
            raise HTTPException(status_code=404, detail="Файл проекта не найден")

        try:
            delete_file(file_name=pf.name)  # Ваша функция удаления из MinIO
        except Exception as e:
            print(f"Ошибка удаления из MinIO: {e}")

        db.delete(pf)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка операции: {str(e)}") from e

from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models import Project


def get_projects_filtered(
        db: Session,
        search: Optional[str] = None,
        status: Optional[str] = None,
        subject_area_id: Optional[int] = None,
        is_public: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
) -> List[Project]:
    try:
        query = db.query(Project)

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Project.title.ilike(search_pattern),
                    Project.description.ilike(search_pattern)
                )
            )

        if status:
            query = query.filter(Project.status == status)

        if subject_area_id is not None:
            query = query.filter(Project.subject_area_id == subject_area_id)

        if is_public is not None:
            query = query.filter(Project.is_public == is_public)

        return query.offset(skip).limit(limit).all()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка фильтрации проектов: {str(e)}"
        ) from e
