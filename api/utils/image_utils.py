
#

from io import BytesIO

from PIL import Image

from common import settings


def store_chunk_image(bucket, name, image_binary):
    if settings.STORAGE_IMPL.obj_exist(bucket, name):
        old_binary = settings.STORAGE_IMPL.get(bucket, name)
        old_img = Image.open(BytesIO(old_binary))
        new_img = Image.open(BytesIO(image_binary))
        old_img = old_img.convert("RGB")
        new_img = new_img.convert("RGB")
        width = max(old_img.width, new_img.width)
        height = old_img.height + new_img.height
        combined = Image.new("RGB", (width, height), (255, 255, 255))
        combined.paste(old_img, (0, 0))
        combined.paste(new_img, (0, old_img.height))
        buf = BytesIO()
        combined.save(buf, format="JPEG")
        settings.STORAGE_IMPL.put(bucket, name, buf.getvalue())
    else:
        settings.STORAGE_IMPL.put(bucket, name, image_binary)
