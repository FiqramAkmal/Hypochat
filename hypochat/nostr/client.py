import asyncio
from datetime import timedelta
import os
from nostr_sdk import (
    Client, Filter, HandleNotification, Keys, Kind, NostrSigner, PublicKey, RelayUrl, Timestamp
)
from hypochat.core.constants import GIFT_WRAP_KIND
from hypochat.core.crypto import (
    build_handshake_init_plaintext,
    build_prekey_bundle_plaintext,
    build_session_announce_plaintext,
    generate_session_key,
    generate_prekey_bundle,
    open_handshake_init_plaintext,
    open_hypochat_payload,
    open_session_message_payload,
    parse_handshake_init_plaintext,
    parse_prekey_bundle_plaintext,
    parse_session_control_plaintext,
    parse_session_message_payload,
    seal_hypochat_payload,
    seal_session_message_payload,
)
from hypochat.nostr.relays import get_relays
from hypochat.storage.peer_state_store import get_last_seen, has_seen_event, mark_peer_event
from hypochat.storage.session_store import (
    clear_outgoing_session,
    get_prekey_bundle,
    has_seen_handshake,
    mark_seen_handshake,
    get_incoming_session_by_id,
    get_outgoing_session,
    get_pending_outgoing,
    pop_pending_outgoing,
    rotate_outgoing_session,
    set_prekey_bundle,
    set_incoming_session,
    touch_incoming_session,
    enqueue_pending_outgoing,
)


class PrivateMessageHandler(HandleNotification):
    def __init__(self, owner, client: Client, peer_npub: str, callback, receiver_nsec: str, persist_peer_state: bool = True):
        self.owner = owner
        self.client = client
        self.peer_npub = peer_npub
        self.callback = callback
        self._receiver_nsec = receiver_nsec
        self._self_npub = Keys.parse(receiver_nsec).public_key().to_bech32()
        self.persist_peer_state = persist_peer_state
        self._buffered_session_events: dict[str, list[tuple[str, str, int]]] = {}

    async def _handle_event(self, event):
        processed = await self.extract_processed_event(event)
        if processed is None:
            return None
        event_id, _sender, content, created_at = processed
        mark_peer_event(self.peer_npub, event_id, created_at, persist=self.persist_peer_state)
        await self.callback(content, created_at)
        return None

    def _buffer_session_event(self, session_id: str, event_id: str, payload: str, created_at: int):
        pending = self._buffered_session_events.setdefault(session_id, [])
        pending.append((event_id, payload, created_at))

    async def _drain_buffered_session_events(self, session_id: str):
        pending = self._buffered_session_events.pop(session_id, [])
        if not pending:
            return
        session = get_incoming_session_by_id(self.peer_npub, session_id)
        if session is None:
            return
        for event_id, payload, created_at in sorted(pending, key=lambda item: (item[2], item[0])):
            if has_seen_event(self.peer_npub, event_id):
                continue
            content = open_session_message_payload(session["key"], payload)
            touch_incoming_session(self.peer_npub, session_id)
            mark_peer_event(self.peer_npub, event_id, created_at, persist=self.persist_peer_state)
            await self.callback(content, created_at)

    async def extract_processed_event(self, event):
        event_id = event.id().to_hex()
        if has_seen_event(self.peer_npub, event_id):
            return None
        if event.kind().as_u16() != GIFT_WRAP_KIND:
            return None

        unwrapped = await self.client.unwrap_gift_wrap(event)
        sender = unwrapped.sender().to_bech32()
        if sender != self.peer_npub:
            return None

        rumor = unwrapped.rumor()
        created_at = rumor.created_at().as_secs()
        rumor_content = rumor.content()

        session_payload = parse_session_message_payload(rumor_content)
        if session_payload is not None:
            session = get_incoming_session_by_id(self.peer_npub, session_payload["sid"])
            if session is None:
                self._buffer_session_event(session_payload["sid"], event_id, rumor_content, created_at)
                return None
            content = open_session_message_payload(session["key"], rumor_content)
            touch_incoming_session(self.peer_npub, session_payload["sid"])
            return event_id, sender, content, created_at

        content = open_hypochat_payload(self._receiver_nsec, sender, rumor_content)

        prekey_bundle = parse_prekey_bundle_plaintext(content)
        if prekey_bundle is not None:
            set_prekey_bundle(self.peer_npub, prekey_bundle)
            if prekey_bundle.get("request_reply"):
                local_bundle = await self.owner._ensure_local_prekey_bundle()
                recipient_pk = PublicKey.parse(self.peer_npub)
                await self.client.send_private_msg(recipient_pk, seal_hypochat_payload(self._receiver_nsec, self.peer_npub, build_prekey_bundle_plaintext(local_bundle, request_reply=False)))
            await self.owner._flush_pending_outgoing(self.peer_npub)
            return None

        handshake_init = parse_handshake_init_plaintext(content)
        if handshake_init is not None:
            local_bundle = get_prekey_bundle(self._self_npub)
            if local_bundle is None:
                local_bundle = generate_prekey_bundle()
                set_prekey_bundle(self._self_npub, local_bundle)
            if has_seen_handshake(self.peer_npub, handshake_init["hid"]):
                return None
            opened = open_handshake_init_plaintext(local_bundle, content)
            set_incoming_session(self.peer_npub, opened["session_id"], opened["session_key"])
            mark_seen_handshake(self.peer_npub, opened["handshake_id"])
            await self._drain_buffered_session_events(opened["session_id"])
            return None

        session_control = parse_session_control_plaintext(content)
        if session_control is not None:
            set_incoming_session(self.peer_npub, session_control["sid"], session_control["key"])
            await self._drain_buffered_session_events(session_control["sid"])
            return None

        return event_id, sender, content, created_at

    async def handle_msg(self, relay_url, msg):
        return None

    async def handle(self, relay_url, subscription_id, event):
        try:
            await self._handle_event(event)
        except Exception:
            return None

