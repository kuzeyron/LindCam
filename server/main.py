import json
import logging
import os
from datetime import datetime
from importlib.util import find_spec
from os.path import abspath, dirname, join
from threading import Thread

import numpy as np
import trio
from cv2 import (CAP_PROP_POS_FRAMES, IMWRITE_JPEG_QUALITY, VideoCapture,
                 imencode)
from fastapi import FastAPI, Request, Response
from hypercorn.config import Config
from hypercorn.trio import serve

if SYSTEM_IS_PI := find_spec('picamera2', package='Picamera2'):
    os.environ['LIBCAMERA_LOG_LEVELS'] = '4'
    from libcamera import controls
    from picamera2 import Picamera2

SCRIPT_LOCATION = dirname(abspath(__file__))
logging.basicConfig(filename=join(SCRIPT_LOCATION, 'logs.txt'), filemode='a',
                    format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S',
                    level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler())

with open(join(SCRIPT_LOCATION, 'configuration.json'), encoding='utf-8') as f:
    SERVER_CONFIG = json.load(f)

config = Config()
config.bind = [':'.join((SERVER_CONFIG['SERVER']['host'][0],
                         SERVER_CONFIG['SERVER']['http']))]
app = FastAPI(docs_url=None, redoc_url=None)

def log(text, prompt_user, has_arg=None):
    has_arg = f': {has_arg}' if has_arg else ''
    logging.info(f"[ {prompt_user} ] [{datetime.now()}] {text}{has_arg}.")


class Device:
    def __init__(self, **kwargs):
        for key, value in {**SERVER_CONFIG['CAMERA'], **kwargs}.items():
            setattr(self, key, value)

        self.frame_reset()

        if SYSTEM_IS_PI:
            self.picam2 = Picamera2()
            self.picam2.set_logging(logging.ERROR)

    def frame_reset(self):
        self.compression(np.zeros((*self.resolution[::-1], 3), np.uint8))

    def start(self):
        "Starts the feed of chosen device (camera or video)"
        target = getattr(self, self.target, None)

        if callable(target):
            self.is_running = True
            Thread(target=target, daemon=True).start()
            log('Is now trying stream video.',
                SERVER_CONFIG['SERVER']['prompt_user'])

    def stop(self):
        self.is_running = False

    def camera(self):
        "Camera-stream directly with a supported camera"
        if SYSTEM_IS_PI:
            config = self.picam2.create_still_configuration(
                main={'size': self.resolution, 'format': 'RGB888'},
                controls={'FrameRate': self.fps, 'AfMode': controls.AfModeEnum.Continuous,
                          'LensPosition': 3.5})
            self.picam2.configure(config)
            self.picam2.start()

            while self.is_running:
                self.compression(self.picam2.capture_array())

            self.picam2.stop()

            return self.frame_reset()

        self.video()

    def video(self):
        "Stream directly with the use of OpenCV"
        cap = VideoCapture(self.captureport if self.target == 'camera'
                           else self.videosource)

        while cap.isOpened() and self.is_running:
            ret, frame = cap.read()
            if ret:
                self.compression(frame)
            else:
                cap.set(CAP_PROP_POS_FRAMES, 0)

        self.frame_reset()

    def compression(self, frame):
        "Compression for transport"
        quality = max(30, int(np.average(np.linalg.norm(frame) / np.sqrt(3)) / 1000))
        compressed_img = imencode('.jpg', frame, (int(IMWRITE_JPEG_QUALITY),
                                                  quality))[1]
        self.frame = compressed_img.tobytes()


class FeedStream:
    def __init__(self, **kwargs):
        self._active_sessions = 0
        self.active_addresses = []

        for key, value in {**SERVER_CONFIG['SERVER'], **kwargs}.items():
            setattr(self, key, value)

        log(f'Initializing the socket protocol on port {self.host[1]}',
            self.prompt_user)

        self.first_listener = True
        self.device = Device()

    @property
    def active_sessions(self):
        return self._active_sessions

    @active_sessions.setter
    def active_sessions(self, value):
        self._active_sessions = max(0, value)

        if self._active_sessions == 1 and self.first_listener:
            self.device.start()
            self.first_listener = False

        if self._active_sessions == 0:
            self.device.stop()
            self.first_listener = True

        log('List of active users', self.prompt_user,
            f"({', '.join(self.active_addresses) or 'None'})")

    @active_sessions.getter  # type: ignore[misc]
    def active_sessions(self):
        return self._active_sessions

    async def run(self):
        async with trio.open_nursery() as nursery:
            self._nursery = nursery
            nursery.start_soon(trio.serve_tcp, self.transmit_data,
                               self.host[1])
            nursery.start_soon(serve, app, config)

    async def transmit_data(self, server_stream):
        "Streams the cached frames to chosen listener"
        client_ip, client_port = server_stream.socket.getpeername()
        user = f"{client_ip}:{client_port}"
        self.active_addresses.append(user)
        self.active_sessions += 1
        log('Is now connected and ready to stream', self.prompt_user, f'"{user}"')
        cached_id = None

        while True:
            try:
                frame = self.device.frame
                if cached_id != (frame_id := id(frame)):
                    await server_stream.send_all(frame)
                    cached_id = frame_id
            except (trio.BrokenResourceError, OSError):
                break

        self.active_addresses.pop(self.active_addresses.index(user))
        log('Disconnected user', self.prompt_user, f'"{user}"')
        self.active_sessions -= 1


@app.get('/frame', responses={200: {'content': {'image/jpeg': {}}}},
         response_class=Response)
async def frame(_: Request):
    return Response(content=feed.device.frame, media_type='image/jpeg')


@app.get('/info')
async def info(_: Request):
    return dict(quality=feed.device.framequality, target=feed.device.target,
                resolution=feed.device.resolution)


@app.get('/disconnect')
async def disconnect(_: Request):
    feed.active_sessions -= 1
    return 'Connected' if feed.active_sessions else 'Disconnected'


@app.get('/connect')
async def connect(_: Request):
    feed.active_sessions += 1
    return 'Connected' if feed.active_sessions else 'Disconnected'


@app.get('/information')
async def information(_: Request):
    return f'Antal lyssnaren: {feed.active_sessions}'


feed = FeedStream()
trio.run(feed.run)
