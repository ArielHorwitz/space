from loguru import logger
import sys
import traceback
import asyncio
import prompt_toolkit
from prompt_toolkit import Application
from prompt_toolkit import print_formatted_text as print
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import VSplit, HSplit, Window
from prompt_toolkit.widgets import VerticalLine, HorizontalLine, Frame, TextArea
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
import prompt_toolkit.shortcuts

from gui import STYLE, restart_script, escape_html, window_size
from gui.display import Display
from gui.debug import Debug
from gui.prompt import Prompt
from gui.keybinds import get_keybindings, encode_keyseq
from logic.universe import Universe


HOTKEY_COMMANDS = {
    '^ f12': 'debug',
    'enter': 'focus',
    'space': 'autosim',
    '^ t': 'tick',
    '^ v': 'random',
    '^ c': 'center',
    '^ f': 'flip',
    '^ r': 'reset',
    '^ pageup': 'simrate +10 1',
    '^+ pageup': 'simrate +100 1',
    '^ pagedown': 'simrate -10 1',
    '^+ pagedown': 'simrate -100 1',
    '^ l': 'labels',
    # flight
    '^ up': 'fly',
    '^ down': 'break',
    'up': 'move +1',
    '+ up': 'move +10',
    'down': 'move -1',
    '+ down': 'move -10',
    'left': 'strafe +1',
    '+ left': 'strafe +10',
    'right': 'strafe -1',
    '+ right': 'strafe -10',
    # pov
    'home': 'zoom 1.25',
    'end': 'zoom 0.8',
    '+ home': 'zoom 2',
    '+ end': 'zoom 0.5',
    'd': 'rot +1',
    'D': 'rot +30',
    'a': 'rot -1',
    'A': 'rot -30',
    'w': 'rot 0 +1',
    'W': 'rot 0 +30',
    's': 'rot 0 -1',
    'S': 'rot 0 -30',
    'e': 'rot 0 0 -1',
    'E': 'rot 0 0 -30',
    'q': 'rot 0 0 +1',
    'Q': 'rot 0 0 +30',
    'x': 'flipcam',
    'X': 'flipcam',
}


class App(Application):
    def __init__(self):
        print(HTML('<i>Initializing app...</i>'))
        prompt_toolkit.shortcuts.clear()
        prompt_toolkit.shortcuts.set_title('Space')
        self.universe = Universe()
        self.auto_sim = 10
        self.debug_str = ''
        self.feedback_str = 'Loading...'
        self.display_window = Display(self)
        self.debug_window = Debug(self)
        self.prompt_window = Prompt(self, self.handle_prompt_input)
        self.root_layout = self.get_layout()
        self.commands = {
            'exit': self.exit,
            'quit': self.exit,
            'restart': restart_script,
            'debug': self.debug,
            'focus': self.focus_prompt,
            'autosim': self.toggle_autosim,
            'tick': self.universe.simulate,
            'random': self.universe.randomize_vel,
            'randpos': self.universe.randomize_pos,
            'center': self.universe.center_vel,
            'flip': self.universe.flip_vel,
            'reset': self.universe.reset,
            'simrate': self.set_simrate,
            'labels': self.display_window.toggle_labels,
            'resetcam': self.display_window.reset_camera,
            'flipcam': self.display_window.flip_camera,
            'zoom': self.display_window.zoom_camera,
            'rot': self.display_window.rotate_camera,
            'fly': self.display_window.fly,
            'break': self.display_window.break_move,
            'move': self.display_window.move,
            'strafe': self.display_window.strafe,
            'match': self.universe.match_velocities,
            'meet': self.universe.match_positions,
            'look': self.display_window.camera_look,
        }
        kb = get_keybindings(
            global_keys={
                '^ q': self.exit,
                '^ w': restart_script,
            },
            condition=self.hotkeys_enabled,
            handler=self.handle_hotkey,
        )
        super().__init__(
            layout=self.root_layout,
            style=STYLE,
            full_screen=True,
            key_bindings=kb,
        )
        self.feedback_str = 'Welcome to space.'

    def debug(self, *a):
        self.debug_str += f' | debug args: {a}'

    def hotkeys_enabled(self):
        return not self.root_layout.buffer_has_focus

    def get_layout(self):
        root_container = HSplit([
            VSplit([
                Frame(title='Universe', body=self.display_window),
                Frame(title='Debug', body=self.debug_window),
            ]),
            self.prompt_window,
        ])
        return Layout(root_container)

    def handle_prompt_input(self, buffer):
        text = escape_html(buffer.text)
        self.defocus_prompt()
        if not text:
            return
        command, args = self.resolve_prompt_input(text)
        if command in self.commands:
            self.feedback_str = f'Running command: {command} {args}'
            c = self.commands[command]
            c(*args)
        else:
            self.feedback_str = f'Unkown command: {command} (>> {text})'

    def resolve_prompt_input(self, s):
        command, *args = s.split(' ')
        args = [try_number(a) for a in args]
        return command, args

    def defocus_prompt(self):
        self.root_layout.focus(self.debug_window)

    def focus_prompt(self):
        self.prompt_window.focus()

    def handle_hotkey(self, key):
        if key in HOTKEY_COMMANDS:
            prompt_input = HOTKEY_COMMANDS[key]
            command, args = self.resolve_prompt_input(prompt_input)
            f = self.commands[command]
            f(*args)
            self.debug_str = escape_html(f'Hotkey <{key}> command <{f.__name__}>')
        else:
            self.debug_str = escape_html(f'Hotkey <{key}>')

    def toggle_autosim(self, set_to=None):
        new = 50 if self.auto_sim == 0 else -self.auto_sim
        self.auto_sim = new if set_to is None else set_to
        self.feedback_str = f'Simulation {"in progress" if self.auto_sim else "paused"}'

    def set_simrate(self, value=None, delta=False):
        if delta:
            self.auto_sim = max(0, self.auto_sim + value)
        elif value is None:
            self.auto_sim = 1
        else:
            self.auto_sim = value

    async def logic_loop(self):
        while True:
            if self.auto_sim > 0:
                self.universe.simulate(self.auto_sim)
            await asyncio.sleep(0.02)

    async def refresh_window(self):
        while True:
            self.display_window.update()
            self.debug_window.update()
            self.prompt_window.update()
            self.invalidate()
            await asyncio.sleep(0.02)

    def run(self):
        self.create_background_task(self.logic_loop())
        self.create_background_task(self.refresh_window())
        asyncio.get_event_loop().run_until_complete(self.run_async(pre_run=self.prerun))

    def prerun(self):
        self.defocus_prompt()


def try_number(v):
    try:
        r = float(v)
        if r == int(r):
            r = int(r)
        return r
    except ValueError as e:
        return v


def format_exc(e):
    strs = []
    for line in traceback.format_exception(*sys.exc_info()):
        strs.append(str(line))
    return ''.join(strs)
