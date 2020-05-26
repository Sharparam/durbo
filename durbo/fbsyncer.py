import asyncio
import logging

from concurrent.futures.thread import ThreadPoolExecutor
from inspect import isawaitable

from fbchat import Client as FbClient
from fbchat.models import Message, ThreadType

from .utils import memoize


class FbMessageData:
    def __init__(self, mid, author_id, author_name, message_object, thread_id, thread_type, ts, metadata, msg, **kwargs):
        self._id = mid
        self._author_id = author_id
        self._author_name = author_name
        self._message_object = message_object
        self._thread_id = thread_id
        self._thread_type = thread_type

    @property
    def id(self) -> str:
        return self._id

    @property
    def author_id(self) -> str:
        return self._author_id

    @property
    def author_name(self) -> str:
        return self._author_name

    @property
    def message_object(self):
        return self._message_object

    @property
    def thread_id(self) -> str:
        return self._thread_id

    @property
    def is_group(self) -> bool:
        return self._thread_type == ThreadType.GROUP


class FbSentMessage:
    def __init__(self, mid, author_id, text, thread_id, thread_type):
        self._id = mid
        self._author_id = author_id
        self._text = text
        self._thread_id = thread_id
        self._thread_type = thread_type

    @property
    def id(self) -> str:
        return self._id

    @property
    def author_id(self) -> str:
        return self._author_id

    @property
    def text(self):
        return self._text

    @property
    def thread_id(self) -> str:
        return self._thread_id

    @property
    def is_group(self) -> bool:
        return self._thread_type == ThreadType.GROUP


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
        self._log.info('Starting listen loop on separate thread')
        with ThreadPoolExecutor() as pool:
            await self._loop.run_in_executor(pool, self.listen)

    def set_simple_callback(self, callback: callable) -> None:
        self._simple_callback = callback

    @memoize
    def get_thread_type(self, thread_id: str) -> ThreadType:
        thread = self.fetchThreadInfo(thread_id)[thread_id]
        return thread.type

    def send_text(self, text: str, reply_to_id: str = None) -> FbSentMessage:
        target_id = self._group_id
        target_type = self.get_thread_type(target_id)
        message = Message(text=text, reply_to_id=reply_to_id)
        self._log.info('Sending "%s" to %s (%s)', text, target_id, target_type)
        sent_id = self.send(message, target_id, target_type)

        return FbSentMessage(sent_id, self.uid, text, target_id, target_type)

    def onMessage(self, mid, author_id, message_object, thread_id, thread_type, ts, metadata, msg, **kwargs):
        if thread_id != self._group_id:
            self._log.debug('Message not in configured group (%s), ignoring', thread_id)
            return

        self._log.debug('Marking thread as read')
        self.markAsRead(thread_id)

        if author_id == self.uid:
            self._log.debug('Not processing message from self')
            return

        self._log.debug('Fetching user info for %s', author_id)
        user = self.fetchUserInfo(author_id)[author_id]
        author_name = user.name
        self._log.debug('ID %s has name %s', author_id, author_name)
        data = FbMessageData(mid, author_id, author_name, message_object, thread_id, thread_type, ts, metadata, msg, **kwargs)

        self._log.info('FB [%s] <%s> %s', thread_id, author_name, message_object.text)

        if message_object.text == '/die' and author_id == self._master_id:
            self._log.info('Master requested death, complying')
            msg = Message(text='Ok :(', reply_to_id=mid)
            self.send(msg, thread_id, thread_type)
            self.stop()
            return

        if self._simple_callback:
            cb = self._simple_callback
            self._log.debug('Calling callback')
            r = cb(data)
            if isawaitable(r):
                self._log.debug('Running coroutine')
                asyncio.run_coroutine_threadsafe(r, self._loop).result()

    def onMessageError(self, exception=None, msg=None):
        self._log.error("Exception during message handling", exc_info=exception)
