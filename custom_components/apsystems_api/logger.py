import logging
import inspect
import os

class FileLineLogger(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        # Walk the stack and skip frames from this logger helper file
        for frame_info in inspect.stack():
            # Only match frames from your integration, but NOT this logger.py file
            if "custom_components/apsystems_api" in frame_info.filename and "logger.py" not in frame_info.filename:
                filename = os.path.basename(frame_info.filename)
                lineno = frame_info.lineno
                return f"({filename}:{lineno} in {frame_info.function}) {msg}", kwargs
        return msg, kwargs  # fallback

def get_logger(name: str):
    base_logger = logging.getLogger(name)
    return FileLineLogger(base_logger, {})
