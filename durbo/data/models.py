from peewee import IntegerField, CharField

from .base import BaseModel


class MessageData(BaseModel):
    tg_message_id = IntegerField(index=True)
    tg_sender_id = IntegerField(index=True)
    tg_chat_id = IntegerField(index=True)
    fb_message_id = CharField(index=True)
    fb_sender_id = CharField(index=True)
    fb_thread_id = CharField(index=True)

    class Meta:
        indexes = (
            (('tg_message_id', 'fb_message_id'), True),
        )
