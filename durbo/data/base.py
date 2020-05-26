from peewee import SqliteDatabase, Model

database = SqliteDatabase(None)


def init(db_name: str):
    database.init(db_name)


class BaseModel(Model):
    class Meta:
        database = database
