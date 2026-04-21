import threading
from typing import Any

_ave_service_instance = None
_ave_service_lock = threading.Lock()

def get_ave_service() -> Any:
    """Singleton getter for AveService (import this in both api_server.py dan ave_monitor.py)"""
    global _ave_service_instance
    if _ave_service_instance is None:
        from ave_service import AveService
        with _ave_service_lock:
            if _ave_service_instance is None:
                _ave_service_instance = AveService()
    return _ave_service_instance
