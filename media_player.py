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

# Suppress the deprecation warning for pixbuf_get_from_surface
warnings.filterwarnings("ignore", ".*pixbuf_get_from_surface.*", DeprecationWarning)

class CircularProgressWidget(Gtk.DrawingArea):
    def __init__(self):
        super().__init__()
        self.set_size_request(220, 220)
        self.progress = 0.0
        self.set_draw_func(self.draw_progress)
        
        # Make it interactive - use both click and motion for better detection
        self.gesture_click = Gtk.GestureClick()
        self.gesture_click.connect("pressed", self.on_click)
        self.add_controller(self.gesture_click)
        
        # Add motion controller for better responsiveness
        self.motion_controller = Gtk.EventControllerMotion()
        self.motion_controller.connect("enter", self.on_enter)
        self.motion_controller.connect("leave", self.on_leave)
        self.add_controller(self.motion_controller)
        
        self.callback = None
        self.hovering = False
    
    def set_progress(self, progress):
        self.progress = max(0.0, min(1.0, progress))
        self.queue_draw()
    
    def set_seek_callback(self, callback):
        self.callback = callback
    
    def on_enter(self, controller, x, y):
        """Handle mouse enter for better responsiveness"""
        self.hovering = True
        self.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        self.queue_draw()

    def on_leave(self, controller):
        """Handle mouse leave"""
        self.hovering = False
        self.set_cursor(None)
        self.queue_draw()
    
    def on_click(self, gesture, n_press, x, y):
        if not self.callback:
            return
            
        # Get widget dimensions
        width = self.get_width()
        height = self.get_height()
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 10
        
        # Calculate distance from center
        dx = x - center_x
        dy = y - center_y
        distance = math.sqrt(dx * dx + dy * dy)
        
        # More generous click area - anywhere within reasonable distance
        min_radius = radius - 40  # More tolerant inner bound
        max_radius = radius + 40  # More tolerant outer bound
        
        if distance < min_radius or distance > max_radius:
            return
        
        # Calculate angle from click position
        angle = math.atan2(dy, dx)
        
        # Convert to progress (0-1)
        # Start angle is -π/2 (top), so we adjust
        adjusted_angle = angle + math.pi/2
        
        # Normalize to 0-2π range
        while adjusted_angle < 0:
            adjusted_angle += 2 * math.pi
        while adjusted_angle >= 2 * math.pi:
            adjusted_angle -= 2 * math.pi
            
        progress = adjusted_angle / (2 * math.pi)
        
        # Ensure valid range
        progress = max(0.0, min(1.0, progress))
        
        # Always call the callback
        self.callback(progress)
    
    def draw_progress(self, area, cr, width, height, user_data=None):
        # Center coordinates
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2 - 10
        
        # Background circle (subtle)
        cr.set_source_rgba(1, 1, 1, 0.1)
        cr.set_line_width(6 if self.hovering else 4)  # Thicker when hovering
        cr.arc(center_x, center_y, radius, 0, 2 * math.pi)
        cr.stroke()
        
        # Progress arc
        if self.progress > 0:
            cr.set_source_rgba(1, 1, 1, 0.9 if self.hovering else 0.8)
            cr.set_line_width(6 if self.hovering else 4)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            start_angle = -math.pi / 2  # Start from top
            end_angle = start_angle + (2 * math.pi * self.progress)
            cr.arc(center_x, center_y, radius, start_angle, end_angle)
            cr.stroke()

