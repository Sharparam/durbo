import asyncio
import logging
from typing import List

from inspect import isawaitable

from telethon import TelegramClient, events, tl


class TgSyncer:
    def __init__(self, config: dict) -> None:
        self._log = logging.getLogger(__name__)

        self._my_id = None
        self._master_id = config["master_id"]
        user = config["user"]
        session_name = user["session"]
        api_id = user["api_id"]
        api_hash = user["api_hash"]
        self._bot_token = user.get("bot_token")
        group = config["group"]
        self._group_id = group["id"]

        self._client = TelegramClient(session_name, api_id, api_hash)
        self._client.add_event_handler(self._on_newmessage, events.NewMessage)

    @property
    def client(self) -> TelegramClient:
        return self._client

    async def get_my_id(self) -> int:
        if self._my_id:
            return self._my_id

        self._my_id = await self._client.get_peer_id("me")
        return self._my_id

    async def start(self) -> None:
        self._log.info("Starting")
        if self._bot_token:
            self._log.debug("Starting as bot")
            await self._client.start(bot_token=self._bot_token)
        else:
            await self._client.start()

        self._log.debug("Started")

    async def stop(self) -> None:
        self._log.info("Stopping")
        await self._client.disconnect()
        self._log.debug("Stopped")

    async def run_until_disconnected(self) -> None:
        try:
            await self._client.run_until_disconnected()
        except asyncio.CancelledError:
            self._log.warning("Task was canceled")
        finally:
            await self.stop()

    def set_simple_callback(self, callback: callable) -> None:
        self._simple_callback = callback

    async def send_text(
        self, text: str, reply_to=None, file_paths=None
    ) -> List[tl.types.Message]:
        self._log.info("Sending %s to %s", text, self._group_id)

        sent_messages = []

        if file_paths:
            for file_path in file_paths:
                self._log.info("Sending file %s", file_path)
                msg = await self._client.send_message(
                    self._group_id, text, reply_to=reply_to, file=file_path
                )
                sent_messages.append(msg)
        else:
            msg = await self._client.send_message(
                self._group_id, text, reply_to=reply_to
            )
            sent_messages.append(msg)

        return sent_messages

    async def _on_newmessage(self, event: events.NewMessage.Event) -> None:
        message = event.message
        sender = message.sender
        text = message.raw_text
        name = sender.username

        if not name:
            name = f"{sender.first_name} {sender.last_name}".strip()

        if not name:
            name = sender.id

        self._log.info("TG [%s] <%s> %s", event.chat_id, name, text or "<No text>")

        if self._simple_callback:
            cb = self._simple_callback
            r = cb(message)
            if isawaitable(r):
                await r
