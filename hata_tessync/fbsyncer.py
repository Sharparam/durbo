import asyncio
import logging

from fbchat import Client as FbClient
from fbchat.models import Message, ThreadType

from .utils import memoize


class FbSyncer(FbClient):
    def __init__(self, config: dict, loop: asyncio.AbstractEventLoop = None) -> None:
        self._log = logging.getLogger(__name__)
        self._loop = loop or asyncio.get_event_loop()
        self._master_id = config['master_id']
        user = config['user']
        email = user['email']
        password = user['password']
        self._log.debug('Calling base __init__ with user details')
        super().__init__(email, password)
        group = config['group']
        self._group_id = group['id']

    def start(self) -> None:
        self._log.info('Starting listening loop')
        self.startListening()
        self._log.info('Listening loop started')

    def stop(self) -> None:
        self._log.info('Stopping')
        if self.listening:
            self._log.info('Stopping listening loop')
            self.stopListening()
            self._log.debug('Listening loop stopped')

        if self.isLoggedIn():
            self._log.info('Logging out')
            self.logout()
            self._log.debug('Logged out')

        self._log.info('Stopped')

    async def run_until_disconnected(self) -> None:
        await self._loop.run_in_executor(None, self.listen)

    @memoize
    def get_thread_type(self, thread_id: str) -> ThreadType:
        thread = self.fetchThreadInfo(thread_id)[thread_id]
        return thread.type

    def onMessage(self, mid, author_id, message_object, thread_id, thread_type, ts, metadata, msg, **kwargs):
        if thread_id != self._group_id:
            self._log.debug('Message not in configured group, ignoring')
            return

        self.markAsRead(thread_id)

        if author_id == self.uid:
            self._log.debug('Not processing message from self')
            return

        user = self.fetchUserInfo(author_id)[author_id]
        author_name = user.name
        text = message_object.text.strip()

        if text == '':
            return

        self._log.info('FB [%s] <%s> %s', thread_id, author_name, text)

        if text == '/die' and author_id == self._master_id:
            self._log.info('Master requested death, complying')
            msg = Message(text='Ok :(', reply_to_id=mid)
            self.send(msg, thread_id, thread_type)
            self.stop()
            return
