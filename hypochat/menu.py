import curses
from dataclasses import dataclass
from typing import Any, Callable

from hypochat.storage.contact_store import load_contacts


@dataclass
class MenuAction:
    name: str
    kwargs: dict[str, Any]


class HypochatMenu:
    def __init__(self):
        self.stack: list[tuple[str, list[tuple[str, Any]], int]] = []
        self.result: MenuAction | None = None
        self.colors_enabled = False

    def _setup_colors(self):
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
            except Exception:
                pass
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_YELLOW, -1)
            curses.init_pair(4, curses.COLOR_WHITE, -1)
            self.colors_enabled = True

    def _color(self, pair_id: int, extra: int = 0) -> int:
        if not self.colors_enabled:
            return extra
        return curses.color_pair(pair_id) | extra

    def _draw_menu(self, stdscr, title: str, items: list[tuple[str, Any]], selected: int, hint: str = "↑/↓ move • Enter select • Esc back"):
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        stdscr.addnstr(1, 0, " H Y P O C H A T ".center(max(1, width)), width, self._color(1, curses.A_BOLD))
        stdscr.addnstr(3, 2, title, max(1, width - 4), self._color(4, curses.A_BOLD))
        row = 5
        for idx, (label, _payload) in enumerate(items):
            attr = self._color(2, curses.A_BOLD) if idx == selected else self._color(4)
            prefix = "❯ " if idx == selected else "  "
            stdscr.addnstr(row, 4, prefix + label, max(1, width - 8), attr)
            row += 1
        stdscr.addnstr(height - 2, 2, hint, max(1, width - 4), self._color(3))
        stdscr.refresh()

    def _input_box(self, stdscr, title: str, label: str, initial: str = "", password: bool = False, allow_empty: bool = False) -> str | None:
        buffer = initial
        cursor = len(buffer)
        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            usable_width = max(10, width - 4)
            inner_width = max(8, usable_width - 2)
            top = "╭" + f" {title} " + ("─" * max(0, inner_width - len(title) - 2)) + "╮"
            display = ("*" * len(buffer) if password else buffer)
            visible = display[-max(1, inner_width - 2):]
            middle = "│ " + visible.ljust(max(1, inner_width - 2)) + " │"
            bottom = "╰" + ("─" * inner_width) + "╯"
            stdscr.addnstr(2, 2, title, max(1, width - 4), self._color(1, curses.A_BOLD))
            stdscr.addnstr(4, 2, label, max(1, width - 4), self._color(4))
            stdscr.addnstr(6, 2, top[:usable_width], usable_width)
            stdscr.addnstr(7, 2, middle[:usable_width], usable_width)
            stdscr.addnstr(8, 2, bottom[:usable_width], usable_width)
            stdscr.addnstr(height - 2, 2, "Enter submit • Esc cancel • ←/→ edit", max(1, width - 4), self._color(3))
            cursor_x = min(usable_width - 2, 4 + len(visible))
            stdscr.move(7, cursor_x)
            stdscr.refresh()

            ch = stdscr.getch()
            if ch in (27,):
                return None
            if ch in (10, 13, curses.KEY_ENTER):
                if buffer or allow_empty:
                    return buffer
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                if cursor > 0:
                    buffer = buffer[:cursor - 1] + buffer[cursor:]
                    cursor -= 1
            elif ch == curses.KEY_DC:
                if cursor < len(buffer):
                    buffer = buffer[:cursor] + buffer[cursor + 1:]
            elif ch == curses.KEY_LEFT:
                cursor = max(0, cursor - 1)
            elif ch == curses.KEY_RIGHT:
                cursor = min(len(buffer), cursor + 1)
            elif ch == curses.KEY_HOME:
                cursor = 0
            elif ch == curses.KEY_END:
                cursor = len(buffer)
            elif 32 <= ch <= 126:
                buffer = buffer[:cursor] + chr(ch) + buffer[cursor:]
                cursor += 1

    def _confirm(self, stdscr, title: str, lines: list[str]) -> bool:
        selected = 0
        choices = ["Confirm", "Cancel"]
        while True:
            stdscr.erase()
            height, width = stdscr.getmaxyx()
            stdscr.addnstr(2, 2, title, max(1, width - 4), self._color(1, curses.A_BOLD))
            row = 4
            for line in lines:
                stdscr.addnstr(row, 2, line, max(1, width - 4), self._color(4))
                row += 1
            row += 1
            for idx, choice in enumerate(choices):
                attr = self._color(2, curses.A_BOLD) if idx == selected else self._color(4)
                prefix = "❯ " if idx == selected else "  "
                stdscr.addnstr(row + idx, 4, prefix + choice, max(1, width - 8), attr)
            stdscr.refresh()
            ch = stdscr.getch()
            if ch == 27:
                return False
            if ch == curses.KEY_UP:
                selected = (selected - 1) % len(choices)
            elif ch == curses.KEY_DOWN:
                selected = (selected + 1) % len(choices)
            elif ch in (10, 13, curses.KEY_ENTER):
                return selected == 0

    def _root_items(self):
        return [
            ("Identity", self._identity_menu),
            ("Contacts", self._contacts_menu),
            ("Doctor", MenuAction("doctor", {})),
            ("Chat", self._chat_menu),
            ("Ghost", self._ghost_menu),
            ("Relays", self._relay_menu),
            ("Privacy", self._privacy_menu),
            ("Version", MenuAction("version", {})),
            ("Exit", None),
        ]

    def _identity_menu(self):
        return [
            ("Init identity", "identity_init"),
            ("Show public ID", "identity_id"),
            ("Export recovery key", "identity_export"),
            ("Import recovery key", "identity_import"),
            ("Back", None),
        ]

    def _contacts_menu(self):
        return [
            ("Add contact", "contact_add"),
            ("List contacts", MenuAction("contacts", {})),
            ("Remove contact", "contact_remove"),
            ("Back", None),
        ]

    def _chat_menu(self):
        contacts = load_contacts()
        items: list[tuple[str, Any]] = []
        for contact in contacts:
            items.append((f"{contact['nickname']}  ({contact['public_id'][:18]}...)", MenuAction("chat", {"target": contact["nickname"], "password": None, "tor": None, "store_history": None})))
        items.append(("Chat by nickname/npub manually", "chat_open_manual"))
        items.append(("Back", None))
        return items

    def _ghost_menu(self):
        contacts = load_contacts()
        items: list[tuple[str, Any]] = []
        for contact in contacts:
            items.append((f"{contact['nickname']}  ({contact['public_id'][:18]}...)", MenuAction("ghost", {"target": contact["nickname"], "tor": None})))
        items.append(("Ghost chat by nickname/npub manually", "ghost_open_manual"))
        items.append(("Passive ghost mode", MenuAction("ghost", {"target": None, "tor": None})))
        items.append(("Back", None))
        return items

    def _relay_menu(self):
        return [
            ("List relays", MenuAction("relay_list", {})),
            ("Add relay", "relay_add"),
            ("Remove relay", "relay_remove"),
            ("Back", None),
        ]

    def _privacy_menu(self):
        return [
            ("Usable sync mode", MenuAction("privacy_set", {"use_tor": None, "store_history": False, "tor_proxy": None, "privacy_mode": "usable-sync"})),
            ("Strict no-trace mode", MenuAction("privacy_set", {"use_tor": None, "store_history": False, "tor_proxy": None, "privacy_mode": "strict-no-trace"})),
            ("Set Tor ON, history OFF", MenuAction("privacy_set", {"use_tor": True, "store_history": False, "tor_proxy": None, "privacy_mode": None})),
            ("Set Tor OFF, history OFF", MenuAction("privacy_set", {"use_tor": False, "store_history": False, "tor_proxy": None, "privacy_mode": None})),
            ("Back", None),
        ]

    def _handle_leaf(self, stdscr, token: str | MenuAction | None):
        if token is None:
            return "back"
        if isinstance(token, MenuAction):
            self.result = token
            return "done"
        if token == "identity_init":
            password = self._input_box(stdscr, "Init identity", "Password:", password=True)
            if password is None:
                return None
            confirm = self._input_box(stdscr, "Init identity", "Confirm password:", password=True)
            if confirm is None or confirm != password:
                return None
            self.result = MenuAction("init", {"password": password})
            return "done"
        if token == "identity_id":
            password = self._input_box(stdscr, "Show public ID", "Password:", password=True)
            if password is None:
                return None
            self.result = MenuAction("id", {"password": password})
            return "done"
        if token == "identity_export":
            password = self._input_box(stdscr, "Export recovery key", "Password:", password=True)
            if password is None:
                return None
            self.result = MenuAction("export", {"password": password})
            return "done"
        if token == "identity_import":
            nsec = self._input_box(stdscr, "Import identity", "Recovery key (nsec):")
            if nsec is None:
                return None
            password = self._input_box(stdscr, "Import identity", "Password:", password=True)
            if password is None:
                return None
            confirm = self._input_box(stdscr, "Import identity", "Confirm password:", password=True)
            if confirm is None or confirm != password:
                return None
            self.result = MenuAction("import", {"nsec": nsec, "password": password})
            return "done"
        if token == "contact_add":
            public_id = self._input_box(stdscr, "Add contact", "Public ID (npub):")
            if public_id is None:
                return None
            nickname = self._input_box(stdscr, "Add contact", "Save as name:")
            if nickname is None:
                return None
            self.result = MenuAction("add", {"public_id": public_id, "name": nickname})
            return "done"
        if token == "contact_remove":
            nickname = self._input_box(stdscr, "Remove contact", "Nickname:")
            if nickname is None:
                return None
            self.result = MenuAction("remove", {"nickname": nickname})
            return "done"
        if token == "chat_open_manual":
            target = self._input_box(stdscr, "Open chat", "Nickname or npub:")
            if target is None:
                return None
            password = self._input_box(stdscr, "Open chat", "Password:", password=True)
            if password is None:
                return None
            self.result = MenuAction("chat", {"target": target, "password": password, "tor": None, "store_history": None})
            return "done"
        if token == "ghost_open_manual":
            target = self._input_box(stdscr, "Ghost chat", "Nickname or npub (blank = passive ghost):", allow_empty=True)
            if target is None:
                return None
            self.result = MenuAction("ghost", {"target": target or None, "tor": None})
            return "done"
        if token == "relay_add":
            url = self._input_box(stdscr, "Add relay", "Relay URL:")
            if url is None:
                return None
            self.result = MenuAction("relay_add", {"url": url})
            return "done"
        if token == "relay_remove":
            url = self._input_box(stdscr, "Remove relay", "Relay URL:")
            if url is None:
                return None
            self.result = MenuAction("relay_remove", {"url": url})
            return "done"
        return None

    def _navigate(self, stdscr, title: str, items: list[tuple[str, Any]]):
        selected = 0
        while True:
            self._draw_menu(stdscr, title, items, selected)
            ch = stdscr.getch()
            if ch == curses.KEY_UP:
                selected = (selected - 1) % len(items)
            elif ch == curses.KEY_DOWN:
                selected = (selected + 1) % len(items)
            elif ch == 27:
                return None
            elif ch in (10, 13, curses.KEY_ENTER):
                label, payload = items[selected]
                if callable(payload):
                    result = self._navigate(stdscr, label, payload())
                    if result == "done":
                        return "done"
                else:
                    result = self._handle_leaf(stdscr, payload)
                    if result == "done":
                        return "done"
                    if result == "back":
                        return None

    def run(self) -> MenuAction | None:
        def _wrapped(stdscr):
            self._setup_colors()
            stdscr.keypad(True)
            self._navigate(stdscr, "Main Menu", self._root_items())

        curses.wrapper(_wrapped)
        return self.result


def run_selection_menu() -> MenuAction | None:
    return HypochatMenu().run()
