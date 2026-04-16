"""Managed file storage for uploads and exports."""
import os
import shutil
from datetime import datetime

from app.core import settings


class FileManager:
    """Store and retrieve files in organized directories."""

    def __init__(self) -> None:
        self.upload_dir = settings.upload_directory
        self.export_dir = settings.export_directory

    def store_upload(self, deal_id: int, filename: str, source_path: str) -> str:
        month_dir = datetime.utcnow().strftime("%Y-%m")
        dest_dir = os.path.join(self.upload_dir, str(deal_id), month_dir)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        shutil.copy2(source_path, dest_path)
        return dest_path

    def get_upload_path(self, deal_id: int, filename: str) -> str | None:
        for root, _, files in os.walk(os.path.join(self.upload_dir, str(deal_id))):
            if filename in files:
                return os.path.join(root, filename)
        return None
