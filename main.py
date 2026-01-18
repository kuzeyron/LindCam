import json
from io import BytesIO

import trio
from kivy.app import App
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.network.urlrequest import UrlRequest
from kivy.properties import (BooleanProperty, DictProperty, ListProperty,
                             NumericProperty, ObjectProperty, StringProperty)
from kivy.uix.behaviors import ButtonBehavior, ToggleButtonBehavior
from kivy.uix.behaviors.touchripple import TouchRippleBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.utils import platform
from libs.corestreamer import Stream
from libs.share import SharedImage, SharedVideo

with open('configuration.json', encoding='utf-8') as f:
    CONFIG = json.load(f)


class Streamer(ButtonBehavior, Stream):
    remote = ObjectProperty(None, allownone=True)
    fit_mode = StringProperty('scale-down')
    host = ListProperty(CONFIG['SERVER']['remote'])

    def on_release(self):
        if self.streamable:
            self.streamable = False
            self.fit_mode = 'scale-down'
            self.texture = CoreImage('icons/play.png',
                                     ext='jpeg').texture
        else:
            self.fit_mode = 'contain'
            self._nursery.start_soon(self.connection)

        self.schedule_info()

    def schedule_info(self, *largs):
        if self.remote is not None:
            self.remote.dispatch('on_release')


class SBoxLayout(TouchRippleBehavior, BoxLayout):
    ripple_scale = NumericProperty(1.5)
    show_traces = BooleanProperty(True)

    def on_touch_down(self, touch):
        super().on_touch_down(touch)
        collide_point = self.collide_point(touch.x, touch.y)

        if collide_point and self.show_traces:
            touch.grab(self)
            self.ripple_show(touch)
            return True
        return False

    def on_touch_up(self, touch):
        super().on_touch_up(touch)

        if touch.grab_current is self:
            touch.ungrab(self)
            self.ripple_fade()
            return True


class Information(ButtonBehavior, Label):
    font_name = StringProperty('fonts/JosefinSans-Bold.ttf')
    last_amount = NumericProperty()

    def on_kv_post(self, _):
        self.dispatch('on_release')

    def on_release(self):
        url = CONFIG['SERVER']['remote'][0]
        http = CONFIG['SERVER']['http']
        UrlRequest(f"http://{url}:{http}/information",
                   self.get_data)

    def get_data(self, req, result):
        self.last_amount = int(result[-1])
        self.text = result


class Controller(ButtonBehavior, Label):
    font_name = StringProperty('fonts/JosefinSans-Bold.ttf')
    remote = ObjectProperty(None, allownone=True)
    target = StringProperty()

    def on_state(self, _, state):
        self.opacity = .5 if state == 'down' else 1

    def on_release(self):
        url = CONFIG['SERVER']['remote'][0]
        http = CONFIG['SERVER']['http']
        UrlRequest(f"http://{url}:{http}/{self.target}",
                   self.schedule_info)

    def schedule_info(self, *largs):
        if self.remote is not None:
            self.remote.dispatch('on_release')


class GetFrame(ButtonBehavior, Image):
    def on_release(self):
        url = CONFIG['SERVER']['remote'][0]
        http = CONFIG['SERVER']['http']
        UrlRequest(f"http://{url}:{http}/frame", self.get_frame)

    def get_frame(self, req, result):
        _bytesio = BytesIO(result)
        _bytesio.seek(0)
        self.texture = CoreImage(_bytesio, ext='jpeg').texture


class SharedImageButton(SharedImage, ButtonBehavior, Image):
    frame = ObjectProperty(None, allownone=True)
    pos_hint = DictProperty({'right': .85, 'center_y': .5})
    fit_mode = StringProperty('fill')

    def on_disabled(self, _, disabled):
        self.opacity = .5 if disabled else 1


class SharedVideoButton(SharedVideo, ToggleButtonBehavior, Image):
    frame = ObjectProperty(None, allownone=True)
    pos_hint = DictProperty({'right': .85, 'center_y': .5})
    fit_mode = StringProperty('fill')

    def on_disabled(self, _, disabled):
        self.opacity = .5 if disabled else 1


class Base(BoxLayout):
    url = StringProperty(CONFIG['SERVER']['remote'][0])


class RemoteToolApp(App):
    icon = StringProperty('icons/snap.png')
    host = ListProperty(CONFIG['SERVER']['remote'])
    monitor_is_off = BooleanProperty(False)
    statbar_height = NumericProperty()
    navbar_height = NumericProperty()

    async def async_run(self):
        async with trio.open_nursery() as nursery:
            Window.bind(on_keyboard=self.key_press)
            self._nursery = nursery
            await super().async_run(async_lib='trio')
            nursery.cancel_scope.cancel()

    def build(self):
        return Base()

    def on_start(self):
        if platform == 'android':
            from android.display_cutout import get_cutout_mode, get_heights_of_both_bars
            if get_cutout_mode() not in {None, 'never'}:
                self.statbar_height, self.navbar_height = get_heights_of_both_bars()

    def key_press(self, w, k, *lr):
        return k == 27


if __name__ == "__main__":
    trio.run(RemoteToolApp().async_run)