class CircularImage(Gtk.DrawingArea):
    def __init__(self, size=180):
        super().__init__()
        self.size = size
        self.set_size_request(size, size)
        self.set_draw_func(self.draw_circular_image)
        self.pixbuf = None
        self.default_icon = True
        
    def set_from_file(self, file_path):
        try:
            # Load and scale pixbuf
            original_pixbuf = GdkPixbuf.Pixbuf.new_from_file(file_path)
            self.pixbuf = self.create_circular_pixbuf(original_pixbuf)
            self.default_icon = False
            self.queue_draw()
        except Exception as e:
            print(f"Error loading image: {e}")
            self.set_default_icon()
            
    def set_from_url(self, url):
        try:
            import urllib.request
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                urllib.request.urlretrieve(url, tmp_file.name)
                self.set_from_file(tmp_file.name)
                os.unlink(tmp_file.name)
        except Exception as e:
            print(f"Error loading image from URL: {e}")
            self.set_default_icon()
        
    def set_default_icon(self):
        self.pixbuf = None
        self.default_icon = True
        self.queue_draw()
        
    def create_circular_pixbuf(self, original_pixbuf):
        """Create a circular version of the pixbuf"""
        size = self.size
        
        # Scale to square first
        width = original_pixbuf.get_width()
        height = original_pixbuf.get_height()
        
        if width != height:
            # Crop to square (center crop)
            min_size = min(width, height)
            x_offset = (width - min_size) // 2
            y_offset = (height - min_size) // 2
            original_pixbuf = original_pixbuf.new_subpixbuf(x_offset, y_offset, min_size, min_size)
        
        # Scale to desired size
        scaled_pixbuf = original_pixbuf.scale_simple(size, size, GdkPixbuf.InterpType.BILINEAR)
        
        # Create circular surface
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        ctx = cairo.Context(surface)
        
        # Create circular clipping path
        ctx.arc(size/2, size/2, size/2, 0, 2 * math.pi)
        ctx.clip()
        
        # Draw the scaled pixbuf
        Gdk.cairo_set_source_pixbuf(ctx, scaled_pixbuf, 0, 0)
        ctx.paint()
        
        # Convert surface back to pixbuf
        return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)
        
    def draw_circular_image(self, area, cr, width, height, user_data=None):
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) / 2
        
        if self.pixbuf and not self.default_icon:
            # Draw the circular pixbuf
            Gdk.cairo_set_source_pixbuf(cr, self.pixbuf, 
                                       (width - self.pixbuf.get_width()) / 2,
                                       (height - self.pixbuf.get_height()) / 2)
            cr.paint()
        else:
            # Draw default background circle
            cr.set_source_rgba(0.2, 0.2, 0.2, 0.8)
            cr.arc(center_x, center_y, radius, 0, 2 * math.pi)
            cr.fill()
            
            # Draw music icon
            cr.set_source_rgba(1, 1, 1, 0.7)
            icon_size = radius * 0.6
            
            # Simple music note shape
            note_x = center_x - icon_size/4
            note_y = center_y - icon_size/2
            
            # Draw note stem
            cr.rectangle(note_x + icon_size/3, note_y, icon_size/8, icon_size*0.8)
            cr.fill()
            
            # Draw note head
            cr.arc(note_x, note_y + icon_size*0.7, icon_size/6, 0, 2 * math.pi)
            cr.fill()

