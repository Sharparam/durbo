import asyncio
import logging
from pprint import pprint
from tempfile import mkstemp

from concurrent.futures.thread import ThreadPoolExecutor
from inspect import isawaitable

import fbchat
from fbchat import Client as FbClient
from fbchat.models import Message, ThreadType, Sticker

from PIL import Image

from .utils import memoize, download_file, extension_from_url


class FbMessageData:
    def __init__(self, mid, author_id, author_name, message_object, thread_id, thread_type, ts, metadata, msg, file_paths, **kwargs):
        self._id = mid
        self._author_id = author_id
        self._author_name = author_name
        self._message_object = message_object
        self._thread_id = thread_id
        self._thread_type = thread_type
        self._file_paths = file_paths

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

    @property
    def file_paths(self):
        return self._file_paths


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
        try:
            with ThreadPoolExecutor() as pool:
                await self._loop.run_in_executor(pool, self.listen)
        except asyncio.CancelledError:
            self._log.warning('Task canceled')
        finally:
            self.stop()

    def set_simple_callback(self, callback: callable) -> None:
        self._simple_callback = callback

    @memoize
    def get_thread_type(self, thread_id: str) -> ThreadType:
        thread = self.fetchThreadInfo(thread_id)[thread_id]
        return thread.type

    def send_text(self, text: str, reply_to_id: str = None, media_path: str = None) -> FbSentMessage:
        target_id = self._group_id
        target_type = self.get_thread_type(target_id)
        message = Message(text=text, reply_to_id=reply_to_id)
        self._log.info('Sending "%s" to %s (%s)', text, target_id, target_type)

        if media_path:
            self._log.debug('Sending file %s to messenger', media_path)
            sent_id = self.sendLocalFiles([media_path], message=message, thread_id=target_id, thread_type=target_type)
        else:
            sent_id = self.send(message, target_id, target_type)

        return FbSentMessage(sent_id, self.uid, text, target_id, target_type)

    def onMessage(self, mid, author_id, message_object, thread_id, thread_type, ts, metadata, msg, **kwargs):
        if self._log.isEnabledFor(logging.DEBUG):
            self._log.debug('Received %s from %s in %s (%s) at %s', mid, author_id, thread_id, thread_type, ts)
            pprint(message_object)

        if thread_id != self._group_id:
            self._log.debug('Message not in configured group (%s), ignoring', thread_id)
            return

        self._log.debug('Marking thread as read')
        # self.markAsRead(thread_id)

        if author_id == self.uid:
            self._log.debug('Not processing message from self')
            return

        self._log.debug('Fetching user info for %s', author_id)
        user = self.fetchUserInfo(author_id)[author_id]
        author_name = user.name
        self._log.debug('ID %s has name %s', author_id, author_name)

        file_paths = []

        for attachment in message_object.attachments:
            url = None
            ext = None

            if isinstance(attachment, fbchat.Sticker):
                url = attachment.url
            elif isinstance(attachment, fbchat.FileAttachment):
                url = attachment.url
            elif isinstance(attachment, fbchat.AudioAttachment):
                url = attachment.url
            elif isinstance(attachment, fbchat.ImageAttachment):
                uid = attachment.uid
                ext = attachment.original_extension
                url = self.fetchImageUrl(uid)

            if not url:
                continue

            if not ext:
                ext = extension_from_url(url)

            self._log.info('Downloading message media %s', url)
            path = download_file(url, ext)
            self._log.info('Downloaded to %s', path)
            file_paths.append(path)

        if message_object.sticker:
            sticker_path = self._download_sticker(message_object.sticker)
            file_paths.append(sticker_path)

        data = FbMessageData(mid, author_id, author_name, message_object, thread_id, thread_type, ts, metadata, msg, file_paths, **kwargs)

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

    def _download_sticker(self, sticker: Sticker) -> str:
        if sticker.is_animated == True:
            return self._download_animated_sticker(sticker)

        url = sticker.url
        ext = extension_from_url(url)
        self._log.debug('Message has sticker %s with extension %s', url, ext)
        path = download_file(url, ext)
        self._log.debug('Sticker downloaded to %s', path)

        return path

    def _download_animated_sticker(self, sticker: Sticker) -> str:
        self._log.debug('Converting Facebook animated sticker to GIF')
        spritesheet_url = sticker.large_sprite_image or sticker.medium_sprite_image
        spritesheet_ext = extension_from_url(spritesheet_url)
        self._log.debug('Downloading spritesheet %s', spritesheet_url)
        spritesheet_path = download_file(spritesheet_url, spritesheet_ext)
        self._log.debug('Spritesheet downloaded to %s', spritesheet_path)
        frames_per_row = sticker.frames_per_row
        frames_per_col = sticker.frames_per_col
        fps = sticker.frame_rate
        width = sticker.width
        height = sticker.height
        frame_count = frames_per_row * frames_per_col
        frame_duration_ms = 1000 / fps
        self._log.debug('Sticker has %s frames (%sx%s) sized %sx%s px, playing at %s FPS', frame_count, frames_per_col, frames_per_row, width, height, fps)
        gif_path = mkstemp('.gif', 'durbo_')[1]

        rects = [
            (col * width, row * height, (col + 1) * width, (row + 1) * height)
            for row in range(frames_per_col)
            for col in range(frames_per_row)
        ]

        self._log.debug('Opening spritesheet')
        spritesheet = Image.open(spritesheet_path)

        frames = [spritesheet.crop(rect) for rect in rects]

        self._log.debug('Saving new gif to %s', gif_path)
        frames[0].save(gif_path, save_all=True, append_images=frames[1:], duration=frame_duration_ms, optimize=True)

        return gif_path
