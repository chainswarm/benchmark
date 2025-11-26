from abc import ABC, abstractmethod
from celery import Task
from typing import Any, Dict

from packages.utils.decorators import log_errors

class BaseDataPipelineTask(Task, ABC):

    @log_errors
    @abstractmethod
    def execute_task(self, context) -> Dict[str, Any]:
        pass

    @log_errors
    def run(self, context) -> Dict[str, Any]:
        return self.execute_task(context)