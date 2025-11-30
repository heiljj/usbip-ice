import psycopg
from psycopg.types.enum import Enum, EnumInfo, register_enum

class DeviceState(Enum):
    available = 0
    reserved = 1
    await_flash_default = 2
    flashing_default = 3
    testing = 4
    broken = 5

class Database:
    """Base database class that syncs postgres enums with psycopg"""
    def __init__(self, dburl: str):
        self.url = dburl

        try:
            with psycopg.connect(self.url) as conn:
                info = EnumInfo.fetch(conn, "DeviceState")
                register_enum(info, conn, DeviceState)

        except Exception:
            raise Exception("Failed to connect to database")
