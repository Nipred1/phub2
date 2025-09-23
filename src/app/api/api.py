from typing import List
from app.auth import RoleChecker

from typing import Optional
from fastapi.responses import StreamingResponse
from urllib.parse import quote


from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.minio_client import upload_file, download_file, update_file_with_rename
from app.database import get_db
from sqlalchemy import func

from app.models import User, Project, ProjectFile
# Report
# ReportCreate, ReportRead
from app.schemas import (
    UserCreate, UserRead,
    ProjectCreate, SubjectAreaCreate, SubjectAreaRead,
    ProjectConnectionCreate, ProjectConnectionRead,
    TeamMemberCreate, TeamMemberRead,
    ProjectFileCreate, ProjectFileRead
)
# get_report, get_reports, create_report, delete_report
from app.crud import (
    get_user, get_users, create_user, delete_user,
    get_project, get_projects, create_project, update_project, delete_project,
    get_subject_area, get_subject_areas, create_subject_area, update_subject_area, delete_subject_area,
    get_project_connections, create_project_connection, delete_project_connection,
    get_team_member, get_team_members, create_team_member, update_team_member, delete_team_member,
    get_project_file, get_project_files, create_project_file, delete_project_file
)

MAX_PROJECT_SIZE_BYTES = 1 * 1024 * 1024 * 1024  # 1 ГБ
router = APIRouter()



# --- Пользователи ---

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

@router.post("/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_new_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_email(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Пользователь с таким email уже существует")
    return create_user(db, user)

@router.get("/users/", response_model=List[UserRead])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_users(db, skip=skip, limit=limit)

@router.get("/users/{user_id}", response_model=UserRead)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_user(user_id: int, db: Session = Depends(get_db)):
    try:
        delete_user(db, user_id)
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при обновлении: {str(e)}"
        )
    return None

# --- Проекты ---

from fastapi import Depends, Query
from typing import Optional, List
from sqlalchemy.orm import Session
from app.crud import get_projects_filtered
from app.schemas import ProjectRead
from sqlalchemy import or_, and_
from sqlalchemy.sql import func
from typing import List, Optional


@router.get("/projects/search_by_all", response_model=List[ProjectRead])
def read_projects(
        search: Optional[str] = Query(None, description="Поиск по названию и описанию"),
        keywords: Optional[str] = Query(None, description="Ключевые слова для поиска в тегах (разделенные запятой)"),
        keyword_match: str = Query("any", description="Тип совпадения: 'any' (любое слово) или 'all' (все слова)"),
        status: Optional[str] = Query(None, description="Статус проекта"),
        subject_area_id: Optional[int] = Query(None, description="ID предметной области"),
        is_public: Optional[bool] = Query(None, description="Публичный проект"),
        skip: int = Query(0, ge=0, description="Пропустить N записей"),
        limit: int = Query(100, ge=1, le=1000, description="Максимум записей"),
        db: Session = Depends(get_db)
):
    try:
        query = db.query(Project)

        # Поиск по названию и описанию
        if search:
            search = search.strip()
            if search:
                search_filter = or_(
                    Project.title.ilike(f"%{search}%"),
                    Project.description.ilike(f"%{search}%")
                )
                query = query.filter(search_filter)

        # Поиск по ключевым словам в тегах
        if keywords:
            keywords = keywords.strip()
            if keywords:
                keyword_list = [k.strip().lower() for k in keywords.split(',') if k.strip()]

                if keyword_match == "all":
                    # Ищем проекты, которые содержат ВСЕ указанные ключевые слова
                    conditions = []
                    for keyword in keyword_list:
                        conditions.append(
                            func.jsonb_path_exists(
                                Project.keywords,
                                f'$[*] ? (@ like_regex "{keyword}" flag "i")'
                            )
                        )
                    query = query.filter(and_(*conditions))
                else:
                    # Ищем проекты, которые содержат ЛЮБОЕ из указанных ключевых слов
                    conditions = []
                    for keyword in keyword_list:
                        conditions.append(
                            func.jsonb_path_exists(
                                Project.keywords,
                                f'$[*] ? (@ like_regex "{keyword}" flag "i")'
                            )
                        )
                    query = query.filter(or_(*conditions))

        # Фильтрация по статусу
        if status:
            query = query.filter(Project.status == status)

        # Фильтрация по предметной области
        if subject_area_id:
            query = query.filter(Project.subject_area_id == subject_area_id)

        # Фильтрация по публичности
        if is_public is not None:
            query = query.filter(Project.is_public == is_public)

        # Применяем пагинацию
        query = query.offset(skip).limit(limit)

        # Выполняем запрос
        projects = query.all()

        return projects

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при поиске проектов: {str(e)}"
        )

