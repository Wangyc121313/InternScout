import os
import sys
from pathlib import Path

from loguru import logger as _logger


class LoggerConfig:
    """日志配置类"""

    DEFAULT_FORMAT = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"

    @classmethod
    def setup(
        cls,
        level: str = "INFO",
        log_file: str = None,
        format_str: str = None,
        rotation: str = "10 MB",
        retention: str = "30 days",
    ):
        """配置日志"""
        format_str = format_str or cls.DEFAULT_FORMAT

        # 移除默认的处理器
        _logger.remove()

        # 添加控制台处理器
        _logger.add(
            sys.stdout,
            level=level,
            format=format_str,
            colorize=True,
        )

        # 添加文件处理器
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            _logger.add(
                log_file,
                level=level,
                format=format_str,
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
            )

        return _logger


def get_logger(name: str = None):
    """
    获取logger实例

    Args:
        name: 模块名称，会添加到日志中

    Returns:
        logger实例
    """
    if name:
        return _logger.bind(name=name)
    return _logger


# 从环境变量加载配置
_level = os.getenv("LOG_LEVEL", "INFO")
_log_file = os.getenv("LOG_FILE", "logs/internscout.log")

# 初始化默认配置
LoggerConfig.setup(level=_level, log_file=_log_file)
