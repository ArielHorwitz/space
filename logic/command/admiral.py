
from loguru import logger
import math
import random
import numpy as np
from gui import OBJECT_COLORS
from logic import CELESTIAL_NAMES
from logic.dso.ship import Ship, Tug, Fighter, Escort, Port
from logic.dso.celestial import CelestialObject


PREFIXES = ['XSS', 'KRS', 'ISS', 'JTS', 'VSS']
ADMIRAL_POLL_INTERVAL = 1000
SHIP_CLASSES = [Tug, Fighter, Escort, Port]
SHIP_WEIGHTS = [10, 2, 1, 1]


class Admiral:
    flagship_name = 'Flagship'

    def __init__(self, universe, fid, name):
        self.universe = universe
        self.fid = fid
        self.name = name
        self.ship_prefix = random.choice(PREFIXES)
        self.fleet = []
        self.fleet_oids = set()

    def setup(self):
        self.add_flagship()

    def add_flagship(self):
        ship_name = f'{self.ship_prefix}. {self.flagship_name}'
        self.my_ship = self.universe.add_object(Escort, fid=self.fid, name=ship_name)

    def add_ship(self, cls, name, parent):
        ship_name = f'{self.ship_prefix}. {name}'
        new_ship = self.universe.add_object(cls, fid=self.fid, name=ship_name, parent=parent)
        self.fleet.append(new_ship)
        self.fleet_oids.add(new_ship.oid)

    def __repr__(self):
        return f'<Admiral {self.name} FID #{self.fid}>'

    @property
    def fleet_str(self):
        return '\n'.join(f'{s.label}' for s in self.fleet)

    def print_fleet(self):
        self.universe.output_console(self.fleet_str)

    @property
    def position(self):
        return self.my_ship.position


class Player(Admiral):
    flagship_name = 'Devship'
    def setup(self, controller):
        assert self.fid == 0
        super().setup()
        self.register_commands(controller)
        self.make_fleet(20)

    def register_commands(self, controller):
        d = {
            'admiral.fleet': self.print_fleet,
            'order': self.order_ship,
            **{f'ship.{k}': v for k, v in self.my_ship.commands.items()},
            **{f'cockpit.{k}': v for k, v in self.my_ship.cockpit.commands.items()},
        }
        for command, callback in d.items():
            controller.register_command(command, callback)

    def get_charmap(self, size):
        return self.my_ship.cockpit.get_charmap(size)

    def make_fleet(self, count=20):
        for i in range(count):
            batch_idx = i % 10
            cls = Tug
            if batch_idx == 0:
                cls = Port
            elif batch_idx < 3:
                cls = Fighter
            ship_name = random.choice(CELESTIAL_NAMES)
            self.add_ship(cls, name=ship_name, parent=self.my_ship)

    def order_ship(self, command_name, oid, *args):
        ship = self.universe.ds_objects[oid]
        if oid not in self.fleet_oids:
            self.print_fleet()
            self.universe.output_feedback(f'{ship.label} not in my fleet.')
            return
        command = ship.commands[command_name]
        command(*args)


class Agent(Admiral):
    def setup(self, *a, **k):
        super().setup()
        self.universe.add_event(0, None, self.first_order, 'Start first order')

    def get_new_destination(self):
        oid = random.randint(0, self.universe.object_count-1)
        while not isinstance(self.universe.ds_objects[oid], CelestialObject):
            oid = random.randint(0, self.universe.object_count-1)
        return oid

    def first_order(self, uid):
        oids = random.choices(np.flatnonzero(self.universe.ds_celestials), k=5)
        self.my_ship.order_patrol(oids)
