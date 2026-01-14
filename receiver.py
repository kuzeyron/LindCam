#! /usr/bin/python3
# coding: utf-8

import json
import logging
from datetime import datetime
from glob import glob
from os.path import join

import trio
from httpx import AsyncClient
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.lang.builder import Builder
from kivy.properties import (BooleanProperty, ColorProperty, ListProperty,
                             NumericProperty, StringProperty)
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from libs.lunar import lunar_phase

with open('configuration.json', encoding='utf-8') as f:
    CONFIG = json.load(f)

Window.size = CONFIG['SETTINGS']['window_size']
Builder.load_string("""
#:import Stream libs.corestreamer.Stream

<Label>:
    font_name: 'fonts/JosefinSans-Bold.ttf'

<BoardText@Label>:
    font_size: dp(60)
    outline_color: 0, 0, 0, .1
    outline_width: dp(2)
    size: self.texture_size
    size_hint: None, None

<Weather>:
    color: 1, 1, 1, .5
    font_size: dp(30)
    pos_hint: {'center_x': .5, 'center_y': .5}
    size: dp(90), dp(90)
    size_hint: None, None
    canvas.before:
        Color:
            rgba: root.heat
        RoundedRectangle:
            pos: self.pos
            radius: (dp(50), )
            size: self.size
        Color:
            rgba: 1, 1, 1, .5
        RoundedRectangle:
            pos: self.x + dp(20), self.y + dp(20)
            radius: (dp(50), )
            size: self.width - dp(40), self.height - dp(40)

    FloatLayout:
        Label:
            color: 0, 0, 0, 1
            font_size: dp(17)
            markup: True
            padding: dp(4), dp(4)
            pos_hint: {'top': 1.2, 'right': 1.2}
            size: self.texture_size
            size_hint: None, None
            text: f'[b]{root.deg}[/b]\u00b0'
            canvas.before:
                Color:
                    rgba: 1, 1, 1, .9
                RoundedRectangle:
                    pos: self.pos
                    radius: (dp(15), )
                    size: self.size

<Lunar>:
    pos_hint: {'center_x': .5, 'center_y': .5}
    size: dp(90), dp(90)
    size_hint: None, None
    canvas.before:
        Color:
            rgba: .3, 1, .3, .5
        RoundedRectangle:
            size: self.size
            pos: self.pos
            radius: (dp(50), )
    Image:
        size: dp(60), dp(60)
        size_hint: None, None
        source: root.path
        canvas.before:
            Color:
                rgba: 0, 0, 0, .4
            RoundedRectangle:
                pos: self.pos
                radius: (dp(50), )
                size: self.size

<Picture>:
    Stream:
        id: streamer
        host: app.host

    Label:
        color: 1, 1, 1, .9
        font_size: dp(65)
        opacity: 0 if streamer.streamable else 1
        outline_color: 0, 0, 0, .1
        outline_width: dp(5)
        text: 'Väntar på flödet från kameran..'

    BoxLayout:
        padding: dp(15)
        pos_hint: {'right': 1}
        size: dp(555), dp(220)
        size_hint: None, None
        spacing: dp(3)
        canvas.before:
            Color:
                rgba: .129, .129, .129, .5
            RoundedRectangle:
                size: self.size
                pos: self.pos
                radius: dp(30), 0, 0, 0
            Color:
                rgba: 1, 1, 1, .2
            SmoothLine:
                rounded_rectangle: (self.x - dp(2.5), self.y - dp(2), self.width + dp(5), \
                self.height + dp(2), dp(30), 0, 0, 0)
                width: dp(1)

        BoxLayout:
            id: station
            orientation: 'vertical'
            size_hint_x: None
            spacing: dp(15)
            width: dp(155)

            Weather:
                id: weather

                AsyncImage:
                    id: weather_icon
                    size: dp(85), dp(85)
                    size_hint: None, None
                    source: self.parent.path
                    canvas.before:
                        Color:
                            rgba: 0, 0, 0, .4
                        RoundedRectangle:
                            pos: self.pos
                            radius: (dp(60), )
                            size: self.size

            AsyncImage:
                id: lunar_icon
                pos_hint: {'center_x': .5}
                size: dp(65), dp(65)
                size_hint: None, None
                canvas.before:
                    Color:
                        rgba: 0, .4, 0, 1
                    RoundedRectangle:
                        pos: self.pos
                        radius: (dp(60), )
                        size: self.size

        BoxLayout:
            orientation: 'vertical'
            spacing: dp(2)

            BoardText:
                color: 1, 1, 1, .9
                text: 'LindCamV3'

            BoardText:
                color: 1, 1, 1, .7
                font_size: dp(50)
                id: date
                text: '00.00.0000'

            BoardText:
                color: 1, 1, 1, .5
                font_size: dp(45)
                id: time
                text: '00:00:00'

""")


