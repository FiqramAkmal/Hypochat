import sys

from hypochat.cli import app
from hypochat.core.tor import TorManager
from hypochat.menu import run_selection_menu
from hypochat.storage.config_store import load_config


def _start_launcher_tor() -> TorManager | None:
    config = load_config()
    if not config.get("use_tor", True):
        return None
    manager = TorManager(config.get("tor_proxy", "socks5://127.0.0.1:9050"))
    manager.start()
    return manager


def main():
    if len(sys.argv) == 1:
        manager = _start_launcher_tor()
        try:
            action = run_selection_menu()
            if action is None:
                return
            from hypochat import app as command_app
            dispatch = {
                'init': lambda a: command_app.cmd_init(a.kwargs.get('password')),
                'id': lambda a: command_app.cmd_id(a.kwargs.get('password')),
                'export': lambda a: command_app.cmd_export(a.kwargs.get('password')),
                'import': lambda a: command_app.cmd_import(a.kwargs['nsec'], a.kwargs.get('password')),
                'add': lambda a: command_app.cmd_add(a.kwargs['public_id'], a.kwargs['name']),
                'contacts': lambda a: command_app.cmd_contacts(),
                'doctor': lambda a: command_app.cmd_doctor(a.kwargs.get('password')),
                'remove': lambda a: command_app.cmd_remove(a.kwargs['nickname']),
                'chat': lambda a: command_app.cmd_chat(a.kwargs['target'], a.kwargs.get('password'), a.kwargs.get('tor'), a.kwargs.get('store_history')),
                'ghost': lambda a: command_app.cmd_ghost(a.kwargs.get('target'), a.kwargs.get('tor')),
                'relay_list': lambda a: command_app.cmd_relay_list(),
                'relay_add': lambda a: command_app.cmd_relay_add(a.kwargs['url']),
                'relay_remove': lambda a: command_app.cmd_relay_remove(a.kwargs['url']),
                'privacy_set': lambda a: command_app.cmd_set_privacy(a.kwargs.get('use_tor'), a.kwargs.get('store_history'), a.kwargs.get('tor_proxy'), a.kwargs.get('privacy_mode')),
                'version': lambda a: app(['version']),
            }
            handler = dispatch.get(action.name)
            if handler is not None:
                handler(action)
            return
        finally:
            if manager is not None:
                manager.stop()
    app()


if __name__ == '__main__':
    main()
