import logging

from telethon import TelegramClient, events


class TgSyncer:
    def __init__(self, config: dict) -> None:
        self._log = logging.getLogger(__name__)

        self._master_id = config['master_id']
        user = config['user']
        session_name = user['session']
        api_id = user['api_id']
        api_hash = user['api_hash']
        self._bot_token = user.get('bot_token')
        group = config['group']
        self._group_id = group['id']

        self._client = TelegramClient(session_name, api_id, api_hash)
        self._client.add_event_handler(self._on_newmessage, events.NewMessage)

    @property
    def client(self) -> TelegramClient:
        return self._client

    async def start(self) -> None:
        self._log.info('Starting')
        if self._bot_token:
            self._log.debug('Starting as bot')
            await self._client.start(bot_token=self._bot_token)
        else:
            await self._client.start()

        self._log.debug('Started')

    async def stop(self) -> None:
        self._log.info('Stopping')
        await self._client.disconnect()
        self._log.debug('Stopped')

    async def run_until_disconnected(self) -> None:
        await self._client.run_until_disconnected()

    async def _on_newmessage(self, event: events.NewMessage.Event) -> None:
        message = event.message
        sender = message.sender
        text = message.raw_text

        if not text:
            self._log.debug('Empty or unsupported message, ignore')
            return

        name = sender.username

        if not name or name == '':
            name = f"{sender.first_name} {sender.last_name}".strip()

        if not name or name == '':
            name = sender.id

        self._log.info('TG [%s] <%s> %s', event.chat_id, name, message.raw_text)