class PlayerIconButton(Gtk.Button):
    def __init__(self, player_name, display_name=None):
        super().__init__()
        self.player_name = player_name
        self.display_name = display_name or self.get_display_name(player_name)
        self.set_size_request(48, 48)
        self.add_css_class("circular")
        self.add_css_class("flat")
        self.add_css_class("player-icon")
        
        # Create icon based on player name
        icon_name = self.get_player_icon(player_name)
        self.set_icon_name(icon_name)
        
        # Add tooltip with friendly name
        self.set_tooltip_text(self.display_name)
    
    def get_display_name(self, player_name):
        """Get friendly display name for player"""
        if 'plasma-browser-integration' in player_name.lower():
            return "Firefox"
        return player_name.title()
    
    def get_player_icon(self, player_name):
        """Get appropriate icon for player"""
        player_icons = {
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
        
        player_lower = player_name.lower()
        
        # Special case for plasma-browser-integration - treat it as Firefox
        if 'plasma-browser-integration' in player_lower:
            return 'firefox-symbolic'
        
        for key, icon in player_icons.items():
            if key in player_lower:
                return icon
        
        return 'multimedia-player-symbolic'
    
    def set_active(self, active):
        if active:
            self.add_css_class("suggested-action")
        else:
            self.remove_css_class("suggested-action")

class MediaPlayerWidget(Gtk.Box):
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        
        # Current player info
        self.current_player = None
        self.players = []
        self.player_buttons = []
        self.position = 0
        self.length = 0
        self.is_playing = False
        self._updating_scale = False
        self._seeking = False  # Flag to prevent position updates during seeking
        
        # For instant UI updates
        self.ui_state = {
            'is_playing': False,
            'position': 0,
            'length': 0,
            'volume': 0.5
        }
        
        # Command queue for async execution
        self.command_queue = queue.Queue()
        self.command_thread = threading.Thread(target=self.command_worker, daemon=True)
        self.command_thread.start()
        
        # Create UI
        self.create_ui()
        
        # Start monitoring - more frequent updates
        self.update_players()
        GLib.timeout_add(500, self.update_status)  # 2 times per second for smoother updates

    def command_worker(self):
        """Worker thread for executing commands"""
        while True:
            try:
                command = self.command_queue.get(timeout=1)
                if command:
                    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=1)
                    if result.returncode != 0:
                        print(f"Command failed: {command}")
                self.command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Command error: {e}")
    
    def create_ui(self):
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_margin_start(15)
        self.set_margin_end(15)
        
        # Player selection row
        self.players_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.players_box.set_halign(Gtk.Align.CENTER)
        
        # Album art container with circular progress
        art_container = Gtk.Overlay()
        art_container.set_halign(Gtk.Align.CENTER)
        
        self.progress_widget = CircularProgressWidget()
        self.progress_widget.set_seek_callback(self.on_seek)
        art_container.set_child(self.progress_widget)
        
        self.album_art = CircularImage(180)
        self.album_art.set_halign(Gtk.Align.CENTER)
        self.album_art.set_valign(Gtk.Align.CENTER)
        self.album_art.set_default_icon()
        self.album_art.set_can_target(False)  # Make it click-through
        
        art_container.add_overlay(self.album_art)
        
        # Track info
        track_info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        track_info_box.set_halign(Gtk.Align.CENTER)
        
        self.title_label = Gtk.Label(label="No media playing")
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.title_label.set_halign(Gtk.Align.CENTER)
        self.title_label.add_css_class("title-label")
        self.title_label.set_max_width_chars(25)
        
        self.artist_label = Gtk.Label(label="")
        self.artist_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.artist_label.set_halign(Gtk.Align.CENTER)
        self.artist_label.add_css_class("artist-label")
        self.artist_label.set_max_width_chars(30)
        
        self.time_label = Gtk.Label(label="0:00 / 0:00")
        self.time_label.set_halign(Gtk.Align.CENTER)
        self.time_label.add_css_class("time-label")
        
        track_info_box.append(self.title_label)
        track_info_box.append(self.artist_label)
        track_info_box.append(self.time_label)
        
        # Control buttons
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        controls_box.set_halign(Gtk.Align.CENTER)
        controls_box.set_margin_top(8)
        
        self.prev_button = Gtk.Button()
        self.prev_button.set_icon_name("media-skip-backward-symbolic")
        self.prev_button.add_css_class("circular")
        self.prev_button.add_css_class("control-button")
        self.prev_button.set_size_request(44, 44)
        self.prev_button.connect("clicked", lambda b: self.send_command_instant("Previous"))
        
        self.play_pause_button = Gtk.Button()
        self.play_pause_button.set_icon_name("media-playback-start-symbolic")
        self.play_pause_button.add_css_class("circular")
        self.play_pause_button.add_css_class("play-button")
        self.play_pause_button.set_size_request(56, 56)
        self.play_pause_button.connect("clicked", self.on_play_pause)
        
        self.next_button = Gtk.Button()
        self.next_button.set_icon_name("media-skip-forward-symbolic")
        self.next_button.add_css_class("circular")
        self.next_button.add_css_class("control-button")
        self.next_button.set_size_request(44, 44)
        self.next_button.connect("clicked", lambda b: self.send_command_instant("Next"))
        
        controls_box.append(self.prev_button)
        controls_box.append(self.play_pause_button)
        controls_box.append(self.next_button)
        
        # Volume control
        volume_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        volume_box.set_halign(Gtk.Align.CENTER)
        volume_box.set_margin_top(8)
        
        volume_icon = Gtk.Image()
        volume_icon.set_from_icon_name("audio-volume-medium-symbolic")
        volume_icon.add_css_class("volume-icon")
        
        self.volume_scale = Gtk.Scale()
        self.volume_scale.set_range(0, 1)
        self.volume_scale.set_value(0.5)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_size_request(120, -1)
        self.volume_scale.add_css_class("volume-scale")
        self.volume_scale.connect("value-changed", self.on_volume_changed)
        
        volume_box.append(volume_icon)
        volume_box.append(self.volume_scale)
        
        # Assemble everything
        self.append(self.players_box)
        self.append(art_container)
        self.append(track_info_box)
        self.append(controls_box)
        self.append(volume_box)
    
    def run_command(self, cmd):
        """Run a shell command and return output"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=1)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""
    
    def send_command_instant(self, command):
        """Send command with instant UI feedback"""
        if not self.current_player:
            return
        
        if command == "PlayPause":
            self.ui_state['is_playing'] = not self.ui_state['is_playing']
            icon = "media-playback-pause-symbolic" if self.ui_state['is_playing'] else "media-playback-start-symbolic"
            self.play_pause_button.set_icon_name(icon)
        
        cmd_map = {
            "PlayPause": "play-pause", "Play": "play", "Pause": "pause",
            "Next": "next", "Previous": "previous"
        }
        
        if command in cmd_map:
            cmd = f"playerctl -p {self.current_player} {cmd_map[command]}"
            self.command_queue.put(cmd)
    
    def on_seek(self, progress):
        """Handle seek on circular progress with instant feedback"""
        if not self.current_player or self.ui_state['length'] == 0:
            return
        
        self._seeking = True
        
        self.ui_state['position'] = int(self.ui_state['length'] * progress)
        self.progress_widget.set_progress(progress)
        
        current_time = self.format_time(self.ui_state['position'])
        total_time = self.format_time(self.ui_state['length'])
        self.time_label.set_text(f"{current_time} / {total_time}")
        
        position = self.ui_state['position']
        cmd = f"playerctl -p {self.current_player} position {position}"
        self.command_queue.put(cmd)
        
        GLib.timeout_add(500, lambda: setattr(self, '_seeking', False))
    
    def update_players(self):
        """Update list of available media players"""
        output = self.run_command("playerctl -l 2>/dev/null")
        new_players = output.split('\n') if output else []
        new_players = [p.strip() for p in new_players if p.strip()]
        new_players = [p for p in new_players if not p.lower().startswith('firefox')]
        
        if new_players != self.players:
            self.players = new_players
            
            for button in self.player_buttons:
                self.players_box.remove(button)
            self.player_buttons.clear()
            
            if self.players:
                for player in self.players:
                    display_name = "Firefox" if 'plasma-browser-integration' in player.lower() else player.title()
                    button = PlayerIconButton(player, display_name)
                    button.connect("clicked", lambda b, p=player: self.on_player_selected(p))
                    self.player_buttons.append(button)
                    self.players_box.append(button)
                
                if not self.current_player and self.players:
                    self.current_player = self.players[0]
                
                self.update_player_buttons()
    
    def update_player_buttons(self):
        """Update visual state of player buttons"""
        for i, button in enumerate(self.player_buttons):
            if i < len(self.players):
                button.set_active(self.players[i] == self.current_player)
    
    def on_player_selected(self, player):
        """Handle player selection"""
        self.current_player = player
        self.update_player_buttons()
        # Force a full refresh on player switch
        self.update_status()
    
    def load_album_art(self):
        """Load album artwork as circular image"""
        if not self.current_player:
            return
        
        art_url = self.run_command(f"playerctl -p {self.current_player} metadata mpris:artUrl 2>/dev/null")
        
        if art_url and art_url.startswith(('http://', 'https://', 'file://')):
            if art_url.startswith('file://'):
                file_path = art_url[7:]
                if os.path.exists(file_path):
                    self.album_art.set_from_file(file_path)
                    return
            else:
                self.album_art.set_from_url(art_url)
                return
        
        self.album_art.set_default_icon()
    
    def update_status(self):
        """Update player status and UI"""
        if not self.current_player:
            self.update_players()
            return True
        
        status = self.run_command(f"playerctl -p {self.current_player} status 2>/dev/null")
        
        # If the current player is no longer available, find a new one
        if not status:
            self.current_player = None
            self.update_players()
            return True
        
        actual_playing = status == "Playing"
        
        if actual_playing != self.ui_state['is_playing']:
            self.ui_state['is_playing'] = actual_playing
            icon = "media-playback-pause-symbolic" if actual_playing else "media-playback-start-symbolic"
            self.play_pause_button.set_icon_name(icon)
        
        title = self.run_command(f"playerctl -p {self.current_player} metadata title 2>/dev/null")
        artist = self.run_command(f"playerctl -p {self.current_player} metadata artist 2>/dev/null")
        
        # Check if metadata changed to avoid unnecessary UI updates/flickering
        if title != self.title_label.get_label():
            self.title_label.set_label(title or "Unknown Title")
            self.load_album_art() # Reload art when title changes
        if artist != self.artist_label.get_label():
            self.artist_label.set_label(artist or "Unknown Artist")
        
        if not self._seeking:
            position_str = self.run_command(f"playerctl -p {self.current_player} position 2>/dev/null")
            length_str = self.run_command(f"playerctl -p {self.current_player} metadata mpris:length 2>/dev/null")
            
            try:
                actual_position = int(float(position_str)) if position_str else 0
                actual_length = int(int(length_str) / 1000000) if length_str else 0
            except (ValueError, TypeError):
                actual_position, actual_length = 0, 0
            
            self.ui_state['position'] = actual_position
            self.ui_state['length'] = actual_length
            
            progress = actual_position / actual_length if actual_length > 0 else 0
            self.progress_widget.set_progress(progress)
            
            self.time_label.set_label(f"{self.format_time(actual_position)} / {self.format_time(actual_length)}")
        
        volume_str = self.run_command(f"playerctl -p {self.current_player} volume 2>/dev/null")
        try:
            volume = float(volume_str) if volume_str else 0.5
            if not self._updating_scale:
                self.volume_scale.set_value(volume)
        except (ValueError, TypeError):
            pass
        
        return True
    
    def format_time(self, seconds):
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
    
    def on_play_pause(self, button):
        self.send_command_instant("PlayPause")
    
    def on_volume_changed(self, scale):
        if not self.current_player:
            return
        
        self._updating_scale = True
        volume = scale.get_value()
        self.ui_state['volume'] = volume
        
        cmd = f"playerctl -p {self.current_player} volume {volume}"
        self.command_queue.put(cmd)
        
        GLib.timeout_add(50, lambda: setattr(self, '_updating_scale', False))