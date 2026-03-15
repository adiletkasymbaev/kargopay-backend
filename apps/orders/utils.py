import base64
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile


def decode_base64_file(base64_string: str, file_name: str = 'image.png') -> UploadedFile:
    """
    Декодирует base64 строку в файл.
    
    Args:
        base64_string: Base64 строка (может включать data:image/png;base64, префикс)
        file_name: Имя файла для создания
    
    Returns:
        ContentFile объект
    """
    # Удаляем data URI префикс если есть (например: "data:image/png;base64,")
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    # Декодируем base64
    file_data = base64.b64decode(base64_string)
    
    # Определяем расширение из MIME типа если есть
    if 'data:image/' in base64_string.split(',')[0] if ',' in base64_string else False:
        mime_type = base64_string.split(',')[0].split(':')[1].split(';')[0]
        extension = mime_type.split('/')[1]
        if extension == 'jpeg':
            extension = 'jpg'
        file_name = f'image.{extension}'
    
    return ContentFile(file_data, name=file_name)
