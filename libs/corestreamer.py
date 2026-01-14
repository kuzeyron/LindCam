import logging
from datetime import datetime
from io import BytesIO

import trio
from kivy.app import App
from kivy.core.image import ImageLoader
from kivy.graphics.texture import Texture
from kivy.properties import (BooleanProperty, ColorProperty, ObjectProperty,
                             StringProperty)
from kivy.uix.image import Image


class Stream(Image):
    color = ColorProperty((0, 0, 0, 1))
    fit_mode = StringProperty('cover')
    frame = ObjectProperty()
    nocache = BooleanProperty(True)
    streamable = BooleanProperty(False)

    def on_kv_post(self, _):
        self._app = App.get_running_app()
        self._nursery = self._app._nursery
        self._app.bind(monitor_is_off=self.monitor_status)

    def monitor_status(self, _, monitor_is_off):
        if not monitor_is_off:
            self._nursery.start_soon(self.connection)

    async def connection(self):
        texture = Texture.create(size=(1, 1))
        texture.blit_buffer(bytes([0, 0, 0, 0]), colorfmt='rgba', bufferfmt='ubyte')
        self.texture, self.color = texture, (0, 0, 0, 1)

        try:
            if self._app.monitor_is_off:
                logging.warning("[%s] Nothing to show (monitor is off)", datetime.now())

                return

            client_stream = await trio.open_tcp_stream(*self.host)
            self._nursery.start_soon(self.receiver, client_stream)

        except Exception:
            logging.warning("[%s] Couldn't connect to %s on port %s",
                            datetime.now(), *self.host)
            await trio.sleep(5)
            self._nursery.start_soon(self.connection)

    async def receiver(self, client_stream):
        async with client_stream:
            logging.debug("[%s] Connected to %s on port %s", datetime.now(), *self.host)
            from_memory_texture = next(ldr for ldr in ImageLoader.loaders if ldr.can_load_memory())
            frame_ending = b'\xff\xd9'
            frame_start = b'\xff\xd8'
            length_ending = len(frame_ending)
            bytesio_memory = BytesIO()
            self.color = (1, 1, 1, 1)
            self.streamable = True
            image_content = b''

            while self.streamable and not self._app.monitor_is_off and (data := await client_stream.receive_some(4096)):
                image_content += data
                complete_frame_start = image_content.find(frame_start)
                complete_frame_end = image_content.find(frame_ending)

                if complete_frame_start != -1 and complete_frame_end != -1:
                    self.frame = frame = image_content[complete_frame_start:complete_frame_end+length_ending]
                    bytesio_memory.write(frame)
                    bytesio_memory.seek(0)
                    self.texture = from_memory_texture('__inline__', ext='jpg', rawdata=bytesio_memory,
                                                       inline=True, nocache=True, mipmap=False,
                                                       keep_data=False).texture
                    bytesio_memory.seek(0)
                    image_content = image_content[complete_frame_end+length_ending:]

        if not hasattr(self, 'remote'):
            self.streamable = False
            await trio.sleep(2)
            self._nursery.start_soon(self.connection)
