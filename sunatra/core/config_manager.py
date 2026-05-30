import json
import os
import threading
import time

from sunatra.core.app_meta import user_data_dir

# Delay between rapid set() calls and the actual disk write. Keeps slider/typing
# events from rewriting config.json on every keystroke.
_SAVE_DEBOUNCE_SECONDS = 0.5


class ConfigManager:
    def __init__(self, config_filename="config.json"):
        # Canonical Sunatra per-user data directory (see core.app_meta).
        self.data_dir = user_data_dir()

        # Ensure the directory exists
        if not os.path.exists(self.data_dir):
            try:
                os.makedirs(self.data_dir)
            except OSError as e:
                print(f"Error creating config directory: {e}")

        # store full path
        self.config_file = os.path.join(self.data_dir, config_filename)
        self.config = {}
        self._save_timer = None
        self._save_lock = threading.Lock()
        self.load_config()

    def load_config(self):
        if not os.path.exists(self.config_file):
            self.config = {}
            return

        try:
            with open(self.config_file) as f:
                self.config = json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            # Quarantine the corrupt file so the user can recover values manually.
            quarantine = f"{self.config_file}.corrupt-{int(time.time())}"
            try:
                os.replace(self.config_file, quarantine)
                print(f"Config file was corrupt; moved to {quarantine}: {e}")
            except OSError as move_err:
                print(f"Config file was corrupt and could not be quarantined: {move_err}")
            self.config = {}
        except OSError as e:
            print(f"Error reading config file: {e}")
            self.config = {}

    def save_config(self):
        # Cancel any pending debounced save — we're writing now.
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None

        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except OSError as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self._schedule_save()

    def _schedule_save(self):
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
            timer = threading.Timer(_SAVE_DEBOUNCE_SECONDS, self.save_config)
            timer.daemon = True
            self._save_timer = timer
            timer.start()

    def flush(self):
        """Force any pending debounced save to disk now."""
        with self._save_lock:
            timer = self._save_timer
            self._save_timer = None
        if timer is not None:
            timer.cancel()
        self.save_config()

    def get_data_dir(self):
        """Return the directory where data should be stored"""
        return self.data_dir
