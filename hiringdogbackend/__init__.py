from .celery import app

__all__ = ("app",)
import pymysql
pymysql.install_as_MySQLdb()