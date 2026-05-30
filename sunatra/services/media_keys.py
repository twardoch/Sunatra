from pynput import keyboard


class MediaKeyHandler:
    def __init__(self, player):
        self.player = player
        self.listener = None
        self.running = False

    def start(self):
        if self.running:
            return
        self.running = True
        # Start the listener in a non-blocking way
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()
        self.running = False

    def on_press(self, key):
        if not self.running:
            return

        try:
            if key == keyboard.Key.media_play_pause:
                self.schedule(self.player.toggle_playback)
            elif key == keyboard.Key.media_next:
                self.schedule(self.player.next_song)
            elif key == keyboard.Key.media_previous:
                self.schedule(self.player.previous_song)
        except AttributeError:
            pass

    def schedule(self, func):
        """Schedule the function to run on the main thread if possible, or just run it if thread-safe enough."""
        # Tkinter/CustomTkinter widgets should nominally be updated from the main thread.
        # Since pynput runs in a separate thread, we use `after` to bridge back to the main loop.
        # Assuming `player` is an instance of PlayerWidget which is a CTkFrame.
        if hasattr(self.player, 'after'):
            self.player.after(0, func)
        else:
            # Fallback if for some reason after isn't available
            func()