class NostrClient:
    def __init__(self, nsec: str, use_tor: bool = False, tor_proxy: str | None = None, persist_peer_state: bool = True):
        self.keys = Keys.parse(nsec)
        self.nsec = nsec
        self.npub = self.keys.public_key().to_bech32()
        self.use_tor = use_tor
        self.tor_proxy = tor_proxy
        self.persist_peer_state = persist_peer_state
        signer = NostrSigner.keys(self.keys)
        self.client = Client(signer)
        self._flush_locks: dict[str, asyncio.Lock] = {}

    def _apply_tor_env(self):
        if self.use_tor and self.tor_proxy:
            os.environ.setdefault("ALL_PROXY", self.tor_proxy)
            os.environ.setdefault("all_proxy", self.tor_proxy)

    async def connect(self):
        self._apply_tor_env()
        await self._ensure_local_prekey_bundle()
        for relay in get_relays():
            await self.client.add_relay(RelayUrl.parse(relay))
        await self.client.connect()
        await self.client.wait_for_connection(timedelta(seconds=10))

    async def disconnect(self):
        await self.client.disconnect()

    async def reset_session_context(self, peer_npub: str):
        clear_outgoing_session(peer_npub)
        await self._ensure_local_prekey_bundle()

    async def _ensure_local_prekey_bundle(self):
        bundle = get_prekey_bundle(self.npub)
        if bundle is None:
            bundle = generate_prekey_bundle()
            set_prekey_bundle(self.npub, bundle)
        return bundle

    async def _publish_local_prekey_bundle(self, recipient_npub: str, recipient_pk, request_reply: bool):
        local_bundle = await self._ensure_local_prekey_bundle()
        payload = build_prekey_bundle_plaintext(local_bundle, request_reply=request_reply)
        await self.client.send_private_msg(recipient_pk, seal_hypochat_payload(self.nsec, recipient_npub, payload))

    async def _ensure_peer_prekey_bundle(self, recipient_npub: str, recipient_pk):
        peer_bundle = get_prekey_bundle(recipient_npub)
        if peer_bundle is not None:
            return peer_bundle
        await self._publish_local_prekey_bundle(recipient_npub, recipient_pk, request_reply=True)
        return None

    async def _flush_pending_outgoing(self, recipient_npub: str) -> int:
        lock = self._flush_locks.setdefault(recipient_npub, asyncio.Lock())
        async with lock:
            pending = pop_pending_outgoing(recipient_npub)
            if not pending:
                return 0
            delivered = 0
            for index, plaintext in enumerate(pending):
                status = await self.send_dm(recipient_npub, plaintext)
                if status != "sent":
                    for unsent in pending[index:]:
                        enqueue_pending_outgoing(recipient_npub, unsent)
                    break
                delivered += 1
            return delivered

    async def send_dm(self, recipient_npub: str, plaintext: str) -> str:
        recipient_pk = PublicKey.parse(recipient_npub)
        session = get_outgoing_session(recipient_npub)
        if session is None:
            peer_bundle = await self._ensure_peer_prekey_bundle(recipient_npub, recipient_pk)
            if peer_bundle is None:
                enqueue_pending_outgoing(recipient_npub, plaintext)
                return "queued"
            session = rotate_outgoing_session(recipient_npub, generate_session_key())
            handshake_init = build_handshake_init_plaintext(peer_bundle, session["session_id"], session["key"])
            await self.client.send_private_msg(recipient_pk, seal_hypochat_payload(self.nsec, recipient_npub, handshake_init))
        payload = seal_session_message_payload(session["session_id"], session["key"], plaintext)
        await self.client.send_private_msg(recipient_pk, payload)
        return "sent"

    async def sync_backlog(self, peer_npub: str, callback):
        my_pk = self.keys.public_key()
        last_seen = get_last_seen(peer_npub) if self.persist_peer_state else 0
        filter_query = Filter().kinds([Kind(GIFT_WRAP_KIND)]).pubkey(my_pk).limit(200)
        if last_seen > 0:
            filter_query = filter_query.since(Timestamp.from_secs(last_seen))

        events = await self.client.fetch_events(filter_query, timedelta(seconds=10))
        handler = PrivateMessageHandler(self, self.client, peer_npub, callback, receiver_nsec=self.nsec, persist_peer_state=self.persist_peer_state)
        processed_events = []
        for event in events.to_vec():
            try:
                processed = await handler.extract_processed_event(event)
                if processed is not None:
                    processed_events.append(processed)
            except Exception:
                continue
        for event_id, _sender, content, created_at in sorted(processed_events, key=lambda item: (item[3], item[0])):
            mark_peer_event(peer_npub, event_id, created_at, persist=self.persist_peer_state)
            result = callback(content, created_at)
            if asyncio.iscoroutine(result):
                await result

    async def listen_dm(self, peer_npub: str, callback, sync_backlog: bool = True):
        """Listen for gift-wrapped private messages from a specific peer."""
        my_pk = self.keys.public_key()
        if sync_backlog:
            await self.sync_backlog(peer_npub, callback)
        f = Filter().kinds([Kind(GIFT_WRAP_KIND)]).pubkey(my_pk)
        await self.client.subscribe(f, None)
        handler = PrivateMessageHandler(self, self.client, peer_npub, callback, receiver_nsec=self.nsec, persist_peer_state=self.persist_peer_state)
        await self.client.handle_notifications(handler)
