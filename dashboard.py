import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gdk, GLib
import warnings

warnings.filterwarnings("ignore")

# These will be refactored in the next steps. For now, they are just imported.
from media_player import MediaPlayerWidget
from notifications import NotificationsWidget
from adb import ADBWidget

class Dashboard(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        self.set_title("Media Controller")
        self.set_default_size(800, 600)
        # Use set_size_request for a minimum size, not a fixed one.
        # This works better with tiling window managers like Hyprland.
        self.set_size_request(800, 600) 
        
        self.current_view_name = "media"
        self.current_widget = None # To track the currently active widget instance
        self.widgets = {} # Dictionary to hold widget instances
        
        # Escape key handler
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_controller)
        
        self.create_ui()
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle escape key to close the application."""
        if keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False
    
    def create_ui(self):
        # **FIX 1: Use Adw.ToastOverlay and Adw.Leaflet for a modern layout.**
        # An Adw.Leaflet is the modern, standard way to create a sidebar+content view.
        # It's more efficient and handles transitions better than a manual Gtk.Box.
        toast_overlay = Adw.ToastOverlay()
        self.set_content(toast_overlay)
        
        leaflet = Adw.Leaflet()
        leaflet.set_can_navigate_back(True) # For future adaptive improvements
        toast_overlay.set_child(leaflet)
        
        # **FIX 2: A more professional sidebar.**
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sidebar.set_size_request(90, -1) # Slightly wider for better icon spacing
        sidebar.add_css_class("sidebar")
        
        # **FIX 3: Better padding and alignment for a cleaner look.**
        sidebar.set_margin_top(20)
        sidebar.set_margin_bottom(20)
        sidebar.set_margin_start(10)
        sidebar.set_margin_end(10)
        sidebar.set_valign(Gtk.Align.CENTER) # Vertically center the buttons

        # --- Sidebar Buttons ---
        # No functional change here, just adding to the new sidebar structure.
        self.media_button = Gtk.Button(icon_name="audio-headphones-symbolic")
        self.media_button.set_size_request(60, 60)
        self.media_button.add_css_class("circular")
        self.media_button.add_css_class("sidebar-button")
        self.media_button.set_tooltip_text("Media Player")
        self.media_button.connect("clicked", lambda b: self.switch_view("media"))
        
        self.notifications_button = Gtk.Button(icon_name="preferences-system-notifications-symbolic")
        self.notifications_button.set_size_request(60, 60)
        self.notifications_button.add_css_class("circular")
        self.notifications_button.add_css_class("sidebar-button")
        self.notifications_button.set_tooltip_text("Notifications")
        self.notifications_button.connect("clicked", lambda b: self.switch_view("notifications"))
        
        self.adb_button = Gtk.Button(icon_name="phone-symbolic")
        self.adb_button.set_size_request(60, 60)
        self.adb_button.add_css_class("circular")
        self.adb_button.add_css_class("sidebar-button")
        self.adb_button.set_tooltip_text("ADB Controller")
        self.adb_button.connect("clicked", lambda b: self.switch_view("adb"))
        
        sidebar.append(self.media_button)
        sidebar.append(self.notifications_button)
        sidebar.append(self.adb_button)
        
        # --- Content Area using Gtk.Stack ---
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.content_stack.set_transition_duration(300) # A slightly slower, smoother transition
        
        # Add sidebar and content to the leaflet
        leaflet.append(sidebar)
        leaflet.append(self.content_stack)
        
        # **STARTUP SPEED FIX:** Defer widget creation slightly. This allows the main window
        # to draw itself instantly, giving the perception of a faster launch.
        GLib.timeout_add(50, self.create_and_activate_initial_widgets)
        
        # **FIX 4: Enhanced CSS for a premium look.**
        # This CSS is added to complement your existing style, not replace it.
        self.apply_enhanced_css()

    def create_and_activate_initial_widgets(self):
        """
        Creates the widget instances and adds them to the stack.
        Crucially, it now only ACTIVATES the initial view, preventing others from running.
        """
        try:
            # Create instances but don't start their background work yet.
            # The background work will be started by the new activate() methods.
            self.widgets["media"] = MediaPlayerWidget()
            self.widgets["notifications"] = NotificationsWidget()
            self.widgets["adb"] = ADBWidget()
            
            self.content_stack.add_named(self.widgets["media"], "media")
            self.content_stack.add_named(self.widgets["notifications"], "notifications")
            self.content_stack.add_named(self.widgets["adb"], "adb")

            # Set initial view and ACTIVATE the first widget's background tasks.
            self.content_stack.set_visible_child_name("media")
            self.current_widget = self.widgets["media"]
            # This is a new method we will add to the other widget files.
            if hasattr(self.current_widget, 'activate'):
                self.current_widget.activate() 
            
            self.update_sidebar_buttons()
            
        except Exception as e:
            print(f"Error creating widgets: {e}")
        
        return GLib.SOURCE_REMOVE # Prevents the timeout from running again.
    
    def switch_view(self, view_name):
        """
        **THE CORE LAG FIX:** This function now handles deactivating the old view
        and activating the new one, ensuring only one widget is polling in the background.
        """
        if view_name == self.current_view_name:
            return # Don't do anything if we're already on this view

        try:
            # 1. Deactivate the current widget's background tasks to stop lag.
            if self.current_widget and hasattr(self.current_widget, 'deactivate'):
                self.current_widget.deactivate()

            # 2. Switch the UI
            self.current_view_name = view_name
            self.content_stack.set_visible_child_name(view_name)
            self.update_sidebar_buttons()

            # 3. Activate the new widget's background tasks.
            self.current_widget = self.widgets.get(view_name)
            if self.current_widget and hasattr(self.current_widget, 'activate'):
                self.current_widget.activate()

        except Exception as e:
            print(f"Error switching view: {e}")
    
    def update_sidebar_buttons(self):
        """Update button states based on the current view. (No change needed here)."""
        buttons = {
            "media": self.media_button,
            "notifications": self.notifications_button,
            "adb": self.adb_button
        }
        for name, button in buttons.items():
            if name == self.current_view_name:
                button.add_css_class("active")
            else:
                button.remove_css_class("active")

    def apply_enhanced_css(self):
        """
        Enhanced CSS for a professional look. It PREPENDS new styles to your
        existing ones, ensuring your specific widget styles are preserved.
        """
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(b"""
        /* --- NEW STYLES for a more polished look & feel --- */

        /* Window: Softer shadow for depth, works great with Hyprland transparency. */
        window {
            background: rgba(30, 30, 35, 0.7);
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Sidebar: Subtle gradient and a soft border for separation. */
        .sidebar {
            background-image: linear-gradient(to bottom, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.02));
            border-radius: 12px; /* Rounded corners for the sidebar itself */
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Sidebar Buttons: Smoother transitions and a refined look. */
        .sidebar-button {
            background: transparent;
            border: 1px solid transparent;
            color: rgba(255, 255, 255, 0.6);
            transition: all 250ms ease-in-out;
            border-radius: 30px; /* Perfect circle */
        }

        .sidebar-button:hover {
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.9);
        }
        
        /* Active Sidebar Button: A prominent "glow" effect. */
        .sidebar-button.active {
            background: rgba(80, 160, 255, 0.25);
            color: white;
            border: 1px solid rgba(80, 160, 255, 0.5);
            box-shadow: 0 0 12px rgba(80, 160, 255, 0.5);
        }
        
        /* General Widget Styling for consistency */
        searchbar, entry {
            background: rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 8px;
            color: white;
            padding: 8px 12px;
            box-shadow: inset 0 1px 2px rgba(0,0,0,0.2);
        }
        
        searchbar:focus, entry:focus {
            border-color: rgba(80, 160, 255, 0.6);
            box-shadow: 0 0 0 3px rgba(80, 160, 255, 0.2);
        }
        
        /* Scrollbars that are visible but not intrusive, enhancing your design */
        .notification-body-scroll { background: transparent; } /* Your class */
        
        .notification-body-scroll scrollbar {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
            min-width: 8px;
            opacity: 1; /* Make it visible */
        }

        .notification-body-scroll scrollbar slider {
            background: rgba(255, 255, 255, 0.3);
            border-radius: 4px;
            min-width: 8px;
            min-height: 20px;
        }
        
        /* --- YOUR EXISTING STYLES ARE PRESERVED BELOW --- */
        /* This ensures the specific look of your widgets remains unchanged. */
        
        .invisible-scroll { background: transparent; }
        .invisible-scroll scrollbar { min-width: 0px; opacity: 0; }
        .invisible-scroll scrollbar slider { min-width: 0px; opacity: 0; }
        .notification-icon-bg { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 24px; }
        .notifications-list { background: transparent; }
        .notification-row { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; margin: 4px 0px; transition: all 150ms ease; }
        .notification-row:hover { background: rgba(255, 255, 255, 0.07); border-color: rgba(255, 255, 255, 0.15); }
        .notification-row.expanded { background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.2); }
        .app-name { font-size: 11px; font-weight: bold; color: rgba(255, 255, 255, 0.9); text-transform: uppercase; letter-spacing: 0.5px; }
        .time-label { font-size: 10px; color: rgba(255, 255, 255, 0.6); }
        .summary-label { font-size: 13px; font-weight: 500; color: rgba(255, 255, 255, 0.95); }
        .body-label { font-size: 12px; color: rgba(255, 255, 255, 0.8); line-height: 1.4; }
        .expand-icon { color: rgba(255, 255, 255, 0.6); transition: transform 150ms ease; }
        .title-large { font-size: 20px; font-weight: bold; color: white; }
        .dim-label { color: rgba(255, 255, 255, 0.6); }
        .title-label { font-size: 16px; font-weight: bold; color: rgba(255, 255, 255, 0.95); text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); }
        .artist-label { font-size: 13px; color: rgba(255, 255, 255, 0.8); text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5); }
        .control-button { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.9); transition: all 100ms ease; }
        .control-button:hover { background: rgba(255, 255, 255, 0.2); transform: scale(1.05); }
        .play-button { background: rgba(255, 255, 255, 0.2); border: 2px solid rgba(255, 255, 255, 0.4); color: rgba(255, 255, 255, 0.95); transition: all 100ms ease; }
        .play-button:hover { background: rgba(255, 255, 255, 0.3); transform: scale(1.05); }
        .player-icon { background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.7); transition: all 100ms ease; }
        .player-icon:hover { background: rgba(255, 255, 255, 0.2); color: rgba(255, 255, 255, 0.9); transform: scale(1.05); }
        .player-icon.suggested-action { background: rgba(80, 160, 255, 0.2); color: white; border: 1px solid rgba(80, 160, 255, 0.4); }
        .volume-scale trough { background: rgba(0, 0, 0, 0.3); border-radius: 10px; }
        .volume-scale highlight { background: rgba(255, 255, 255, 0.6); border-radius: 10px; }
        .device-header { background: rgba(255, 255, 255, 0.05); border-radius: 16px; transition: all 150ms ease; padding: 12px 16px; }
        .info-tile { background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05)); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 12px; padding: 12px; transition: all 200ms ease; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1); }
        .info-tile:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2); }
        .section-title { font-size: 14px; font-weight: bold; color: rgba(255, 255, 255, 0.9); text-transform: uppercase; letter-spacing: 0.5px; }
        .action-button { background: rgba(255, 255, 255, 0.08); border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 12px; color: rgba(255, 255, 255, 0.9); transition: all 150ms ease; }
        .action-button:hover { background: rgba(255, 255, 255, 0.15); border-color: rgba(255, 255, 255, 0.3); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3); }

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

# This remains the same, it's standard and correct.
def main():
    try:
        app = DashboardApp()
        return app.run()
    except Exception as e:
        print(f"Error starting app: {e}")
        return 1

if __name__ == '__main__':
    main()