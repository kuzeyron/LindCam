import subprocess
from datetime import datetime
from importlib.util import find_spec
from os import makedirs
from os.path import join

import trio
from kivy.app import App
from kivy.properties import ObjectProperty
from kivy.utils import platform

__all__ = ('SharedImage', 'SharedVideo')

if find_spec('androidstorage4kivy', package='SharedStorage'):
    from android import autoclass, cast, mActivity
    from android.runnable import run_on_ui_thread
    from android.storage import app_storage_path
    from androidstorage4kivy import SharedStorage

    CurrentActivity = cast('android.app.Activity', mActivity)
    Environment = autoclass('android.os.Environment')
    Intent = autoclass('android.content.Intent')
    Shared = SharedStorage()
    StrictMode = autoclass('android.os.StrictMode')
    StrictMode.disableDeathOnFileUriExposure()
    String = autoclass("java.lang.String")
    Toast = autoclass("android.widget.Toast")

    @run_on_ui_thread
    def android_share(filepath: str, directory: str, filetype: str, message: str):
        Toast.makeText(mActivity, String(message), 5000).show()
        file = Shared.copy_to_shared(filepath, collection=directory, filepath=filepath)
        ShareIntent = Intent(Intent.ACTION_SEND)
        ShareIntent.setType(filetype)
        ShareIntent.putExtra(Intent.EXTRA_STREAM, cast('android.os.Parcelable', file))
        ShareIntent.setFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        CurrentActivity.startActivity(ShareIntent)
else:
    from enum import Enum

    class Environment(Enum):  # type: ignore[no-redef]
        DIRECTORY_MOVIES = 1
        DIRECTORY_PICTURES = 2


class ShareBase:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.storage_path = kwargs.get('storage_path', 'LindCam')

    def filename(self):
        return datetime.now().strftime(self.storage_path + '_%d-%m-%Y_%H-%M-%S')

    def android_path(self, ext_type: str):
        content_folder = join(app_storage_path(), self.storage_path)
        makedirs(content_folder, exist_ok=True)

        return join(content_folder, self.filename() + ext_type)

    def linux_path(self, ext_type: str):
        makedirs(self.storage_path, exist_ok=True)

        return join(self.storage_path, self.filename() + ext_type)

    def android_share(self, filepath: str, directory: str, filetype: str, message: str):
        android_share(filepath, directory, filetype, message)

    def linux_share(self, filepath: str, directory: str, filetype: str, message: str):
        pass


class SharedImage(ShareBase):
    frame = ObjectProperty()

    def on_state(self, _: object, state: str):
        if state == 'down':
            filepath = getattr(self, platform + '_path')('.png')
            self.frame.save(filepath, flipped=False)
            share = getattr(self, platform + '_share')
            share(filepath, Environment.DIRECTORY_PICTURES,
                  '"image/.png"', "Gör bilden redo för delning")
            self.opacity = .5
            return
        self.opacity = 1.


class SharedVideo(ShareBase):
    def on_state(self, _: object, state: str):
        if state == 'down':
            trio.lowlevel.spawn_system_task(self.recorder)
            self.opacity = .5
            return
        self.record = False
        self.opacity = 1.

    async def ffmpeg_process(self):
        filepath = getattr(self, platform + '_path')('.mp4')
        stream = App.get_running_app().root.ids.stream
        width, height = stream.texture.size
        self.record = True
        process = subprocess.Popen(['ffmpeg', '-y',
                                    '-f', 'image2pipe', '-vcodec', 'mjpeg',
                                    '-s', f'{width}x{height}', '-r', '15',
                                    '-i', '-',
                                    '-vcodec', 'mpeg4',
                                    '-q:v', '3',
                                    '-pix_fmt', 'yuv420p',
                                    filepath], stdin=subprocess.PIPE)
        while self.record:
            process.stdin.write(stream.frame)
            await trio.sleep(.01)

        process.stdin.close()
        process.wait()

        return filepath

    async def recorder(self):
        filepath = await self.ffmpeg_process()
        share = getattr(self, platform + '_share')
        share(filepath, Environment.DIRECTORY_MOVIES,
              '"video/.mp4"', "Gör videon redo för delning")
