import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib
import warnings

warnings.filterwarnings("ignore")

from media_player import MediaPlayerWidget
from notifications import NotificationsWidget
from adb import ADBWidget

class Dashboard(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Media Controller")
        self.set_default_size(800, 600)
        self.set_size_request(800, 600)
        
        self.current_view = "media"
        
        # Escape key handler
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
        
        self.create_ui()
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle escape key"""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
    
    def create_ui(self):
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        
        # Clean sidebar
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        sidebar.set_size_request(80, -1)
        sidebar.add_css_class("sidebar")
        sidebar.set_margin_top(15)
        sidebar.set_margin_bottom(15)
        sidebar.set_margin_start(15)
        sidebar.set_margin_end(15)
        
        # Media button
        self.media_button = Gtk.Button()
        self.media_button.set_icon_name("audio-headphones-symbolic")
        self.media_button.set_size_request(60, 60)
        self.media_button.add_css_class("circular")
        self.media_button.add_css_class("sidebar-button")
        self.media_button.set_tooltip_text("Media Player")
        self.media_button.connect("clicked", lambda b: self.switch_view("media"))
        
        # Notifications button
        self.notifications_button = Gtk.Button()
        self.notifications_button.set_icon_name("preferences-system-notifications-symbolic")
        self.notifications_button.set_size_request(60, 60)
        self.notifications_button.add_css_class("circular")
        self.notifications_button.add_css_class("sidebar-button")
        self.notifications_button.set_tooltip_text("Notifications")
        self.notifications_button.connect("clicked", lambda b: self.switch_view("notifications"))
        
        # ADB button
        self.adb_button = Gtk.Button()
        self.adb_button.set_icon_name("phone-symbolic")
        self.adb_button.set_size_request(60, 60)
        self.adb_button.add_css_class("circular")
        self.adb_button.add_css_class("sidebar-button")
        self.adb_button.set_tooltip_text("ADB Controller")
        self.adb_button.connect("clicked", lambda b: self.switch_view("adb"))
        
        sidebar.append(self.media_button)
        sidebar.append(self.notifications_button)
        sidebar.append(self.adb_button)
        
        # Content area
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.content_stack.set_transition_duration(200)
        
        # Create widgets
        GLib.timeout_add(50, self.create_widgets)
        
        main_box.append(sidebar)
        main_box.append(self.content_stack)
        
        # FIXED CSS with PROPERLY VISIBLE body scrollbars
        self.add_working_scroll_css()
        
        self.set_content(main_box)
    
    def create_widgets(self):
        """Create widgets"""
        try:
            self.media_widget = MediaPlayerWidget()
            self.notifications_widget = NotificationsWidget()
            self.adb_widget = ADBWidget()
            
            self.content_stack.add_named(self.media_widget, "media")
            self.content_stack.add_named(self.notifications_widget, "notifications")
            self.content_stack.add_named(self.adb_widget, "adb")
            
            self.content_stack.set_visible_child_name("media")
            self.update_sidebar_buttons()
            
        except Exception as e:
            print(f"Error creating widgets: {e}")
        
        return False
    
    def switch_view(self, view_name):
        """Switch views"""
        try:
            self.current_view = view_name
            self.content_stack.set_visible_child_name(view_name)
            self.update_sidebar_buttons()
        except Exception as e:
            print(f"Error switching view: {e}")
    
    def update_sidebar_buttons(self):
        """Update button states"""
        self.media_button.remove_css_class("active")
        self.notifications_button.remove_css_class("active")
        self.adb_button.remove_css_class("active")
        
        if self.current_view == "media":
            self.media_button.add_css_class("active")
        elif self.current_view == "notifications":
            self.notifications_button.add_css_class("active")
        elif self.current_view == "adb":
            self.adb_button.add_css_class("active")
    
    def add_working_scroll_css(self):
        """FIXED CSS with ACTUALLY VISIBLE body scrollbars"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        /* Clean transparent window */
        window {
            background: rgba(20, 20, 20, 0.1);
            border-radius: 12px;
            border: 1px solid white;
        }
        
        /* Clean sidebar */
        .sidebar {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Perfect circular sidebar buttons */
        .sidebar-button {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: rgba(255, 255, 255, 0.7);
            transition: all 150ms ease;
            margin-bottom: 8px;
            border-radius: 30px;
        }
        
        
        .sidebar-button.active {
            background: rgba(255, 255, 255, 0.3);
            color: rgba(255, 255, 255, 1.0);
            border: 2px solid rgba(255, 255, 255, 0.5);
        }
        
        /* Search styling */
        searchbar, entry {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            color: rgba(255, 255, 255, 0.9);
            padding: 8px 12px;
        }
        
        searchbar:focus, entry:focus {
            background: rgba(255, 255, 255, 0.15);
            border-color: rgba(255, 255, 255, 0.4);
            outline: none;
            box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.1);
        }
        
        /* INVISIBLE MAIN SCROLLBAR */
        .invisible-scroll {
            background: transparent;
        }
        
        .invisible-scroll scrollbar {
            background: transparent;
            opacity: 0;
            min-width: 0px;
        }
        
        .invisible-scroll scrollbar slider {
            background: transparent;
            opacity: 0;
            min-width: 0px;
        }
        /* FIXED: ACTUALLY VISIBLE body scrollbars with proper styling */
        .notification-body-scroll {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 8px;
        }
        
        .notification-body-scroll scrollbar {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 6px;
            min-width: 0px;
            opacity: 1;
        }
        
        .notification-body-scroll scrollbar.vertical {
            border-left: 1px solid rgba(255, 255, 255, 0.1);
            margin-left: 10px;
        }
        
        .notification-body-scroll scrollbar slider {
            background: rgba(255, 255, 255, 0.4);
            border-radius: 6px;
            min-width: 1px;
            min-height: 20px;
            margin: 0px;
            opacity: 1;
        }
        
        .notification-body-scroll scrollbar slider:active {
            background: rgba(255, 255, 255, 0.8);
        }
        
        
        /* PERFECT CIRCULAR notification icon background */
        .notification-icon-bg {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 24px;
        }
        
        /* Clean notification rows */
        .notifications-list {
            background: transparent;
        }
        
        .notification-row {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            margin: 6px 0px;
            transition: all 150ms ease;
        }
        
        .notification-row:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.2);
        }
        
        .notification-row.expanded {
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.3);
        }
        
        /* Text styling */
        .app-name {
            font-size: 11px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.9);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .time-label {
            font-size: 10px;
            color: rgba(255, 255, 255, 0.6);
        }
        
        .summary-label {
            font-size: 13px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.95);
        }
        
        .body-label {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.8);
            line-height: 1.4;
        }
        
        .expand-icon {
            color: rgba(255, 255, 255, 0.6);
            transition: transform 150ms ease;
        }
        
        .title-large {
            font-size: 18px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.95);
        }
        
        .dim-label {
            color: rgba(255, 255, 255, 0.6);
        }
        
        /* Media player styles */
        .title-label { font-size: 16px; font-weight: bold; color: rgba(255, 255, 255, 0.95); text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); }
        .artist-label { font-size: 13px; color: rgba(255, 255, 255, 0.8); text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); }
        .time-label { font-size: 12px; font-weight: 500; color: rgba(255, 255, 255, 0.9); text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); margin-top: 4px; }
        .control-button { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.9); transition: all 100ms ease; }
        .control-button:hover { background: rgba(255, 255, 255, 0.2); transform: scale(1.05); }
        .control-button:active { background: rgba(255, 255, 255, 0.3); transform: scale(0.95); }
        .play-button { background: rgba(255, 255, 255, 0.2); border: 2px solid rgba(255, 255, 255, 0.4); color: rgba(255, 255, 255, 0.95); transition: all 100ms ease; }
        .play-button:hover { background: rgba(255, 255, 255, 0.3); transform: scale(1.05); }
        .play-button:active { background: rgba(255, 255, 255, 0.4); transform: scale(0.95); }
        .player-icon { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.7); transition: all 100ms ease; }
        .player-icon:hover { background: rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.9); transform: scale(1.05); }
        .player-icon:active { background: rgba(255, 255, 255, 0.3); transform: scale(0.95); }
        .player-icon.suggested-action { background: rgba(255, 255, 255, 0.3); color: rgba(255, 255, 255, 1.0); border: 2px solid rgba(255, 255, 255, 0.5); }
        .volume-icon { color: rgba(255, 255, 255, 0.8); }
        .volume-scale trough { background: rgba(255, 255, 255, 0.2); border-radius: 10px; }
        .volume-scale highlight { background: rgba(255, 255, 255, 0.6); border-radius: 10px; }
        .volume-scale slider { background: rgba(255, 255, 255, 0.9); border: 2px solid rgba(255, 255, 255, 0.3); border-radius: 50%; min-width: 14px; min-height: 14px; }
        
        /* ADB Widget styles */
        .device-header {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            transition: all 150ms ease;
        }
        
        .device-header:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.2);
        }
        
        .info-tile {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05));
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            padding: 12px;
            transition: all 200ms ease;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }
        
        .info-tile:hover {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.08));
            border-color: rgba(255, 255, 255, 0.25);
            transform: translateY(-2px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        }
        
        .tile-icon {
            color: rgba(255, 255, 255, 0.9);
            margin-bottom: 4px;
        }
        
        .tile-title {
            font-size: 12px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.7);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .tile-value {
            font-size: 14px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.95);
        }
        
        .device-card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            transition: all 150ms ease;
        }
        
        .device-card:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.2);
        }
        
        .device-name {
            font-size: 16px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.95);
        }
        
        .device-id {
            font-size: 12px;
            color: rgba(255, 255, 255, 0.7);
            font-family: monospace;
        }
        
        .status-label {
            font-size: 11px;
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-connected {
            background: rgba(0, 255, 0, 0.2);
            color: rgba(0, 255, 0, 0.9);
            border: 1px solid rgba(0, 255, 0, 0.3);
        }
        
        .status-disconnected {
            background: rgba(255, 0, 0, 0.2);
            color: rgba(255, 0, 0, 0.9);
            border: 1px solid rgba(255, 0, 0, 0.3);
        }
        
        .detail-label {
            font-size: 13px;
            color: rgba(255, 255, 255, 0.8);
        }
        
        .device-icon {
            color: rgba(255, 255, 255, 0.8);
        }
        
        .section-title {
            font-size: 14px;
            font-weight: bold;
            color: rgba(255, 255, 255, 0.9);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .action-button {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 12px;
            color: rgba(255, 255, 255, 0.9);
            transition: all 150ms ease;
        }
        
        .action-button:hover {
            background: rgba(255, 255, 255, 0.15);
            border-color: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .action-button:active {
            transform: translateY(0px);
            background: rgba(255, 255, 255, 0.2);
        }
        
        .action-label {
            font-size: 11px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.85);
        }
        
        .success {
            color: rgba(0, 255, 0, 0.9);
            background: rgba(0, 255, 0, 0.15);
            border: 1px solid rgba(0, 255, 0, 0.2);
        }
        
        .error {
            color: rgba(255, 0, 0, 0.9);
            background: rgba(255, 0, 0, 0.15);
            border: 1px solid rgba(255, 0, 0, 0.2);
        }
        """)
        
        Gtk.StyleContext.add_provider_for_display(
            self.get_display(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

class DashboardApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(application_id="com.gaurish.Dashboard", **kwargs)
        self.connect('activate', self.on_activate)
    
    def on_activate(self, app):
        try:
            self.win = Dashboard(application=app)
            self.win.present()
        except Exception as e:
            print(f"Error creating dashboard: {e}")

def main():
    try:
        app = DashboardApp()
        return app.run()
    except Exception as e:
        print(f"Error starting app: {e}")
        return 1

if __name__ == '__main__':
    main()