import logging

from telethon import TelegramClient, events


class TgSyncer:
    def __init__(self, config: dict) -> None:
        self._log = logging.getLogger(__name__)

        self._master_id = config['master_id']
        user = config['user']
        self._session_name = user['session']
        self._api_id = user['api_id']
        self._api_hash = user['api_hash']
        self._bot_token = user.get('bot_token', None)
        group = config['group']
        self._group_id = group['id']

        self._client = TelegramClient(self._session_name, self._api_id, self._api_hash)

        @self._client.on(events.NewMessage)
        async def on_newmessage(event: events.NewMessage) -> None:
            await self._on_newmessage(event)

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

    async def _on_newmessage(self, event: events.NewMessage) -> None:
        message = event.message
        sender = message.sender
        text = message.raw_text.strip()

        if text == '':
            self._log.debug('Empty or unsupported message, ignore')
            return

        name = sender.username

        if not name or name == '':
            name = f"{sender.first_name} {sender.last_name}".strip()

        if not name or name == '':
            name = sender.id

        self._log.info('TG [%s] <%s> %s', event.chat_id, name, message.raw_text)