class Weather(AnchorLayout):
    deg = NumericProperty()
    heat = ColorProperty((.3, .3, 1, .5))
    path = StringProperty(join('icons', 'na.png'))


class Picture(FloatLayout):
    pass


class CamApp(App):
    host = ListProperty(CONFIG['SERVER']['remote'])
    icon = StringProperty(join('icons', 'snap.png'))
    monitor_is_off = BooleanProperty(None)

    async def async_run(self):
        async with trio.open_nursery() as nursery:
            Clock.schedule_interval(lambda dt: nursery.start_soon(self.check_monitor_status), 60)
            nursery.start_soon(self.check_monitor_status)
            self._nursery = nursery
            await super().async_run(async_lib='trio')
            nursery.cancel_scope.cancel()

    def build(self):
        return Picture()

    async def check_lunar_phase(self):
        self.root.ids.lunar_icon.source = join('icons', 'lunar', lunar_phase())
        self.root.ids.lunar_icon.reload()

    async def check_weather_report(self):
        weather_conf = CONFIG['WEATHER']
        lat, lon = weather_conf['coordinates']
        widget_ids = self.root.ids
        weather = widget_ids.weather

        async with AsyncClient() as client:
            try:
                r = await client.get(f"https://api.openweathermap.org/data/3.0/onecall?lat={lat}&lon={lon}"
                                     f"&appid={weather_conf['key']}&units=metric&exclude=minutely,"
                                     "hourly,daily,alerts")
                data = r.json()['current']
                weather.path = f"https://openweathermap.org/img/wn/{data['weather'][0]['icon']}@2x.png"
                weather.deg = round(data['temp'], 1)

            except Exception as error:
                logging.error("Couldn't fetch weather data: %s", error)
                weather.path = join('icons', 'na.png')
                weather.deg = -99.9

        if 10 > weather.deg > -100:
            weather.heat = .3, .3, 1, .5
        elif 20 > weather.deg > 10:
            weather.heat = .5, .5, 1, .8
        elif 28 > weather.deg > 20:
            weather.heat = .3, 1, .3, .5
        else:
            weather.heat = 1, 1, 0, .8

        widget_ids.weather_icon.reload()

    async def check_monitor_status(self):
        for status in glob('/sys/class/drm/card*[0-1]*/*HDMI*/status'):
            with open(status, encoding='utf-8') as f:
                self.monitor_is_off = not f.read() == 'disconnected\n'
        else:
            self.monitor_is_off = False

    def time_set(self):
        time_now = datetime.now()
        self.root.ids.date.text = time_now.strftime('%d.%m.%Y')
        self.root.ids.time.text = time_now.strftime('%H:%M:%S')

    def on_monitor_is_off(self, _: object, monitor_is_off: bool):
        if monitor_is_off:
            Clock.unschedule(self.check_weather_report)
            Clock.unschedule(self.check_lunar_phase)
            Clock.unschedule(self.time_set)

            return

        Clock.schedule_interval(lambda dt: self._nursery.start_soon(self.check_weather_report),
                                                                    60 * 60 * 2)
        Clock.schedule_interval(lambda dt: self._nursery.start_soon(self.check_lunar_phase),
                                                                    60 * 60 * 4)
        Clock.schedule_interval(lambda dt: self.time_set(), 1)
        self._nursery.start_soon(self.check_weather_report)
        self._nursery.start_soon(self.check_lunar_phase)


if __name__ == "__main__":
    trio.run(CamApp().async_run)