@router.get("/projects/search_by_keyword", response_model=List[ProjectRead])
def search_projects_by_partial_keyword(
        keyword: str = Query(..., min_length=1, description="Ключевое слово для поиска"),
        db: Session = Depends(get_db)
):
    try:
        keyword = keyword.strip().lower()

        results = db.query(Project).filter(
            func.jsonb_path_exists(
                Project.keywords,
                f'$[*] ? (@ like_regex "{keyword}" flag "i")'
            )
        ).all()

        if not results:
            raise HTTPException(
                status_code=404,
                detail=f"Проекты по ключевому слову '{keyword}' не найдены"
            )

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при поиске проектов: {str(e)}"
        )

@router.get("/projects_fil/", response_model=List[ProjectRead])
def read_projects(
    search: Optional[str] = Query(None, description="Поиск по названию и описанию"),
    status: Optional[str] = Query(None, description="Статус проекта"),
    subject_area_id: Optional[int] = Query(None, description="ID предметной области"),
    is_public: Optional[bool] = Query(None, description="Публичный проект"),
    skip: int = Query(0, ge=0, description="Пропустить N записей"),
    limit: int = Query(100, ge=1, le=1000, description="Максимум записей"),
    db: Session = Depends(get_db)
):
    projects = get_projects_filtered(
        db=db,
        search=search,
        status=status,
        subject_area_id=subject_area_id,
        is_public=is_public,
        skip=skip,
        limit=limit
    )
    return projects


@router.post("/projects/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_new_project(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(RoleChecker(["админ"]))  # Разрешено только admin
):
    return create_project(db, project)

@router.get("/projects/", response_model=List[ProjectRead])
def read_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_projects(db, skip=skip, limit=limit)

