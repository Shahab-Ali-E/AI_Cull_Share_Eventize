from typing import Dict
import uuid

class ProgressManager:
    def __init__(self):
        self.progress_data: Dict[str, int] = {}

    def start_task(self) -> str:
        task_id = str(uuid.uuid4())
        self.progress_data[task_id] = 0
        return task_id

    def update_progress(self, task_id: str, progress: int):
        if task_id in self.progress_data:
            self.progress_data[task_id] = progress

    def get_progress(self, task_id: str) -> int:
        return self.progress_data.get(task_id, 0)

    def finish_task(self, task_id: str):
        if task_id in self.progress_data:
            del self.progress_data[task_id]

progress_manager = ProgressManager()
