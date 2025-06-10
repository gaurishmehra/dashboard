import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, GdkPixbuf, Gio, Gdk
import cairo
import subprocess
import os
import tempfile
import math
import threading
import queue
import warnings
import urllib.request

# Suppress the deprecation warning for pixbuf_get_from_surface, which is fine for now.
warnings.filterwarnings("ignore", ".*pixbuf_get_from_surface.*", DeprecationWarning)

class CircularProgressWidget(Gtk.DrawingArea):
    """
    A circular progress widget that is also a seek bar.
    Refinements:
    - Better hover feedback.
    - More robust click detection.
    """
    def __init__(self):
        super().__init__()
        self.set_size_request(220, 220)
        self.progress = 0.0
        self.set_draw_func(self.draw_progress)
        
        # Gesture for clicking to seek
        gesture_click = Gtk.GestureClick()
        gesture_click.connect("pressed", self.on_click)
        self.add_controller(gesture_click)
        
        # Motion controller for hover effects and setting the cursor
        motion_controller = Gtk.EventControllerMotion()
        motion_controller.connect("enter", self.on_enter)
        motion_controller.connect("leave", self.on_leave)
        self.add_controller(motion_controller)
        
        self.seek_callback = None
        self.is_hovering = False
    
    def set_progress(self, progress):
        self.progress = max(0.0, min(1.0, progress))
        self.queue_draw()
    
    def set_seek_callback(self, callback):
        self.seek_callback = callback
    
    def on_enter(self, controller, x, y):
        self.is_hovering = True
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        self.queue_draw()

    def on_leave(self, controller):
        self.is_hovering = False
        self.set_cursor(None)
        self.queue_draw()
    
    def on_click(self, gesture, n_press, x, y):
        if not self.seek_callback:
            return
            
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        center_x, center_y = width / 2, height / 2
        
        # Calculate angle from click position relative to the center
        dx, dy = x - center_x, y - center_y
        angle = math.atan2(dy, dx)
        
        # Convert angle to progress (0-1). We shift by PI/2 because 0 radians is 'right'
        # and we want 'up' to be the start of the circle.
        progress = (angle + math.pi / 2) / (2 * math.pi)
        if progress < 0:
            progress += 1.0
            
        progress = max(0.0, min(1.0, progress))
        self.seek_callback(progress)
    
    def draw_progress(self, area, cr, width, height, user_data=None):
        center_x, center_y = width / 2, height / 2
        radius = min(width, height) / 2 - 10
        line_width = 8 if self.is_hovering else 5

        # Background track
        cr.set_source_rgba(1, 1, 1, 0.1)
        cr.set_line_width(line_width)
        cr.arc(center_x, center_y, radius, 0, 2 * math.pi)
        cr.stroke()
        
        # Progress arc
        if self.progress > 0:
            cr.set_source_rgba(1, 1, 1, 0.9)
            cr.set_line_width(line_width)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            start_angle = -math.pi / 2  # Start from the top
            end_angle = start_angle + (2 * math.pi * self.progress)
            cr.arc(center_x, center_y, radius, start_angle, end_angle)
            cr.stroke()

class CircularImage(Gtk.DrawingArea):
    """
    A widget to display a circular image.
    Refinements:
    - Now handles its own threading for loading from a URL.
    - More robust error handling.
    """
    def __init__(self, size=180):
        super().__init__()
        self.size = size
        self.set_size_request(size, size)
        self.set_draw_func(self.draw_circular_image)
        self.pixbuf = None
        self.is_default_icon = True
        self.set_default_icon()
        
    def _set_pixbuf_on_main_thread(self, pixbuf):
        """Helper to safely update pixbuf from a background thread."""
        if pixbuf:
            self.pixbuf = self.create_circular_pixbuf(pixbuf)
            self.is_default_icon = False
        else:
            self.set_default_icon()
        self.queue_draw()
        return GLib.SOURCE_REMOVE

    def set_from_file(self, file_path):
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_path)
            self._set_pixbuf_on_main_thread(pixbuf)
        except GLib.Error as e:
            print(f"Error loading image from file '{file_path}': {e}")
            self._set_pixbuf_on_main_thread(None)
            
    def _load_url_thread(self, url):
        """Worker function to download an image in a background thread."""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                urllib.request.urlretrieve(url, tmp_file.name)
                pixbuf = GdkPixbuf.Pixbuf.new_from_file(tmp_file.name)
                GLib.idle_add(self._set_pixbuf_on_main_thread, pixbuf)
                os.unlink(tmp_file.name)
        except Exception as e:
            print(f"Error downloading or processing image from URL '{url}': {e}")
            GLib.idle_add(self._set_pixbuf_on_main_thread, None)

    def set_from_url(self, url):
        """Asynchronously loads an image from a URL without blocking the UI."""
        thread = threading.Thread(target=self._load_url_thread, args=(url,))
        thread.daemon = True
        thread.start()
        
    def set_default_icon(self):
        self.pixbuf = None
        self.is_default_icon = True
        self.queue_draw()
        
    def create_circular_pixbuf(self, original_pixbuf):
        size = self.size
        # Center-crop to a square
        width, height = original_pixbuf.get_width(), original_pixbuf.get_height()
        min_dim = min(width, height)
        sub_pixbuf = original_pixbuf.new_subpixbuf((width - min_dim) // 2, (height - min_dim) // 2, min_dim, min_dim)
        
        # Scale to the target size
        scaled_pixbuf = sub_pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
        
        # Create a circular mask
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surface)
        ctx.arc(size/2, size/2, size/2, 0, 2 * math.pi)
        ctx.clip()
        Gdk.cairo_set_source_pixbuf(ctx, scaled_pixbuf, 0, 0)
        ctx.paint()
        
        return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)
        
