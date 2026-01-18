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
from kivy.properties import (BooleanProperty, ColorProperty, ListProperty,
                             NumericProperty, StringProperty)
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.floatlayout import FloatLayout
from libs.lunar import lunar_phase

with open('configuration.json', encoding='utf-8') as f:
    CONFIG = json.load(f)

Window.size = CONFIG['SETTINGS']['window_size']


class Weather(AnchorLayout):
    deg = NumericProperty()
    heat = ColorProperty((.3, .3, 1, .5))
    path = StringProperty(join('icons', 'na.png'))


class Picture(FloatLayout):
    pass


class ReceiverApp(App):
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
    trio.run(ReceiverApp().async_run)
