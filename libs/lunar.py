#! /usr/bin/python3
'''
    lunar.py - Calculate Lunar Phase
    Author: Sean B. Palmer, inamidst.com
    Cf. http://en.wikipedia.org/wiki/Lunar_phase#Lunar_phase_calculation
'''
from datetime import datetime
from decimal import Decimal
from math import floor

__all__ = ('lunar_phase', )


def lunar_phase():
    diff = datetime.now() - datetime(2001, 1, 1)
    days = Decimal(diff.days) + (Decimal(diff.seconds) / Decimal(86400))
    lunations = Decimal(.20439731) + (days * Decimal(.03386319269))
    index = floor(lunations % Decimal(1) * Decimal(8)) + Decimal(.5)

    return {0: "wi-moon-alt-full",
            1: "wi-moon-waxing-crescent-3",
            2: "wi-moon-alt-third-quarter",
            3: "wi-moon-waning-crescent-3",
            4: "wi-moon-alt-new",
            5: "wi-moon-alt-waxing-crescent-4",
            6: "wi-moon-alt-first-quarter",
            7: "wi-moon-waning-crescent-3"}[int(index) & 7] + '.png'