# In media_player.py, inside the CircularImage class:

    def draw_circular_image(self, area, cr, width, height, user_data=None):
        if self.pixbuf and not self.is_default_icon:
            # This part is correct and remains the same
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, (width - self.size) / 2, (height - self.size) / 2)
            cr.paint()
        else: # Draw a placeholder icon
            center_x, center_y = width / 2, height / 2
            icon_radius = self.size * 0.4 
            icon_size = int(icon_radius * 2)

            # Draw the background circle
            cr.set_source_rgba(0.2, 0.2, 0.25, 0.8)
            cr.arc(center_x, center_y, self.size / 2, 0, 2 * math.pi)
            cr.fill()
            
            # Get the themed icon as a paintable object
            icon_theme = Gtk.IconTheme.get_for_display(self.get_display())
            paintable = icon_theme.lookup_icon(
                "audio-x-generic-symbolic", # Use the symbolic variant
                None,
                icon_size,
                1,
                Gtk.TextDirection.NONE,
                Gtk.IconLookupFlags.FORCE_SYMBOLIC
            )

            # === THE FIX IS HERE ===
            if paintable:
                # 1. Create a snapshot object
                snapshot = Gtk.Snapshot.new()
                
                # 2. Use snapshot() with the correct arguments: snapshot, width, height
                paintable.snapshot(snapshot, icon_size, icon_size)
                
                # 3. Get the renderable node from the snapshot
                render_node = snapshot.to_node()
                
                # 4. Draw the node to the cairo context
                if render_node:
                    # Set the color for the symbolic icon before drawing
                    cr.set_source_rgba(1, 1, 1, 0.7) 
                    cr.save()
                    # Translate to center the icon
                    cr.translate(center_x - icon_radius, center_y - icon_radius)
                    render_node.draw(cr)
                    cr.restore()
            # === END OF FIX ===

class PlayerIconButton(Gtk.Button):
    def __init__(self, player_name):
        super().__init__()
        self.player_name = player_name
        
        if 'plasma-browser-integration' in player_name.lower():
            display_name = "Browser"
            icon_name = "web-browser-symbolic"
        else:
            display_name = player_name.split('.')[0].title()
            # A simple map for common player icons
            icon_map =         player_icons = {
            'spotify': 'audio-x-generic-symbolic',
            'firefox': 'firefox-symbolic',
            'chrome': 'web-browser-symbolic',
            'chromium': 'web-browser-symbolic',
            'vlc': 'video-x-generic-symbolic',
            'mpv': 'video-x-generic-symbolic',
            'rhythmbox': 'audio-x-generic-symbolic',
            'amarok': 'audio-x-generic-symbolic',
            'clementine': 'audio-x-generic-symbolic',
            'audacious': 'audio-x-generic-symbolic',
            'deadbeef': 'audio-x-generic-symbolic',
            'smplayer': 'video-x-generic-symbolic',
            'totem': 'video-x-generic-symbolic',
            'banshee': 'audio-x-generic-symbolic',
            'pragha': 'audio-x-generic-symbolic',
            'lollypop': 'audio-x-generic-symbolic',
            'strawberry': 'audio-x-generic-symbolic',
            'elisa': 'audio-x-generic-symbolic',
            'plasma-browser-integration': 'firefox-symbolic',
            'kdeconnect': 'phone-symbolic'
        }
            player_key = display_name.lower()
            icon_name = icon_map.get(player_key, "multimedia-player-symbolic")

        self.set_size_request(48, 48)
        self.add_css_class("circular")
        self.add_css_class("player-icon")
        self.set_icon_name(icon_name)
        self.set_tooltip_text(display_name)
    
    def set_active(self, active):
        if active:
            self.add_css_class("suggested-action")
        else:
            self.remove_css_class("suggested-action")

class MediaPlayerWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        
        # State management
        self.current_player = None
        self.players = []
        self.player_buttons = []
        self._last_known_art_url = None
        
        # Flags for preventing UI feedback loops
        self._is_seeking = False
        self._is_volume_changing = False
        
        # **LAG FIX: Properties to manage activation state**
        self.is_active = False
        self.update_timer_id = None
        
        # Command queue for sending playerctl commands without blocking
        self.command_queue = queue.Queue()
        self.command_thread = threading.Thread(target=self._command_worker, daemon=True)
        self.command_thread.start()
        
        self.create_ui()
        # **LAG FIX: Note that the update timer is NOT started here.**
        # It will be started by the activate() method.

    def _command_worker(self):
        """Worker thread for executing blocking playerctl commands."""
        while True:
            try:
                command = self.command_queue.get()
                if command:
                    subprocess.run(command, shell=True, capture_output=True, text=True, timeout=2)
                self.command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in command worker: {e}")

    # **LAG FIX: New methods to control background activity**
    def activate(self):
        """Called by the parent Dashboard when this widget becomes visible."""
        if self.is_active:
            return
        self.is_active = True
        print("MediaPlayerWidget Activated")
        # Perform an immediate update and then start the periodic timer.
        self.update_all_info() 
        if self.update_timer_id is None:
            # Poll every 500ms for smooth progress updates. This is fine now
            # because it will be stopped when the view is inactive.
            self.update_timer_id = GLib.timeout_add(500, self.update_all_info)

    def deactivate(self):
        """Called by the parent Dashboard when this widget is hidden."""
        if not self.is_active:
            return
        self.is_active = False
        print("MediaPlayerWidget Deactivated")
        # Stop the update timer to prevent any background work.
        if self.update_timer_id:
            GLib.source_remove(self.update_timer_id)
            self.update_timer_id = None
    
    def create_ui(self):
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        
        self.players_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.CENTER)
        
        art_container = Gtk.Overlay(halign=Gtk.Align.CENTER)
        self.progress_widget = CircularProgressWidget()
        self.progress_widget.set_seek_callback(self.on_seek)
        art_container.set_child(self.progress_widget)
        
        self.album_art = CircularImage(180)
        self.album_art.set_halign(Gtk.Align.CENTER)
        self.album_art.set_valign(Gtk.Align.CENTER)
        self.album_art.set_can_target(False)
        art_container.add_overlay(self.album_art)
        
        track_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, halign=Gtk.Align.CENTER)
        self.title_label = Gtk.Label(label="No Media Playing", ellipsize=Pango.EllipsizeMode.END, max_width_chars=30, halign=Gtk.Align.CENTER)
        self.title_label.add_css_class("title-label")
        self.artist_label = Gtk.Label(label="Select a player", ellipsize=Pango.EllipsizeMode.END, max_width_chars=35, halign=Gtk.Align.CENTER)
        self.artist_label.add_css_class("artist-label")
        self.time_label = Gtk.Label(label="--:-- / --:--", halign=Gtk.Align.CENTER)
        self.time_label.add_css_class("time-label")
        track_info_box.append(self.title_label)
        track_info_box.append(self.artist_label)
        track_info_box.append(self.time_label)
        
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15, halign=Gtk.Align.CENTER, margin_top=10)
        self.prev_button = Gtk.Button(icon_name="media-skip-backward-symbolic", css_classes=["circular", "control-button"], sensitive=False)
        self.prev_button.set_size_request(44, 44)
        self.prev_button.connect("clicked", lambda b: self._queue_command("previous"))
        self.play_pause_button = Gtk.Button(icon_name="media-playback-start-symbolic", css_classes=["circular", "play-button"], sensitive=False)
        self.play_pause_button.set_size_request(56, 56)
        self.play_pause_button.connect("clicked", self.on_play_pause_clicked)
        self.next_button = Gtk.Button(icon_name="media-skip-forward-symbolic", css_classes=["circular", "control-button"], sensitive=False)
        self.next_button.set_size_request(44, 44)
        self.next_button.connect("clicked", lambda b: self._queue_command("next"))
        controls_box.append(self.prev_button)
        controls_box.append(self.play_pause_button)
        controls_box.append(self.next_button)
        
        volume_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10, halign=Gtk.Align.CENTER, margin_top=10)
        
        # === THE FIX IS HERE ===
        # 1. Create the scale with only valid constructor properties
        self.volume_scale = Gtk.Scale(draw_value=False, sensitive=False, css_classes=["volume-scale"])
        # 2. Set the range and value afterwards using their specific methods
        self.volume_scale.set_range(0, 1)
        self.volume_scale.set_value(0.5)
        # === END OF FIX ===
        
        self.volume_scale.set_size_request(120, -1)
        self.volume_scale.connect("value-changed", self.on_volume_changed)
        volume_box.append(Gtk.Image(icon_name="audio-volume-medium-symbolic"))
        volume_box.append(self.volume_scale)
        
        self.append(self.players_box)
        self.append(art_container)
        self.append(track_info_box)
        self.append(controls_box)
        self.append(volume_box)

    def _run_sync_command(self, cmd):
        """Runs a command that needs an immediate return value. Use sparingly."""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=0.5)
            return result.stdout.strip() if result.returncode == 0 else None
        except subprocess.TimeoutExpired:
            print(f"Timeout running command: {cmd}")
            return None
        except Exception:
            return None
            
    def _queue_command(self, command):
        """Queues a command for the background worker thread."""
        if self.current_player:
            self.command_queue.put(f"playerctl -p {self.current_player} {command}")

    def on_play_pause_clicked(self, button):
        """Instantly updates UI and queues the command."""
        is_currently_playing = "media-playback-pause-symbolic" in button.get_icon_name()
        new_icon = "media-playback-start-symbolic" if is_currently_playing else "media-playback-pause-symbolic"
        button.set_icon_name(new_icon)
        self._queue_command("play-pause")
    
    def on_seek(self, progress):
        """Instantly updates progress UI and queues the seek command."""
        if not self.current_player: return
        
        length_str = self._run_sync_command(f"playerctl -p {self.current_player} metadata mpris:length")
        if not length_str: return
        
        self._is_seeking = True
        total_seconds = int(length_str) // 1000000
        target_seconds = int(total_seconds * progress)
        
        self.progress_widget.set_progress(progress)
        self.time_label.set_text(f"{self.format_time(target_seconds)} / {self.format_time(total_seconds)}")
        
        self._queue_command(f"position {target_seconds}")
        
        # After a short delay, allow regular position updates to resume.
        GLib.timeout_add(1000, lambda: setattr(self, '_is_seeking', False))
    
    def on_volume_changed(self, scale):
        if self._is_volume_changing: return # Prevent feedback loop
        volume = scale.get_value()
        self._queue_command(f"volume {volume}")

    def on_player_selected(self, player_name):
        """Handle switching to a different media player."""
        if self.current_player != player_name:
            self.current_player = player_name
            self._last_known_art_url = None # Force art reload for new player
            self.update_all_info(force_update=True)
            self.update_player_buttons_state()

