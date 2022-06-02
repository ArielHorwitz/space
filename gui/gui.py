from loguru import logger
import sys
import traceback
import asyncio
import prompt_toolkit
import arrow
from prompt_toolkit import Application
from prompt_toolkit import print_formatted_text as print
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import VSplit, HSplit, Window
from prompt_toolkit.widgets import VerticalLine, HorizontalLine, Frame, TextArea
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout.layout import Layout
import prompt_toolkit.shortcuts

from gui import STYLE, restart_script, window_size, resolve_prompt_input
from gui.controller import Controller
from gui.screenswitch import ScreenSwitcher
from gui.prompt import Prompt
from gui.keybinds import get_keybindings, encode_keyseq
from usr.config import FPS, HOTKEY_COMMANDS, LAYOUT_SCREENS
from logic.universe import Universe

FRAME_TIME = 1 / FPS
logger.info(f'Running at {FPS} FPS ({FRAME_TIME*1000:.1f} ms)')


class App(Application):
    def __init__(self):
        print(HTML('<i>Initializing app...</i>'))
        prompt_toolkit.shortcuts.clear()
        prompt_toolkit.shortcuts.set_title('Space')
        self._last_key = ''
        self.controller = Controller('App')
        self.universe = Universe(self.controller)
        self.root_layout = self.get_layout()
        self.register_commands()
        kb = get_keybindings(
            global_keys={'^ q': self.exit, '^ w': restart_script, 'escape': self.defocus_prompt},
            condition=self.hotkeys_enabled,
            handler=self.handle_hotkey,
        )

        super().__init__(
            layout=self.root_layout,
            style=STYLE,
            full_screen=True,
            key_bindings=kb,
        )

    # Setup
    def register_commands(self):
        d = {
            'quit': self.exit,
            'quit.restart': restart_script,
            'debug': self.debug,
            'prompt.focus': self.focus_prompt,
            'prompt.defocus': self.defocus_prompt,
            'prompt.clear': self.prompt_window.clear,
            'layout.screen': self.screen_switcher.switch_to,
            'layout.screen.next': self.screen_switcher.next_screen,
        }
        for command, callback in d.items():
            self.controller.register_command(command, callback)

    def get_layout(self):
        self.prompt_window = Prompt(self, self.handle_prompt_input)
        self.screen_switcher = ScreenSwitcher(app=self, screens=LAYOUT_SCREENS)
        root_container = HSplit([
            self.screen_switcher,
            self.prompt_window,
        ])
        return Layout(root_container)

    # Handlers
    def handle_prompt_input(self, text):
        self.defocus_prompt()
        if not text:
            return
        command, args = resolve_prompt_input(text)
        # logger.debug(f'Resolved prompt input: {command} {args}')
        self.controller.do_command(command, *args)

    def handle_hotkey(self, key):
        self._last_key = key
        if key in HOTKEY_COMMANDS:
            prompt_input = HOTKEY_COMMANDS[key]
            # logger.debug(f'Hotkey <{key}> resolved to: {prompt_input}')
            self.handle_prompt_input(prompt_input)
        # else:
        #     logger.debug(f'Unknown hotkey <{key}>')

    def get_window_content(self, name, size=None):
        size = self.screen_size if size is None else size
        content = self.universe.get_window_content(name, size)
        return HTML(content)

    # Miscallaneous
    def defocus_prompt(self):
        self.prompt_window.defocus()

    def focus_prompt(self):
        self.prompt_window.focus()

    def hotkeys_enabled(self):
        return not self.root_layout.buffer_has_focus

    @property
    def screen_size(self):
        width = window_size().columns - 2
        height = window_size().lines - 4
        return width, height

    def debug(self, *a):
        logger.debug(f'Debug action called: {a}')

    # Runtime
    async def logic_loop(self):
        while True:
            self.universe.update()
            await asyncio.sleep(FRAME_TIME)

    async def refresh_window(self):
        while True:
            self.screen_switcher.update()
            self.prompt_window.update()
            self.invalidate()
            await asyncio.sleep(FRAME_TIME)

    def run(self):
        self.create_background_task(self.logic_loop())
        self.create_background_task(self.refresh_window())
        asyncio.get_event_loop().run_until_complete(self.run_async(pre_run=self.prerun))

    def prerun(self):
        self.defocus_prompt()
