import time

from pypresence import Presence


class DiscordRPC:
    def __init__(self, client_id='1451837816131686472'):
        self.client_id = client_id
        self.rpc = None
        self.connected = False
        self.connect()

    def connect(self):
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.connected = True
            print(f"Discord RPC Connected! Client ID: {self.client_id}")
        except Exception as e:
            print(f"Discord RPC failed to connect (is Discord running?): {e}")
            self.connected = False

    def update_presence(self, track_title, artist, duration=None, current_time=None, is_paused=False):
        if not self.connected:
            self.connect()
            if not self.connected:
                 return

        try:
            # Ensure strings are valid and at least 2 chars (Discord requirement)
            track_title = str(track_title)
            if len(track_title) < 2:
                track_title += " "

            artist_str = f"by {artist}" if artist else "Unknown Artist"
            if len(artist_str) < 2:
                artist_str += " "

            if is_paused:
                self.rpc.update(
                    details=track_title,
                    state="Paused",
                    large_image="suno_logo",
                    small_image="pause",
                    small_text="Paused"
                )
            else:
                # Calculate end time for countdown
                end = None
                if duration and current_time is not None:
                     # Discord expects end timestamp
                     remaining = duration - current_time
                     end = time.time() + remaining

                self.rpc.update(
                    details=track_title,
                    state=artist_str,
                    end=end,
                    large_image="suno_logo",
                    large_text="Sunatra",
                    small_image="play",
                    small_text="Playing"
                )
        except Exception as e:
            print(f"Failed to update Discord status: {e}")
            # Do not set self.connected = False immediately on update error,
            # maybe it's just a payload issue.
            # But if it's a pipe error, it will fail next time too.
            if "Pipe" in str(e) or "Connection" in str(e):
                 self.connected = False

    def clear(self):
        if self.connected and self.rpc:
            try:
                self.rpc.clear()
            except:
                pass

    def close(self):
        if self.connected and self.rpc:
            try:
                self.rpc.close()
            except:
                pass
            self.connected = False