@router.get("/projects/{project_id}", response_model=ProjectRead)
def read_project(project_id: int, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return project

@router.put("/projects/{project_id}", response_model=ProjectRead)
def update_existing_project(project_id: int, project_data: ProjectCreate, db: Session = Depends(get_db)):
    project = update_project(db, project_id, project_data.dict(exclude_unset=True))
    return project

@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project(project_id: int, db: Session = Depends(get_db)):
    delete_project(db, project_id)
    return None

# --- Отчеты ---
#
# @router.post("/reports/", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
# def create_new_report(report: ReportCreate, db: Session = Depends(get_db)):
#     return create_report(db, report)
#
# @router.get("/reports/", response_model=List[ReportRead])
# def read_reports(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
#     return get_reports(db, skip=skip, limit=limit)
#
# @router.get("/reports/{report_id}", response_model=ReportRead)
# def read_report(report_id: int, db: Session = Depends(get_db)):
#     report = get_report(db, report_id)
#     if not report:
#         raise HTTPException(status_code=404, detail="Отчет не найден")
#     return report
#
# @router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
# def remove_report(report_id: int, db: Session = Depends(get_db)):
#     delete_report(db, report_id)
#     return None

# --- Предметные области ---

@router.post("/subject_areas/", response_model=SubjectAreaRead, status_code=status.HTTP_201_CREATED)
def create_new_subject_area(subject_area: SubjectAreaCreate, db: Session = Depends(get_db)):
    return create_subject_area(db, subject_area)

@router.get("/subject_areas/", response_model=List[SubjectAreaRead])
def read_subject_areas(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_subject_areas(db, skip=skip, limit=limit)

@router.get("/subject_areas/{subject_area_id}", response_model=SubjectAreaRead)
def read_subject_area(subject_area_id: int, db: Session = Depends(get_db)):
    subject_area = get_subject_area(db, subject_area_id)
    if not subject_area:
        raise HTTPException(status_code=404, detail="Предметная область не найдена")
    return subject_area

@router.put("/subject_areas/{subject_area_id}", response_model=SubjectAreaRead)
def update_existing_subject_area(subject_area_id: int, subject_area_data: SubjectAreaCreate, db: Session = Depends(get_db)):
    subject_area = update_subject_area(db, subject_area_id, subject_area_data.dict(exclude_unset=True))
    return subject_area

@router.delete("/subject_areas/{subject_area_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_subject_area(subject_area_id: int, db: Session = Depends(get_db)):
    delete_subject_area(db, subject_area_id)
    return None

# --- Связи проектов ---

@router.post("/project_connections/", response_model=ProjectConnectionRead, status_code=status.HTTP_201_CREATED)
def create_new_project_connection(pc: ProjectConnectionCreate, db: Session = Depends(get_db)):
    return create_project_connection(db, pc)

@router.get("/project_connections/{project_id}", response_model=List[ProjectConnectionRead])
def read_project_connections(project_id: int, db: Session = Depends(get_db)):
    return get_project_connections(db, project_id)

@router.delete("/project_connections/{project_id}/{related_project_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_connection(project_id: int, related_project_id: int, db: Session = Depends(get_db)):
    delete_project_connection(db, project_id, related_project_id)
    return None

# --- Участники команд ---

@router.post("/team_members/", response_model=TeamMemberRead, status_code=status.HTTP_201_CREATED)
def create_new_team_member(tm: TeamMemberCreate, db: Session = Depends(get_db)):
    return create_team_member(db, tm)

@router.get("/team_members/", response_model=List[TeamMemberRead])
def read_team_members(project_id: int = None, db: Session = Depends(get_db)):
    return get_team_members(db, project_id)

@router.get("/team_members/{team_member_id}", response_model=TeamMemberRead)
def read_team_member(team_member_id: int, db: Session = Depends(get_db)):
    tm = get_team_member(db, team_member_id)
    if not tm:
        raise HTTPException(status_code=404, detail="Участник команды не найден")
    return tm

@router.put("/team_members/{team_member_id}", response_model=TeamMemberRead)
def update_existing_team_member(team_member_id: int, tm_data: TeamMemberCreate, db: Session = Depends(get_db)):
    tm = update_team_member(db, team_member_id, tm_data.dict(exclude_unset=True))
    return tm

@router.delete("/team_members/{team_member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team_member(team_member_id: int, db: Session = Depends(get_db)):
    delete_team_member(db, team_member_id)
    return None

# --- Файлы проектов ---

@router.post("/project_files/", response_model=ProjectFileRead, status_code=status.HTTP_201_CREATED)
def create_new_project_file(pf: ProjectFileCreate, db: Session = Depends(get_db)):
    return create_project_file(db, pf)

@router.get("/project_files/", response_model=List[ProjectFileRead])
def read_project_files(project_id: int = None, db: Session = Depends(get_db)):
    return get_project_files(db, project_id)

@router.get("/project_files/{file_id}", response_model=ProjectFileRead)
def read_project_file(file_id: int, db: Session = Depends(get_db)):
    pf = get_project_file(db, file_id)
    if not pf:
        raise HTTPException(status_code=404, detail="Файл проекта не найден")
    return pf

@router.put("/project_files/{file_id}", response_model=ProjectFileRead)
async def update_existing_project_file(
    file_id: int,
    file: UploadFile = File(...),
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    # Получаем файл из базы
    pf = get_project_file(db, file_id)
    if not pf:
        raise HTTPException(status_code=404, detail="Файл проекта не найден")

    old_file_name = pf.name
    old_file_size = pf.file_metadata.get("size", 0)

    # Получаем размер нового загружаемого файла
    file.file.seek(0, 2)
    new_file_size = file.file.tell()
    file.file.seek(0)

    # Считаем текущий суммарный размер всех файлов проекта в базе
    total_size = db.query(
        func.coalesce(func.sum(ProjectFile.file_metadata['size'].as_integer()), 0)
    ).filter(ProjectFile.project_id == pf.project_id).scalar() or 0

    # Рассчитываем новый суммарный размер (вычитаем размер старого файла, добавляем нового)
    updated_total_size = total_size - old_file_size + new_file_size

    if updated_total_size > MAX_PROJECT_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Превышен общий размер файлов проекта: допустимо не более 1 ГБ"
        )

    # Обновляем файл в MinIO
    try:
        pf.url = update_file_with_rename(
            new_file_data=file.file,
            old_file_name=old_file_name,
            new_file_name=file.filename,
            content_type=file.content_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении файла в хранилище: {e}")

    # Обновляем запись в базе
    pf.name = file.filename
    pf.file_metadata = {
        "content_type": file.content_type,
        "size": new_file_size
    }
    if is_public is not None:
        pf.is_public = is_public

    try:
        db.add(pf)
        db.commit()
        db.refresh(pf)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении записи в БД: {e}")

    return pf

@router.delete("/project_files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_file(file_id: int, db: Session = Depends(get_db)):
    delete_project_file(db, file_id)
    return None

@router.post("/project_files/upload", response_model=ProjectFileRead, status_code=status.HTTP_201_CREATED)
async def upload_project_file(
    project_id: int,
    uploaded_by: int,
    is_public: Optional[bool] = False,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # Получаем размер загружаемого файла
    file.file.seek(0, 2)  # в конец
    new_file_size = file.file.tell()
    file.file.seek(0)

    # Вычисляем текущий суммарный размер файлов проекта из базы
    total_size_query = (
        db.query(func.coalesce(func.sum(ProjectFile.file_metadata['size'].as_integer()), 0))
        .filter(ProjectFile.project_id == project_id)
    )
    total_size = total_size_query.scalar() or 0

    # Проверяем превышение лимита
    if total_size + new_file_size > MAX_PROJECT_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Превышен общий размер файлов проекта: допустимо не более 1 ГБ"
        )

    # Если всё поднялось — загружаем файл
    try:
        file_url = upload_file(
            file_data=file.file,
            file_name=file.filename,
            content_type=file.content_type
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки файла: {e}")

    # Формируем метаданные с размером и content_type
    file_metadata = {
        "content_type": file.content_type,
        "size": new_file_size
    }

    # Создаём запись в БД
    pf_in = ProjectFileCreate(
        project_id=project_id,
        name=file.filename,
        url=file_url,
        file_metadata=file_metadata,
        uploaded_by=uploaded_by,
        is_public=is_public
    )
    try:
        pf = create_project_file(db, pf_in)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка записи в БД: {e}")

    return pf


def get_project_file(db: Session, file_id: int):
    return db.query(ProjectFile).filter(ProjectFile.id == file_id).first()


@router.get("/project_files/download_by_id/{file_id}", status_code=status.HTTP_200_OK)
def download_project_file_by_id(file_id: int, db: Session = Depends(get_db)):
    try:
        # Получаем запись файла из базы по id
        pf = get_project_file(db, file_id)
        if not pf:
            raise HTTPException(status_code=404, detail="Файл не найден")

        try:
            file_obj = download_file(pf.name)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Ошибка при скачивании файла: {e}")

        # Кодируем имя файла для корректной передачи в заголовке
        encoded_filename = quote(pf.name.encode('utf-8'))

        response = StreamingResponse(
            file_obj,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename*=UTF-8\'\'{encoded_filename}'
            }
        )
        return response

    except HTTPException:
        raise  # Пробрасываем HTTPException как есть
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при скачивании файла: {str(e)}"
        )
