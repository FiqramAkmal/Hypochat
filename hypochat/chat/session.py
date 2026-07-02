import asyncio
import curses
import textwrap
from datetime import datetime
from typing import Callable

from hypochat.nostr.client import NostrClient
from hypochat.storage.transcript_store import append_transcript_message, load_transcript
from hypochat.ui.console import err

CHAT_HELP = [
    "/exit  quit chat",
    "/clear clear conversation view",
    "/id    show your Public ID",
    "/help  show this help",
]


class ChatSession:
    def __init__(
        self,
        nostr_client: NostrClient,
        peer_nickname: str,
        peer_npub: str,
        my_npub: str,
        store_history: bool = False,
        persist_transcript: bool = True,
        header_status_provider: Callable[[], list[str]] | None = None,
    ):
        self.client = nostr_client
        self.peer_nickname = peer_nickname
        self.peer_npub = peer_npub
        self.my_npub = my_npub
        self.store_history = store_history
        self.persist_transcript = persist_transcript
        self.header_status_provider = header_status_provider
        self.running = True
        self.rendered_cache_keys: set[tuple[str, int, str]] = set()
        self.messages: list[dict] = []
        self.pending_incoming: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
        self.status_message = ""
        self.scroll_offset = 0
        self.colors_enabled = False
        self.render_cache_width: int | None = None
        self.render_cache_lines: list[tuple[list[tuple[str, int]], bool]] = []
        self.render_cache_dirty = True
        self.pending_status_events: asyncio.Queue[str] = asyncio.Queue()

    def _setup_colors(self):
        if curses.has_colors():
            curses.start_color()
            try:
                curses.use_default_colors()
            except Exception:
                pass
            curses.init_pair(1, curses.COLOR_CYAN, -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)
            curses.init_pair(3, curses.COLOR_WHITE, -1)
            curses.init_pair(4, curses.COLOR_YELLOW, -1)
            curses.init_pair(5, curses.COLOR_BLACK, -1)
            curses.init_pair(6, curses.COLOR_WHITE, -1)
            self.colors_enabled = True

    def _color(self, pair_id: int, extra: int = 0) -> int:
        if not self.colors_enabled:
            return extra
        return curses.color_pair(pair_id) | extra

    def _format_time(self, ts: int | None) -> str:
        if ts:
            dt = datetime.fromtimestamp(ts).astimezone()
        else:
            dt = datetime.now().astimezone()
        return dt.strftime("%H:%M:%S")

    def _message_key(self, sender: str, text: str, ts: int) -> tuple[str, int, str]:
        return sender, int(ts or 0), text

    def _append_message(self, sender: str, text: str, ts: int | None, persist_to_store: bool = True) -> bool:
        timestamp = int(ts or datetime.now().astimezone().timestamp())
        cache_key = self._message_key(sender, text, timestamp)
        if cache_key in self.rendered_cache_keys:
            return False

        self.rendered_cache_keys.add(cache_key)
        self.render_cache_dirty = True
        self.messages.append(
            {"sender": sender, "text": text, "timestamp": timestamp}
        )
        self.messages.sort(
            key=lambda item: (
                int(item.get("timestamp", 0)),
                item.get("sender", ""),
                item.get("text", ""),
            )
        )
        if persist_to_store and self.persist_transcript and sender != "system":
            append_transcript_message(self.peer_npub, sender, text, timestamp)
        return True

    def cache_incoming_message(self, text: str, ts: int):
        return self._append_message(self.peer_nickname, text, ts)

    async def queue_incoming_message(self, text: str, ts: int):
        await self.pending_incoming.put((text, ts))

    def _load_transcript(self):
        if not self.persist_transcript:
            self.rendered_cache_keys.clear()
            self.messages = []
            return
        self.rendered_cache_keys.clear()
        self.messages = []
        for item in load_transcript(self.peer_npub):
            sender = item.get("sender", self.peer_nickname)
            text = item.get("text", "")
            ts = int(item.get("timestamp", 0) or 0)
            self._append_message(sender, text, ts, persist_to_store=False)

    def _banner_lines(self, width: int) -> list[tuple[str, int]]:
        title = " H Y P O C H A T CLI ".center(max(1, width))[:width]
        subtitle = f" chatting with {self.peer_nickname} ".center(max(1, width))[:width]
        dynamic_lines = self.header_status_provider() if self.header_status_provider else []
        while len(dynamic_lines) < 2:
            dynamic_lines.append("")
        status1 = dynamic_lines[0].center(max(1, width))[:width]
        status2 = (self.status_message or dynamic_lines[1] or " /help commands | PgUp/PgDn scroll ").center(max(1, width))[:width]
        return [
            (title, self._color(1, curses.A_BOLD)),
            (subtitle, self._color(3, curses.A_BOLD)),
            (status1, self._color(4)),
            (status2, self._color(4)),
        ]

    def _segment_width(self, segments: list[tuple[str, int]]) -> int:
        return sum(len(text) for text, _ in segments)

    def _wrap_incoming(self, sender: str, text: str, time_str: str, width: int) -> list[list[tuple[str, int]]]:
        prefix = f"[{time_str}] "
        middle = f"{sender}"
        separator = " > "
        prefix_len = len(prefix) + len(middle) + len(separator)
        text_width = max(8, width - prefix_len)
        wrapped = textwrap.wrap(text, width=text_width) or [""]
        lines = []
        lines.append([
            (prefix, self._color(6)),
            (middle, self._color(1, curses.A_BOLD)),
            (separator, 0),
            (wrapped[0], 0),
        ])
        indent = " " * prefix_len
        for chunk in wrapped[1:]:
            lines.append([(indent, 0), (chunk, 0)])
        return lines

    def _wrap_outgoing(self, text: str, time_str: str, width: int) -> list[list[tuple[str, int]]]:
        suffix_plain = " < "
        you_text = "you"
        time_text = f" [{time_str}]"
        suffix_len = len(suffix_plain) + len(you_text) + len(time_text)
        text_width = max(8, width - suffix_len)
        wrapped = textwrap.wrap(text, width=text_width) or [""]
        lines = []
        for index, chunk in enumerate(wrapped):
            if index == len(wrapped) - 1:
                segments = [
                    (chunk, 0),
                    (suffix_plain, 0),
                    (you_text, self._color(2, curses.A_BOLD)),
                    (time_text, self._color(6)),
                ]
            else:
                segments = [(chunk, 0)]
            lines.append(segments)
        return lines

    def _render_message_lines(self, width: int) -> list[tuple[list[tuple[str, int]], bool]]:
        if not self.render_cache_dirty and self.render_cache_width == width:
            return self.render_cache_lines

        rendered: list[tuple[list[tuple[str, int]], bool]] = []
        content_width = max(20, width - 1)
        for item in self.messages:
            sender = item["sender"]
            text = item["text"]
            ts = int(item["timestamp"])
            time_str = self._format_time(ts)
            if sender == "you":
                for segments in self._wrap_outgoing(text, time_str, content_width):
                    rendered.append((segments, True))
            elif sender == "system":
                wrapped = textwrap.wrap(text, width=content_width) or [text]
                for chunk in wrapped:
                    rendered.append(([(chunk, self._color(4))], False))
            else:
                for segments in self._wrap_incoming(sender, text, time_str, content_width):
                    rendered.append((segments, False))
        self.render_cache_width = width
        self.render_cache_lines = rendered
        self.render_cache_dirty = False
        return rendered

    def _draw_header(self, stdscr, width: int):
        for row, (line, attr) in enumerate(self._banner_lines(width)):
            try:
                stdscr.addnstr(row, 0, line.ljust(max(1, width - 1)), max(1, width - 1), attr)
            except curses.error:
                pass

    def _draw_segments(self, stdscr, row: int, width: int, segments: list[tuple[str, int]], align_right: bool):
        total_width = self._segment_width(segments)
        usable_width = max(1, width - 1)
        col = max(0, usable_width - total_width) if align_right else 0
        for text, attr in segments:
            available = max(0, usable_width - col)
            if available <= 0:
                break
            try:
                stdscr.addnstr(row, col, text, available, attr)
            except curses.error:
                pass
            col += min(len(text), available)

    def _draw_conversation(self, stdscr, start_row: int, height: int, width: int):
        rendered = self._render_message_lines(width)
        max_scroll = max(0, len(rendered) - height)
        self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
        start_index = max(0, len(rendered) - height - self.scroll_offset)
        visible = rendered[start_index:start_index + height]

        row = start_row
        for segments, align_right in visible:
            try:
                stdscr.addnstr(row, 0, " " * max(0, width - 1), max(0, width - 1))
            except curses.error:
                pass
            self._draw_segments(stdscr, row, width, segments, align_right)
            row += 1
        while row < start_row + height:
            try:
                stdscr.addnstr(row, 0, " " * max(0, width - 1), max(0, width - 1))
            except curses.error:
                pass
            row += 1

    def _draw_input_box(self, stdscr, input_buffer: str, cursor_index: int, height: int, width: int):
        box_top = height - 3
        usable_width = max(4, width - 1)
        inner_width = max(1, usable_width - 2)
        title = " Message "
        top = "╭" + title + ("─" * max(0, inner_width - len(title))) + "╮"
        visible_capacity = max(1, inner_width - 1)
        window_start = max(0, cursor_index - visible_capacity)
        window_end = max(cursor_index, window_start + visible_capacity)
        visible_text = input_buffer[window_start:window_end][-visible_capacity:]
        relative_cursor = max(0, min(len(visible_text), cursor_index - window_start))
        middle = "│ " + visible_text.ljust(max(0, inner_width - 1)) + "│"
        bottom = "╰" + ("─" * inner_width) + "╯"
        try:
            stdscr.addnstr(box_top, 0, top[:usable_width], usable_width)
            stdscr.addnstr(box_top + 1, 0, middle[:usable_width], usable_width)
            stdscr.addnstr(box_top + 2, 0, bottom[:usable_width], usable_width)
        except curses.error:
            pass
        cursor_x = min(usable_width - 2, 2 + relative_cursor)
        try:
            stdscr.move(box_top + 1, max(2, cursor_x))
        except curses.error:
            pass

    def _draw(self, stdscr, input_buffer: str, cursor_index: int):
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        if height < 8 or width < 40:
            stdscr.addnstr(0, 0, "Terminal too small. Resize to continue.", max(0, width - 1))
            stdscr.refresh()
            return
        self._draw_header(stdscr, width)
        conversation_start = 5
        conversation_height = max(1, height - conversation_start - 4)
        self._draw_conversation(stdscr, conversation_start, conversation_height, width)
        self._draw_input_box(stdscr, input_buffer, cursor_index, height, width)
        stdscr.refresh()

    def _draw_input_only(self, stdscr, input_buffer: str, cursor_index: int):
        height, width = stdscr.getmaxyx()
        if height < 8 or width < 40:
            self._draw(stdscr, input_buffer, cursor_index)
            return
        self._draw_input_box(stdscr, input_buffer, cursor_index, height, width)
        stdscr.refresh()

    async def _send_outgoing(self, text: str):
        try:
            status = await self.client.send_dm(self.peer_npub, text)
            if status == "queued":
                await self.pending_status_events.put("waiting for peer prekey sync...")
            else:
                await self.pending_status_events.put("")
        except Exception as exc:
            await self.pending_status_events.put(f"send failed: {exc}")

    async def _run_curses_loop(self, stdscr):
        curses.noecho()
        curses.cbreak()
        try:
            curses.curs_set(1)
        except Exception:
            pass
        stdscr.keypad(True)
        stdscr.nodelay(True)
        self._setup_colors()

        input_buffer = ""
        cursor_index = 0
        self._draw(stdscr, input_buffer, cursor_index)

        while self.running:
            updated = False
            input_only_update = False
            while not self.pending_incoming.empty():
                text, ts = await self.pending_incoming.get()
                if self._append_message(self.peer_nickname, text, ts):
                    self.scroll_offset = 0
                    updated = True
                    input_only_update = False

            while not self.pending_status_events.empty():
                self.status_message = await self.pending_status_events.get()
                updated = True
                input_only_update = False

            ch = stdscr.getch()
            if ch == curses.KEY_RESIZE:
                updated = True
                input_only_update = False
            elif ch == curses.KEY_PPAGE:
                self.scroll_offset += 5
                updated = True
                input_only_update = False
            elif ch == curses.KEY_NPAGE:
                self.scroll_offset = max(0, self.scroll_offset - 5)
                updated = True
                input_only_update = False
            elif ch == curses.KEY_UP:
                self.scroll_offset += 1
                updated = True
                input_only_update = False
            elif ch == curses.KEY_DOWN:
                self.scroll_offset = max(0, self.scroll_offset - 1)
                updated = True
                input_only_update = False
            elif ch in (10, 13, curses.KEY_ENTER):
                text = input_buffer.strip()
                input_buffer = ""
                if text == "/exit":
                    self.running = False
                    updated = True
                    input_only_update = False
                elif text == "/clear":
                    self.messages = []
                    self.rendered_cache_keys.clear()
                    self.render_cache_dirty = True
                    self.status_message = "conversation cleared"
                    updated = True
                    input_only_update = False
                elif text == "/id":
                    self.status_message = self.my_npub
                    updated = True
                    input_only_update = False
                elif text == "/help":
                    now_ts = int(datetime.now().astimezone().timestamp())
                    for idx, help_line in enumerate(CHAT_HELP):
                        self._append_message("system", help_line, now_ts + idx)
                    updated = True
                    input_only_update = False
                elif text:
                    timestamp = int(datetime.now().astimezone().timestamp())
                    self._append_message("you", text, timestamp)
                    self.status_message = "sending..."
                    self.scroll_offset = 0
                    asyncio.create_task(self._send_outgoing(text))
                    updated = True
                    input_only_update = False
                cursor_index = 0
            elif ch in (curses.KEY_BACKSPACE, 127, 8):
                if cursor_index > 0:
                    input_buffer = input_buffer[:cursor_index - 1] + input_buffer[cursor_index:]
                    cursor_index -= 1
                    updated = True
                    input_only_update = True
            elif ch == curses.KEY_DC:
                if cursor_index < len(input_buffer):
                    input_buffer = input_buffer[:cursor_index] + input_buffer[cursor_index + 1:]
                    updated = True
                    input_only_update = True
            elif ch == curses.KEY_LEFT:
                cursor_index = max(0, cursor_index - 1)
                updated = True
                input_only_update = True
            elif ch == curses.KEY_RIGHT:
                cursor_index = min(len(input_buffer), cursor_index + 1)
                updated = True
                input_only_update = True
            elif ch == curses.KEY_HOME:
                cursor_index = 0
                updated = True
                input_only_update = True
            elif ch == curses.KEY_END:
                cursor_index = len(input_buffer)
                updated = True
                input_only_update = True
            elif ch == -1:
                pass
            elif 32 <= ch <= 126:
                input_buffer = input_buffer[:cursor_index] + chr(ch) + input_buffer[cursor_index:]
                cursor_index += 1
                updated = True
                input_only_update = True

            if updated:
                if input_only_update:
                    self._draw_input_only(stdscr, input_buffer, cursor_index)
                else:
                    self._draw(stdscr, input_buffer, cursor_index)
                await asyncio.sleep(0)
            else:
                await asyncio.sleep(0.002)

    async def run(self):
        await self.client.sync_backlog(self.peer_npub, self.cache_incoming_message)
        self._load_transcript()
        listen_task = asyncio.create_task(
            self.client.listen_dm(self.peer_npub, self.queue_incoming_message, sync_backlog=False)
        )
        stdscr = curses.initscr()
        listen_exception = None
        try:
            await self._run_curses_loop(stdscr)
        finally:
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                listen_exception = exc
            try:
                stdscr.keypad(False)
            except Exception:
                pass
            for mode in (curses.nocbreak, curses.echo, curses.endwin):
                try:
                    mode()
                except Exception:
                    pass
        if listen_exception is not None:
            err(f"Chat session error: {listen_exception}")
