import asyncio
import logging
import toml

from telethon import tl

from .tgsyncer import TgSyncer
from .fbsyncer import FbSyncer, FbMessageData

from .config.logging import setup_logging

from .data.base import database, init as init_db
from .data.models import MessageData

# import code; code.interact(local=dict(globals(), **locals()))

log_name = 'durbo' if __name__ == '__main__' else __name__

setup_logging()
log = logging.getLogger(log_name)

config = toml.load('config.toml')
dbname = config['database']['name']
tgconf = config['telegram']
fbconf = config['facebook']

log.info('Initializing database')
init_db(dbname)
database.create_tables([MessageData])

tg = TgSyncer(tgconf)
fb = FbSyncer(fbconf)


def tg_callback(message: tl.types.Message):
    sender = message.sender
    sender_id = sender.id
    sender_name = f"{sender.first_name} {sender.last_name}".strip() or sender.username or sender_id

    reply_to_id = None

    if message.reply_to_msg_id:
        log.debug('Message is a reply, fetching target ID')
        stored_data = MessageData.get_or_none(MessageData.tg_message_id == message.reply_to_msg_id)
        if stored_data:
            reply_to_id = stored_data.fb_message_id

    sent_message = fb.send_text(f"<{sender_name}>\n{message.raw_text}", reply_to_id)
    data = MessageData(
        tg_message_id=message.id,
        tg_sender_id=sender_id,
        tg_chat_id=message.chat_id,
        fb_message_id=sent_message.id,
        fb_sender_id=sent_message.author_id,
        fb_thread_id=sent_message.thread_id
    )

    data.save()


async def fb_callback(message: FbMessageData):
    log.debug('Facebook message callback')

    sender_id = message.author_id

    reply_to = None

    if message.message_object.reply_to_id:
        log.debug('Message is a reply, fetching target ID')
        stored_data = MessageData.get_or_none(MessageData.fb_message_id == message.message_object.reply_to_id)
        if stored_data:
            reply_to = stored_data.tg_message_id

    log.debug('Proxying message to telegram')
    sent_message = await tg.send_text(f"<**{message.author_name}**>\n{message.message_object.text}", reply_to)
    data = MessageData(
        tg_message_id=sent_message.id,
        tg_sender_id=sent_message.from_id,
        tg_chat_id=sent_message.chat_id,
        fb_message_id=message.id,
        fb_sender_id=sender_id,
        fb_thread_id=message.thread_id
    )

    data.save()

tg.set_simple_callback(tg_callback)
fb.set_simple_callback(fb_callback)

loop = asyncio.get_event_loop()


async def _amain() -> None:
    log.info('Starting up')

    try:
        await tg.start()
        log.debug('Awaiting sync tasks')
        await asyncio.wait([
            tg.run_until_disconnected(),
            fb.run_until_disconnected()])

        log.debug('Sync tasks finished')
    finally:
        await tg.stop()
        fb.stop()


def main() -> None:
    try:
        loop.run_until_complete(_amain())
    except KeyboardInterrupt:
        log.info('User pressed Ctrl-C, exiting')
        loop.run_until_complete(tg.stop())
        fb.stop()


if __name__ == '__main__':
    main()
