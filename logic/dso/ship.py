from loguru import logger
import math
import numpy as np
from functools import wraps
from collections import defaultdict, namedtuple

from logic.dso.cockpit import Cockpit
from logic.dso.dso import DeepSpaceObject
from logic import EPSILON


FlightPlan = namedtuple('FlightPlan', ['cutoff', 'break_burn', 'arrival', 'total'])


class Ship(DeepSpaceObject):
    type_name = 'ship'
    thrust = 1
    icon = '·'
    color = 'green'
    current_order_uid = None
    current_flight = None

    def setup(self, name, controller=None):
        self.name = name
        self.label = f'{self.icon}{self.oid} {self.name}'
        self.cockpit = Cockpit(ship=self, controller=controller)
        self.cockpit.follow(self.oid)
        self.stats = defaultdict(lambda: 0)
        if controller:
            self.register_commands(controller)

    def register_commands(self, controller):
        d = {
            'ship.fly': self.fly_to,
            'ship.burn': self.engine_burn,
            'ship.break': self.engine_break_burn,
            'ship.cut': self.engine_cut_burn,
        }
        for command, callback in d.items():
            controller.register_command(command, callback)

    # Orders
    def event_callback(f):
        @wraps(f)
        def event_callback_wrapper(self, uid):
            # Ignore event callback if uid is obsolete
            # uid of 0 means ignore uid check (force callback)
            if uid != 0 and self.check_obsolete_order(uid):
                logger.debug(f'event_callback with obsolete uid: {uid} {f}')
                return
            f(self, uid)
        return event_callback_wrapper

    def check_obsolete_order(self, uid):
        return uid != self.current_order_uid

    # Navigation
    def fly_to(self, oid, cruise_speed):
        target = self.universe.ds_objects[oid]
        self.cockpit.look(oid)
        travel_vector = target.position - self.position
        travel_dist = np.linalg.norm(travel_vector)
        plan = self._simple_flight_plan(
            travel_dist=travel_dist,
            cruise_speed=cruise_speed,
            thrust=self.thrust,
            tick_offset=self.universe.tick,
        )
        # Cruise burn, cruise cutoff, break burn, break cutoff
        self.engine_burn(travel_vector)
        self.universe.add_event(0, plan.cutoff, self.fly_cruise_cutoff,
            f'{self.label}: Cruise burn cutoff')
        self.current_flight = plan
        return plan

    @event_callback
    def fly_cruise_cutoff(self, uid):
        self.engine_cut_burn()
        self.universe.add_event(uid, self.current_flight.break_burn, self.fly_break_burn,
        f'{self.label}: break burn ignition')

    @event_callback
    def fly_break_burn(self, uid):
        self.engine_break_burn()
        self.universe.add_event(uid, self.current_flight.arrival, self.fly_end,
            f'{self.label}: break burn cutoff, arrival.')

    @event_callback
    def fly_end(self, uid):
        self.engine_cut_burn()
        self.current_flight = None

    @staticmethod
    def _simple_flight_plan(travel_dist, cruise_speed, thrust, tick_offset=0):
        burn_time = cruise_speed / thrust
        burn_distance = burn_time * (burn_time + 1) // 2 * thrust
        while burn_distance >= travel_dist / 2:
            cruise_speed *= 0.95
            burn_time = cruise_speed / thrust
            burn_distance = burn_time * (burn_time + 1) // 2 * thrust
        cruise_dist = travel_dist - (burn_distance * 2)
        cruise_time = cruise_dist / cruise_speed
        total = burn_time * 2 + cruise_time
        cutoff = tick_offset + burn_time
        break_burn = cutoff + cruise_time
        arrival = break_burn + burn_time
        fp = FlightPlan(cutoff, break_burn, arrival, total)
        assert arrival / (tick_offset + total) - 1 < EPSILON
        return fp

    # Engine
    def engine_burn(self, vector=None, throttle=1):
        if vector is None:
            self.cockpit.camera.update()
            vector = self.cockpit.camera.current_axes[0]
        assert isinstance(vector, np.ndarray)
        assert vector.shape == (3, )
        mag = np.linalg.norm(vector)
        if mag == 0:
            m = f'{self} trying to engine burn without direction: {vector}'
            logger.warning(m)
            return
        vector *= self.thrust * throttle / mag
        self.universe.engine.get_derivative_second('position')[self.oid] = vector

    def engine_cut_burn(self):
        self.universe.engine.get_derivative_second('position')[self.oid] = 0

    def engine_break_burn(self, throttle=1, auto_cutoff=False):
        v = self.universe.velocities[self.oid]
        mag = np.linalg.norm(v)
        if mag == 0:
            m = f'{self} trying to engine break burn without direction: {v}'
            logger.warning(m)
            return
        self.engine_burn(-v, throttle)
        if auto_cutoff:
            cutoff = self.universe.tick + mag / self.thrust
            self.universe.add_event(0, cutoff, lambda uid: self.engine_cut_burn(),
                f'Auto cutoff engine burn: {mag} v')

    # Properties
    def __repr__(self):
        return f'<Ship {self.label}>'

    @property
    def current_orders(self):
        if self.current_flight:
            return self.format_fp(self.current_flight)
        return 'Idle.'

    def format_fp(self, fp):
        remaining = self.universe.tick - fp.arrival
        if self.universe.tick < fp.cutoff:
            return f'Cruise burn: {self.universe.tick - fp.cutoff:.4f} ({remaining:.4f})'
        elif self.universe.tick < fp.break_burn:
            return f'Cruising: {self.universe.tick - fp.break_burn:.4f} ({remaining:.4f})'
        return f'Break burn: {self.universe.tick - fp.arrival:.4f}'


class Tug(Ship):
    type_name = 'tug'
    thrust = 0.01
    icon = '¬'
    color = 'yellow'


class Fighter(Ship):
    type_name = 'fighter'
    thrust = 3
    icon = '‡'
    color = 'red'


class Escort(Ship):
    type_name = 'escort'
    thrust = 1
    icon = '≡'
    color = 'green'


class Port(Ship):
    type_name = 'port'
    thrust = 0
    icon = 'þ'
    color = 'blue'
