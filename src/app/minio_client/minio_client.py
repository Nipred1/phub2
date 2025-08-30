from minio import Minio
from minio.error import S3Error
import os

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_SECURE = False

client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

BUCKET_NAME = "project-files"

def ensure_bucket_exists():
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)

def upload_file(file_data, file_name: str, content_type: str):
    """
    file_data — объект с методом read(), например UploadFile.file
    """
    ensure_bucket_exists()
    # Если file_data — объект с read(), можно передать длину файла, если известна
    file_data.seek(0, 2)  # Перемещаемся в конец файла, чтобы узнать размер
    size = file_data.tell()
    file_data.seek(0)     # Возвращаемся в начало

    client.put_object(
        bucket_name=BUCKET_NAME,
        object_name=file_name,
        data=file_data,
        length=size,
        content_type=content_type
    )
    return f"{MINIO_ENDPOINT}/{BUCKET_NAME}/{file_name}"

def download_file(file_name: str):
    """
    Скачивает файл из MinIO.
    Возвращает объект Response или поток байт.
    """
    try:
        response = client.get_object(BUCKET_NAME, file_name)
        return response
    except S3Error as err:
        raise Exception(f"Ошибка при скачивании файла: {err}")

def delete_file(file_name: str):
    try:
        client.remove_object(BUCKET_NAME, file_name)
    except S3Error as err:
        raise Exception(f"Ошибка при удалении файла: {err}")

def update_file_with_rename(new_file_data, old_file_name: str, new_file_name: str, content_type: str):
    """
    Обновляет файл в MinIO, удаляя старый файл с old_file_name и загружая новый под new_file_name.

    new_file_data — объект с методом read(), например UploadFile.file
    old_file_name — текущее имя файла в MinIO (для удаления)
    new_file_name — новое имя файла для загрузки
    """

    ensure_bucket_exists()

    # Удаляем старый файл, если он существует
    try:
        client.remove_object(BUCKET_NAME, old_file_name)
    except S3Error as err:
        # Игнорируем ошибку если файла не было, иначе пробрасываем
        if "not found" not in str(err).lower():
            raise Exception(f"Ошибка при удалении старого файла: {err}")

    # Определяем размер нового файла
    new_file_data.seek(0, os.SEEK_END)
    size = new_file_data.tell()
    new_file_data.seek(0)

    # Загружаем новый файл с новым именем
    client.put_object(
        bucket_name=BUCKET_NAME,
        object_name=new_file_name,
        data=new_file_data,
        length=size,
        content_type=content_type
    )

    return f"{MINIO_ENDPOINT}/{BUCKET_NAME}/{new_file_name}"