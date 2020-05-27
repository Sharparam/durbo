import asyncio
import logging
import sys
import toml

from tempfile import gettempdir
from pprint import pprint

from telethon import tl

from .tgsyncer import TgSyncer
from .fbsyncer import FbSyncer, FbMessageData

from .config.logging import setup_logging

from .data.base import database, init as init_db
from .data.models import MessageData

# import code; code.interact(local=dict(globals(), **locals()))

log_name = "durbo" if __name__ == "__main__" else __name__

setup_logging()
log = logging.getLogger(log_name)

config = toml.load("config.toml")
dbname = config["database"]["name"]
tgconf = config["telegram"]
fbconf = config["facebook"]

log.info("Initializing database")
init_db(dbname)
database.create_tables([MessageData])

tg = TgSyncer(tgconf)
fb = FbSyncer(fbconf)


async def tg_callback(message: tl.types.Message):
    sender = message.sender
    sender_id = sender.id
    sender_name = (
        f"{sender.first_name} {sender.last_name}".strip()
        or sender.username
        or sender_id
    )

    text = message.raw_text

    if message.poll:
        text = "[Telegram poll, please go to the Telegram group to interact]"
    elif message.game:
        text = "[Telegram game, please go to the Telegram group to interact]"
    elif message.sticker:
        text = "[webp image unsupported by Facebook, please go to the Telegram group to view]"

    reply_to_id = None

    if message.reply_to_msg_id:
        log.debug("Message is a reply, fetching target ID")
        stored_data = MessageData.get_or_none(
            MessageData.tg_message_id == message.reply_to_msg_id
        )
        if stored_data:
            reply_to_id = stored_data.fb_message_id

    media_path = None

    if (message.photo or message.document) and not message.sticker:
        log.info("Message has a file attached, downloading it")
        media_path = await message.download_media(gettempdir())
        log.info("Message media downloaded to %s", media_path)

    sent_message = fb.send_text(f"<{sender_name}>\n{text}", reply_to_id, media_path)

    data = MessageData(
        tg_message_id=message.id,
        tg_sender_id=sender_id,
        tg_chat_id=message.chat_id,
        fb_message_id=sent_message.id,
        fb_sender_id=sent_message.author_id,
        fb_thread_id=sent_message.thread_id,
    )

    data.save()


async def fb_callback(message: FbMessageData):
    log.debug("Facebook message callback")

    sender_id = message.author_id

    reply_to = None

    if message.message_object.reply_to_id:
        log.debug("Message is a reply, fetching target ID")
        stored_data = MessageData.get_or_none(
            MessageData.fb_message_id == message.message_object.reply_to_id
        )
        if stored_data:
            reply_to = stored_data.tg_message_id

    log.debug("Proxying message to telegram")
    sent_messages = await tg.send_text(
        f"<**{message.author_name}**>\n{message.message_object.text or ''}",
        reply_to,
        message.file_paths,
    )

    tg_sender_id = await tg.get_my_id()

    for sent_message in sent_messages:
        data = MessageData(
            tg_message_id=sent_message.id,
            tg_sender_id=tg_sender_id,
            tg_chat_id=sent_message.chat_id,
            fb_message_id=message.id,
            fb_sender_id=sender_id,
            fb_thread_id=message.thread_id,
        )

        data.save()


tg.set_simple_callback(tg_callback)
fb.set_simple_callback(fb_callback)

loop = asyncio.get_event_loop()


async def _amain() -> None:
    log.info("Starting up")

    try:
        await tg.start()
        log.debug("Awaiting sync tasks")
        await asyncio.wait(
            [tg.run_until_disconnected(), fb.run_until_disconnected()],
            return_when=asyncio.FIRST_COMPLETED,
        )

        log.debug("Sync tasks finished")
    except:  # noqa: E722
        info = sys.exc_info()[0]
        log.critical("Unexpected error", exc_info=info)
        raise
    finally:
        await tg.stop()
        fb.stop()


def main() -> None:
    try:
        loop.run_until_complete(_amain())
    except KeyboardInterrupt:
        log.info("User pressed Ctrl-C, exiting")
        loop.run_until_complete(tg.stop())
        fb.stop()
    except:  # noqa: E722
        info = sys.exc_info()[0]
        log.critical("Unexpected error", exc_info=info)
        raise


if __name__ == "__main__":
    main()