# In media_player.py, inside the MediaPlayerWidget class

    def update_all_info(self, force_update=False):
        """The main update loop, called by the timer. This version uses a dedicated
        'playerctl position' call for maximum reliability."""
        if not self.is_active:
            return GLib.SOURCE_REMOVE

        players_output = self._run_sync_command("playerctl -l 2>/dev/null")
        new_players = [p for p in (players_output.split('\n') if players_output else []) if 'firefox' not in p.lower()]

        if new_players != self.players or force_update:
            self.players = new_players
            self._rebuild_player_buttons()
        
        if not self.current_player or self.current_player not in self.players:
            self.current_player = self.players[0] if self.players else None
            self._last_known_art_url = None
            self.update_player_buttons_state()

        if not self.current_player:
            self._reset_ui_to_default()
            return GLib.SOURCE_CONTINUE
        
        # --- THE FIX ---
        # 1. Get metadata WITHOUT position, as mpris:position is unreliable.
        metadata_output = self._run_sync_command(
            f"playerctl -p {self.current_player} metadata --format "
            "'{{status}};{{mpris:length}};{{volume}};{{mpris:artUrl}};{{title}};{{artist}}'"
        )
        
        # 2. Get position with its own dedicated, robust command.
        position_str = self._run_sync_command(f"playerctl -p {self.current_player} position")
        
        if not metadata_output:
            self.current_player = None
            return GLib.SOURCE_CONTINUE

        try:
            status, length_us_str, vol_str, art_url, title, artist = metadata_output.split(';', 5)
            
            is_playing = (status == 'Playing')
            self.play_pause_button.set_icon_name("media-playback-pause-symbolic" if is_playing else "media-playback-start-symbolic")

            self.title_label.set_label(title or "Unknown Title")
            self.artist_label.set_label(artist or "Unknown Artist")

            # 3. Parse all values robustly.
            try:
                length_s = int(float(length_us_str) / 1000000)
            except (ValueError, TypeError, AttributeError):
                length_s = 0

            try:
                position_s = int(float(position_str))
            except (ValueError, TypeError, AttributeError):
                position_s = 0

            if position_s > length_s and length_s > 0:
                position_s = length_s

            if not self._is_seeking:
                self.time_label.set_text(f"{self.format_time(position_s)} / {self.format_time(length_s)}")
                self.progress_widget.set_progress(position_s / length_s if length_s > 0 else 0)

            if art_url != self._last_known_art_url:
                self._last_known_art_url = art_url
                if art_url.startswith(('http', 'file')):
                    self.album_art.set_from_url(art_url) if art_url.startswith('http') else self.album_art.set_from_file(art_url.replace('file://', ''))
                else:
                    self.album_art.set_default_icon()
            
            self._is_volume_changing = True
            try:
                self.volume_scale.set_value(float(vol_str))
            except (ValueError, TypeError, AttributeError):
                self.volume_scale.set_value(0.5)
            self._is_volume_changing = False

            for w in [self.play_pause_button, self.prev_button, self.next_button, self.volume_scale, self.progress_widget]:
                w.set_sensitive(True)

        except Exception as e:
            print(f"Error parsing metadata ('{metadata_output}' and '{position_str}'): {e}")
            self._reset_ui_to_default()
        
        return GLib.SOURCE_CONTINUE

    def on_seek(self, progress):
        """Instantly updates progress UI and queues the seek command."""
        if not self.current_player: return
        
        length_us_str = self._run_sync_command(f"playerctl -p {self.current_player} metadata mpris:length")
        
        # === Apply the same robust parsing here ===
        try:
            total_seconds = int(float(length_us_str) / 1000000)
        except (ValueError, TypeError, AttributeError):
            # If we can't get the length, we can't seek.
            return
        
        if total_seconds == 0:
            return # Can't seek on a zero-length track
        # === End of parsing fix ===

        self._is_seeking = True
        target_seconds = int(total_seconds * progress)
        
        self.progress_widget.set_progress(progress)
        self.time_label.set_text(f"{self.format_time(target_seconds)} / {self.format_time(total_seconds)}")
        
        # playerctl's position command expects seconds, which can be a float for precision
        target_position_for_playerctl = total_seconds * progress
        self._queue_command(f"position {target_position_for_playerctl}")
        
        GLib.timeout_add(1000, lambda: setattr(self, '_is_seeking', False))

    # (The format_time method and others remain the same)
    
    def _rebuild_player_buttons(self):
        """Clears and rebuilds the player selection buttons."""
        for button in self.player_buttons:
            self.players_box.remove(button)
        self.player_buttons.clear()
        
        for player_name in self.players:
            button = PlayerIconButton(player_name)
            button.connect("clicked", lambda b, p=player_name: self.on_player_selected(p))
            self.player_buttons.append(button)
            self.players_box.append(button)
        
        self.update_player_buttons_state()

    def update_player_buttons_state(self):
        """Sets the 'active' CSS class on the current player button."""
        for button in self.player_buttons:
            button.set_active(button.player_name == self.current_player)

    def _reset_ui_to_default(self):
        """Resets the UI to the 'No media playing' state."""
        self.title_label.set_label("No Media Playing")
        self.artist_label.set_label("Waiting for a player...")
        self.time_label.set_text("--:-- / --:--")
        self.album_art.set_default_icon()
        self.progress_widget.set_progress(0)
        self.play_pause_button.set_icon_name("media-playback-start-symbolic")
        self._last_known_art_url = None
        for w in [self.play_pause_button, self.prev_button, self.next_button, self.volume_scale, self.progress_widget]:
            w.set_sensitive(False)

# In media_player.py, inside the MediaPlayerWidget class

    def format_time(self, seconds):
        """
        Formats seconds into a H:MM:SS or MM:SS string.
        """
        if seconds < 0: seconds = 0
        
        # Calculate hours, minutes, and seconds
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        
        if h > 0:
            return f"{h:d}:{m:02d}:{s:02d}"
        else:
            return f"{m:d}:{s:02d}"