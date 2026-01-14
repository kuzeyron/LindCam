import json
from io import BytesIO

import trio
from kivy.app import App
from kivy.core.image import Image as CoreImage
from kivy.core.window import Window
from kivy.lang import Builder
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

Builder.load_string('''
<SLabel@Label>:
    font_name: 'fonts/JosefinSans-Bold.ttf'
    font_size: dp(24)
    size_hint_y: .1

<SharedImageButton>:
    size: dp(80), dp(80)
    size_hint: None, None
    source: 'icons/share.png'
    canvas.before:
        Color:
            rgba: .6, .2, .2, 1
        RoundedRectangle:
            pos: self.pos
            radius: (dp(20), )
            size: self.size

<SharedVideoButton>:
    size: dp(80), dp(80)
    size_hint: None, None
    source: 'icons/play.png'
    canvas.before:
        Color:
            rgba: .2, .2, .6, 1
        RoundedRectangle:
            pos: self.pos
            radius: (dp(20), )
            size: self.size

<Controller>:
    canvas.before:
        Color:
            rgba: .1, .1, 1, 1
        RoundedRectangle:
            pos: self.pos
            size: self.size

<Base>:
    orientation: 'vertical'
    padding: 0, app.statbar_height, 0, app.navbar_height + dp(5)
    canvas.before:
        Color:
            rgba: 2., .1, 1, .1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: 'vertical'

        Carousel:
            size: self.parent.size

            BoxLayout:
                orientation: 'vertical'

                SBoxLayout:
                    orientation: 'vertical'
                    padding: dp(10), dp(20)
                    spacing: dp(10)
                    canvas.before:
                        Color:
                            rgba: .1, .1, 1, .1
                        Rectangle:
                            size: self.size
                            pos: self.pos
                    SLabel:
                        text: 'Snapshot'
                        pos_hint: {'top': 1}

                    GetFrame:
                        fit_mode: 'contain'
                        id: frame
                        on_release: info.dispatch('on_release')
                        source: 'icons/snap.png'
                        url: root.url

                    SharedImageButton:
                        disabled: info.last_amount == 0 and \
                        not stream.streamable
                        frame: frame.texture
                        pos_hint: {'center_x': .5, 'center_y': .5}

                BoxLayout:
                    height: dp(50)
                    padding: dp(5)
                    size_hint_y: None
                    spacing: dp(5)

                    Controller:
                        disabled: True if info.last_amount > 0 else False
                        remote: info
                        target: 'connect'
                        text: 'Starta flödet'
                        url: root.url

                    Controller:
                        disabled: True if info.last_amount < 1 else False
                        remote: info
                        target: 'disconnect'
                        text: 'Stoppa flödet'
                        url: root.url

            SBoxLayout:
                orientation: 'vertical'
                padding: dp(10), dp(10)
                spacing: dp(10)

                SLabel:
                    text: 'Stream'
                    pos_hint: {'top': 1}

                Streamer:
                    host: app.host
                    id: stream
                    remote: info
                    source: 'icons/play.png'

                SharedVideoButton:
                    disabled: not stream.streamable
                    id: videoshare
                    pos_hint: {'center_x': .5, 'center_y': .5}

        Information:
            id: info
            size_hint_y: .1
            url: root.url
''')


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


class CamApp(App):
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
    trio.run(CamApp().async_run)
