import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, Gdk
import subprocess
import re
import threading
import sys
import warnings
import json
import os

warnings.filterwarnings("ignore")

# One-time CSS injection for pink-themed switches
_PINK_SWITCH_CSS_APPLIED = False
def ensure_pink_switch_css():
    global _PINK_SWITCH_CSS_APPLIED
    if _PINK_SWITCH_CSS_APPLIED:
        return
    css = """
    switch.pink-toggle {
        background-color: rgba(255, 182, 193, 0.25);
        border: 1px solid rgba(255, 182, 193, 0.4);
        transition: all 150ms ease;
    }
    switch.pink-toggle:hover {
        background-color: rgba(255, 182, 193, 0.35);
        border-color: rgba(255, 182, 193, 0.5);
    }
    switch.pink-toggle slider {
        background-color: rgba(255, 255, 255, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.2);
        box-shadow: 0 1px 2px rgba(0,0,0,0.25);
    }
    switch.pink-toggle:checked {
        background-color: rgba(255, 182, 193, 0.5);
        border-color: rgba(255, 182, 193, 0.7);
        box-shadow: 0 0 0 3px rgba(255, 182, 193, 0.2);
    }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _PINK_SWITCH_CSS_APPLIED = True

# This class defines a custom GTK widget to display a single WiFi network.
# It shows the network name, signal strength, and buttons to connect or disconnect.
class WiFiNetworkWidget(Gtk.Box):
    # Sets up the widget with the specific network's information.
    def __init__(self, network_info, is_connected=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.network_info = network_info
        self.is_connected = is_connected
        self.is_loading = False
        self.create_ui()

    # Builds the visual elements of the widget, like the icon, labels, and buttons.
    def create_ui(self):
        self.add_css_class("info-tile")
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        signal_strength = self.network_info.get('signal', 0)
        icon_name = self.get_signal_icon(signal_strength)
        signal_icon = Gtk.Image.new_from_icon_name(icon_name)
        signal_icon.set_pixel_size(32)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)

        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_label = Gtk.Label(label=self.network_info.get('ssid', 'Unknown Network'))
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class("device-name")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_box.append(name_label)

        if self.network_info.get('security') != 'Open' and self.network_info.get('security') != '--' and not self.is_connected:
            lock_icon = Gtk.Image.new_from_icon_name("changes-prevent-symbolic")
            lock_icon.set_pixel_size(16)
            lock_icon.add_css_class("dim-label")
            name_box.insert_child_after(lock_icon, name_label)

        if self.is_connected:
            status_text = f"Connected • {signal_strength}% signal"
        else:
            security = self.network_info.get('security', 'Open')
            status_text = f"{security} • {signal_strength}% signal"

        self.status_label = Gtk.Label(label=status_text)
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("device-status")
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)

        info_box.append(name_box)
        info_box.append(self.status_label)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(16, 16)
        self.spinner.set_visible(False)
        self.connect_btn = Gtk.Button(label="Connect")
        self.connect_btn.set_size_request(90, 36)
        self.connect_btn.add_css_class("suggested-action")
        self.disconnect_btn = Gtk.Button(label="Disconnect")
        self.disconnect_btn.set_size_request(90, 36)
        self.disconnect_btn.add_css_class("destructive-action")

        button_box.append(self.spinner)
        button_box.append(self.connect_btn)
        button_box.append(self.disconnect_btn)

        self.append(signal_icon)
        self.append(info_box)
        self.append(button_box)

        self.update_buttons()

    # Updates the sensitivity of the connect and disconnect buttons based on connection status and loading state.
    def update_buttons(self):
        self.connect_btn.set_sensitive(not self.is_connected and not self.is_loading)
        self.disconnect_btn.set_sensitive(self.is_connected and not self.is_loading)

    # Shows or hides a loading spinner and disables the buttons during connection attempts.
    def set_loading(self, loading):
        self.is_loading = loading
        self.spinner.set_visible(loading)
        if loading:
            self.spinner.start()
            status_prefix = "Connecting" if not self.is_connected else "Disconnecting"
            self.status_label.set_label(f"{status_prefix}...")
        else:
            self.spinner.stop()
            signal = self.network_info.get('signal', 0)
            if self.is_connected:
                self.status_label.set_label(f"Connected • {signal}% signal")
            else:
                security = self.network_info.get('security', 'Open')
                self.status_label.set_label(f"{security} • {signal}% signal")
        self.update_buttons()

    # Selects the appropriate WiFi icon based on signal strength percentage.
    def get_signal_icon(self, strength):
        if strength >= 75: return "network-wireless-signal-excellent-symbolic"
        if strength >= 50: return "network-wireless-signal-good-symbolic"
        if strength >= 25: return "network-wireless-signal-ok-symbolic"
        return "network-wireless-signal-weak-symbolic"

# This class defines a custom GTK widget to display Ethernet connections.
# It shows the connection name, status, and buttons to connect or disconnect.
class EthernetConnectionWidget(Gtk.Box):
    # Sets up the widget with the specific connection's information.
    def __init__(self, connection_info, is_connected=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.connection_info = connection_info
        self.is_connected = is_connected
        self.is_loading = False
        self.create_ui()

    # Builds the visual elements of the widget for Ethernet connections.
    def create_ui(self):
        self.add_css_class("info-tile")
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # Ethernet icon
        ethernet_icon = Gtk.Image.new_from_icon_name("network-wired-symbolic")
        ethernet_icon.set_pixel_size(32)

        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)

        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_label = Gtk.Label(label=self.connection_info.get('name', 'Unknown Connection'))
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class("device-name")
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        name_box.append(name_label)

        if self.is_connected:
            status_text = "Connected • Wired"
        else:
            status_text = f"Available • {self.connection_info.get('device', 'Unknown device')}"

        self.status_label = Gtk.Label(label=status_text)
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.add_css_class("device-status")
        self.status_label.set_ellipsize(Pango.EllipsizeMode.END)

        info_box.append(name_box)
        info_box.append(self.status_label)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(16, 16)
        self.spinner.set_visible(False)
        self.connect_btn = Gtk.Button(label="Connect")
        self.connect_btn.set_size_request(90, 36)
        self.connect_btn.add_css_class("suggested-action")
        self.disconnect_btn = Gtk.Button(label="Disconnect")
        self.disconnect_btn.set_size_request(90, 36)
        self.disconnect_btn.add_css_class("destructive-action")

        button_box.append(self.spinner)
        button_box.append(self.connect_btn)
        button_box.append(self.disconnect_btn)

        self.append(ethernet_icon)
        self.append(info_box)
        self.append(button_box)

        self.update_buttons()

    # Updates the sensitivity of the connect and disconnect buttons based on connection status and loading state.
    def update_buttons(self):
        self.connect_btn.set_sensitive(not self.is_connected and not self.is_loading)
        self.disconnect_btn.set_sensitive(self.is_connected and not self.is_loading)

    # Shows or hides a loading spinner and disables the buttons during connection attempts.
    def set_loading(self, loading):
        self.is_loading = loading
        self.spinner.set_visible(loading)
        if loading:
            self.spinner.start()
            status_prefix = "Connecting" if not self.is_connected else "Disconnecting"
            self.status_label.set_label(f"{status_prefix}...")
        else:
            self.spinner.stop()
            if self.is_connected:
                self.status_label.set_label("Connected • Wired")
            else:
                self.status_label.set_label(f"Available • {self.connection_info.get('device', 'Unknown device')}")
        self.update_buttons()

# This class creates a dialog box that pops up to ask for a WiFi password.
class WiFiPasswordDialog(Adw.MessageDialog):
    # Initializes the dialog with a title and a password entry field.
    def __init__(self, parent, network_name):
        super().__init__(transient_for=parent)
        self.set_title("Connect to WiFi")
        self.set_heading(f"Enter password for '{network_name}'")

        entry_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        entry_box.set_margin_top(12); entry_box.set_margin_bottom(12)
        entry_box.set_margin_start(12); entry_box.set_margin_end(12)

        self.password_entry = Gtk.Entry()
        self.password_entry.set_placeholder_text("Password")
        self.password_entry.set_visibility(False)
        self.password_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.password_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-conceal-symbolic")
        self.password_entry.set_icon_activatable(Gtk.EntryIconPosition.SECONDARY, True)
        self.password_entry.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY, "Show/hide password")
        self.password_entry.connect("icon-press", self.on_icon_pressed)
        self.password_entry.connect("activate", lambda e: self.response("connect"))

        entry_box.append(self.password_entry)
        self.set_extra_child(entry_box)

        self.add_response("cancel", "Cancel")
        self.add_response("connect", "Connect")
        self.set_response_appearance("connect", Adw.ResponseAppearance.SUGGESTED)
        self.set_default_response("connect")
        self.password_entry.grab_focus()

    # Toggles the password's visibility when the user clicks the eye icon.
    def on_icon_pressed(self, entry, *args):
        is_visible = not entry.get_visibility()
        entry.set_visibility(is_visible)
        icon = "view-reveal-symbolic" if is_visible else "view-conceal-symbolic"
        entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, icon)

    # Returns the text currently in the password entry field.
    def get_password(self):
        return self.password_entry.get_text()

# This is the main widget that manages all WiFi functionality. It scans for networks,
# displays them, and handles turning the WiFi radio on and off.
# Now also includes Ethernet/LAN connection management.
class WiFiWidget(Gtk.Box):
    # Cache file path for persistent storage
    CACHE_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), '.wifi_cache.json')
    
    # Prepares the widget by setting up state variables and starting a background thread.
    # This thread runs shell commands so the user interface doesn't freeze.
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.connected_network = None
        self.available_networks = []
        self.wifi_enabled = False
        self.network_widgets = {}
        self.is_active = False
        self.update_timer_id = None
        self.scan_timer_id = None

        # Ethernet-related state variables
        self.connected_ethernet = None
        self.available_ethernet = []
        self.ethernet_widgets = {}

        # Data loading state
        self.wifi_data_loaded = False
        self.ethernet_data_loaded = False
        self._has_cached_data = False  # Track if we have any cached data to show
        self._is_loading = False  # Track if we're currently loading
        self._cache_dirty = False  # Track if cache needs saving
        self._pending_action = False  # Track if connect/disconnect is in progress

        # Load cache from file on startup
        self.load_cache_from_file()
        self.create_ui()
    
    def load_cache_from_file(self):
        """Load cached network data from file"""
        try:
            if os.path.exists(self.CACHE_FILE):
                with open(self.CACHE_FILE, 'r') as f:
                    cache_data = json.load(f)
                
                self.connected_network = cache_data.get('connected_network')
                self.available_networks = cache_data.get('available_networks', [])
                self.wifi_enabled = cache_data.get('wifi_enabled', False)
                self.connected_ethernet = cache_data.get('connected_ethernet')
                self.available_ethernet = cache_data.get('available_ethernet', [])
                self._has_cached_data = True
                print("WiFi cache loaded from file")
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading WiFi cache: {e}")
            self._has_cached_data = False
    
    def save_cache_to_file(self):
        """Save current network data to cache file (debounced)"""
        self._cache_dirty = True
    
    def _do_save_cache(self):
        """Actually write cache to file"""
        if not self._cache_dirty:
            return
        try:
            cache_data = {
                'connected_network': self.connected_network,
                'available_networks': self.available_networks,
                'wifi_enabled': self.wifi_enabled,
                'connected_ethernet': self.connected_ethernet,
                'available_ethernet': self.available_ethernet
            }
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(cache_data, f)
            self._cache_dirty = False
        except IOError as e:
            print(f"Error saving WiFi cache: {e}")

    # Starts the automatic updates when the widget becomes visible.
    def activate(self):
        if self.is_active: return
        self.is_active = True
        print("WiFiWidget Activated")
        
        # If we have cached data, show it immediately without spinner
        if self._has_cached_data:
            # Just show cached data, fetch updates silently in background
            self.wifi_data_loaded = True
            self.ethernet_data_loaded = True
            GLib.idle_add(self.update_ui)
            self.fetch_all_data(show_spinner=False)
        else:
            # First time load - show spinner
            self.fetch_all_data(show_spinner=True)
        
        if self.update_timer_id is None:
            self.update_timer_id = GLib.timeout_add_seconds(10, self.update_all_connections)
        if self.scan_timer_id is None:
            self.scan_timer_id = GLib.timeout_add_seconds(60, self.scan_networks)

    # Stops the automatic updates when the widget is hidden to save resources.
    def deactivate(self):
        if not self.is_active: return
        self.is_active = False
        print("WiFiWidget Deactivated")
        if self.update_timer_id: GLib.source_remove(self.update_timer_id); self.update_timer_id = None
        if self.scan_timer_id: GLib.source_remove(self.scan_timer_id); self.scan_timer_id = None
        # Save cache on deactivate
        self._do_save_cache()

    # Updates both WiFi and Ethernet connections periodically.
    def update_all_connections(self):
        if not self.is_active: return False
        self.fetch_all_data(show_spinner=False)  # No spinner on periodic updates
        return True

    # Fetch all data in a single background thread
    def fetch_all_data(self, show_spinner=False):
        # Skip if a connect/disconnect action is pending
        if self._pending_action:
            return
        
        # Prevent multiple simultaneous fetches
        if self._is_loading:
            return
        
        self._is_loading = True
        
        # Show spinning scan button
        GLib.idle_add(lambda: self.set_scan_button_loading(True))
        
        # Only show loading spinner on first load (no cached data)
        if show_spinner and not self._has_cached_data:
            GLib.idle_add(self.show_loading)
        
        def fetch_all():
            try:
                self.fetch_all_status()
            except Exception as e:
                print(f"Error fetching data: {e}")
            finally:
                GLib.idle_add(self._on_fetch_complete)
        
        threading.Thread(target=fetch_all, daemon=True).start()
    
    def fetch_all_status(self):
        """Fetch all WiFi and Ethernet status in one go - runs in background thread"""
        try:
            # Get radio status
            radio_output = subprocess.run("nmcli radio wifi", shell=True, capture_output=True, text=True, timeout=3).stdout.strip()
            self.wifi_enabled = radio_output == "enabled"
            
            # Get active connections (both wifi and ethernet)
            active_output = subprocess.run("nmcli -t -f NAME,TYPE,DEVICE c show --active", shell=True, capture_output=True, text=True, timeout=3).stdout.strip()
            
            # Parse active connections
            self.connected_network = None
            self.connected_ethernet = None
            for line in active_output.split('\n'):
                if not line.strip():
                    continue
                # Use rsplit to handle colons in connection names
                if ':802-11-wireless:' in line:
                    # Format: NAME:TYPE:DEVICE - split from right to handle colons in NAME
                    idx = line.find(':802-11-wireless:')
                    if idx > 0:
                        ssid = line[:idx]
                        self.connected_network = {'ssid': ssid, 'signal': 80, 'security': 'Connected'}
                elif ':802-3-ethernet:' in line:
                    idx = line.find(':802-3-ethernet:')
                    if idx > 0:
                        name = line[:idx]
                        device = line.split(':')[-1] if ':' in line else 'eth0'
                        self.connected_ethernet = {'name': name, 'device': device}
            
            # Get WiFi networks if enabled
            if self.wifi_enabled:
                # Use human-readable format which is easier to parse
                nets_output = subprocess.run("nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list", shell=True, capture_output=True, text=True, timeout=5).stdout.strip()
                self.available_networks = []
                seen = set()
                connected_ssid = self.connected_network['ssid'] if self.connected_network else None
                for line in nets_output.split('\n'):
                    if not line.strip():
                        continue
                    # nmcli -t uses : as separator, but SECURITY can have multiple values
                    # Format: SSID:SIGNAL:SECURITY (SECURITY may contain spaces but not colons usually)
                    # Split into max 3 parts from the right for signal and security
                    parts = line.split(':')
                    if len(parts) >= 2:
                        # SSID might contain colons, so join all but last 2 parts
                        if len(parts) > 3:
                            ssid = ':'.join(parts[:-2])
                            signal_str = parts[-2]
                            security = parts[-1]
                        elif len(parts) == 3:
                            ssid = parts[0]
                            signal_str = parts[1]
                            security = parts[2]
                        else:
                            ssid = parts[0]
                            signal_str = parts[1] if len(parts) > 1 else '0'
                            security = ''
                        
                        if not ssid or ssid in seen:
                            continue
                        
                        try:
                            signal = int(signal_str)
                        except:
                            signal = 0
                        
                        if ssid == connected_ssid:
                            # Update connected network signal
                            if self.connected_network:
                                self.connected_network['signal'] = signal
                        else:
                            seen.add(ssid)
                            self.available_networks.append({
                                'ssid': ssid, 
                                'signal': signal, 
                                'security': security if security else 'Open'
                            })
                self.available_networks.sort(key=lambda x: x['signal'], reverse=True)
            
            # Get available ethernet connections
            eth_output = subprocess.run("nmcli -t -f NAME,TYPE c show", shell=True, capture_output=True, text=True, timeout=3).stdout.strip()
            self.available_ethernet = []
            connected_eth_name = self.connected_ethernet['name'] if self.connected_ethernet else None
            for line in eth_output.split('\n'):
                if not line.strip():
                    continue
                if ':802-3-ethernet' in line:
                    idx = line.find(':802-3-ethernet')
                    conn_name = line[:idx] if idx > 0 else line.split(':')[0]
                    if conn_name and conn_name != connected_eth_name:
                        self.available_ethernet.append({'name': conn_name, 'device': 'ethernet'})
            
            self._has_cached_data = True
            self.save_cache_to_file()
        except Exception as e:
            print(f"Error in fetch_all_status: {e}")
    
    def _on_fetch_complete(self):
        """Called on main thread when fetch completes"""
        self._is_loading = False
        self.wifi_data_loaded = True
        self.ethernet_data_loaded = True
        self.set_scan_button_loading(False)
        self.update_ui_after_data_fetch()

    def update_ui_after_data_fetch(self):
        """Update UI after all data has been fetched"""
        try:
            # Update WiFi switch state
            self.wifi_switch.handler_block_by_func(self.on_wifi_toggled)
            self.wifi_switch.set_active(self.wifi_enabled)
            self.wifi_switch.handler_unblock_by_func(self.on_wifi_toggled)
            
            # Update the main UI
            self.update_ui()
        except Exception as e:
            print(f"Error updating UI after data fetch: {e}")

    def show_loading(self):
        """Show loading spinner while data is being fetched"""
        try:
            # Clear existing content
            while child := self.content_box.get_first_child():
                self.content_box.remove(child)
            self.network_widgets.clear()
            self.ethernet_widgets.clear()
            
            # Show loading spinner
            loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                                  halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                                  vexpand=True)
            
            spinner = Gtk.Spinner(spinning=True, width_request=32, height_request=32)
            loading_label = Gtk.Label(label="Loading network information...", css_classes=["dim-label"])
            
            loading_box.append(spinner)
            loading_box.append(loading_label)
            self.content_box.append(loading_box)
        except Exception as e:
            print(f"Error showing loading state: {e}")

    def show_error(self, title, message):
        """Show error message"""
        try:
            # Clear existing content
            while child := self.content_box.get_first_child():
                self.content_box.remove(child)
            self.network_widgets.clear()
            self.ethernet_widgets.clear()
            
            error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                                halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                                vexpand=True)
            
            error_icon = Gtk.Image(icon_name="dialog-error-symbolic")
            error_icon.set_pixel_size(48)
            error_title = Gtk.Label(label=title, css_classes=["title-label"])
            error_message = Gtk.Label(label=message, css_classes=["dim-label"])
            
            error_box.append(error_icon)
            error_box.append(error_title)
            error_box.append(error_message)
            self.content_box.append(error_box)
        except Exception as e:
            print(f"Error showing error state: {e}")

    # Constructs the main user interface for the WiFi widget, including the header,
    # on/off switch, and the area where networks will be listed.
    def create_ui(self):
        self.set_margin_top(15); self.set_margin_bottom(15); self.set_margin_start(15); self.set_margin_end(15)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12); header_box.set_margin_bottom(16)
        title_label = Gtk.Label(label="WiFi"); title_label.add_css_class("title-large"); title_label.set_hexpand(True); title_label.set_halign(Gtk.Align.START)
        self.wifi_switch = Gtk.Switch(); self.wifi_switch.set_valign(Gtk.Align.CENTER)
        # Apply pink theme to switch
        ensure_pink_switch_css()
        self.wifi_switch.add_css_class("pink-toggle")
        self.wifi_switch.connect("notify::active", self.on_wifi_toggled)
        self.scan_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Scan for networks"); self.scan_button.add_css_class("circular"); self.scan_button.connect("clicked", lambda b: self.scan_networks())
        header_box.append(title_label); header_box.append(self.scan_button); header_box.append(self.wifi_switch)
        scrolled_window = Gtk.ScrolledWindow(); scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); scrolled_window.set_vexpand(True); scrolled_window.add_css_class("invisible-scroll")
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); scrolled_window.set_child(self.content_box)
        self.append(header_box); self.append(scrolled_window)
        
        # Display cached data if available, otherwise will show loading when activated
        if self._has_cached_data:
            self.wifi_switch.set_active(self.wifi_enabled)
            self.wifi_data_loaded = True
            self.ethernet_data_loaded = True
            self.update_ui()
    
    def set_scan_button_loading(self, loading):
        """Set scan button to spinning/loading state"""
        if loading:
            self.scan_button.add_css_class("refresh-spinning")
            self.scan_button.set_sensitive(False)
        else:
            self.scan_button.remove_css_class("refresh-spinning")
            self.scan_button.set_sensitive(True)

    # A simple helper to run a command and return its output.
    def run_wifi_command(self, command, timeout=15):
        try:
            # Use shell=True for commands with pipes, quotes, and special characters
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            return ""

    # Legacy methods kept for compatibility but now use threaded approach
    def update_wifi_status(self):
        # This is now handled by fetch_all_data()
        pass

    def update_ethernet_status(self):
        # This is now handled by fetch_all_data()
        pass

    def update_networks(self):
        # This is now handled by fetch_all_data()
        pass

    # Processes the raw text output from the `nmcli` command into a clean list of networks.
    def parse_networks_output(self, output):
        networks, seen_ssids = [], set()
        for line in output.split('\n')[1:]:
            match = re.match(r'^\s*(\S.*?)\s+(\d+)\s+(.+?)\s*$', line.strip())
            if match:
                ssid, signal, security = match.groups()
                if ssid and ssid != '--' and ssid not in seen_ssids:
                    seen_ssids.add(ssid)
                    networks.append({'ssid': ssid, 'signal': int(signal), 'security': security.strip()})
        return sorted(networks, key=lambda x: x['signal'], reverse=True)

    # Sends a command to tell the system to scan for WiFi networks.
    def scan_networks(self):
        if self.wifi_enabled:
            self.set_scan_button_loading(True)
            def do_scan():
                self.run_wifi_command("nmcli dev wifi rescan")
                GLib.idle_add(lambda: self.fetch_all_data(show_spinner=False) or False)
            threading.Thread(target=do_scan, daemon=True).start()
        return True

    # This function is called when the user clicks the main WiFi on/off switch.
    def on_wifi_toggled(self, switch, *args):
        cmd = f"nmcli radio wifi {'on' if switch.get_active() else 'off'}"
        def do_toggle():
            self.run_wifi_command(cmd)
            GLib.timeout_add(500, lambda: self.fetch_all_data(show_spinner=False) or False)
        threading.Thread(target=do_toggle, daemon=True).start()

    # Checks if a saved connection profile already exists for a given network SSID.
    def does_connection_exist(self, ssid):
        return ssid in self.run_wifi_command("nmcli -t -f NAME c").split('\n')

    # Creates the correct shell command to connect to a new password-protected network.
    def get_connect_and_save_command(self, ssid, password):
        return f"nmcli device wifi connect '{ssid}' password '{password}'"

    # This is triggered when a user clicks the "Connect" or "Disconnect" button for a network.
    def on_network_connect(self, network_info, connect=True):
        ssid = network_info['ssid']
        widget = self.network_widgets.get(ssid)
        if widget: widget.set_loading(True)
        
        # Set pending flag to prevent background refresh from interfering
        self._pending_action = True

        if connect:
            is_open = network_info.get('security', '') in ['Open', '--', '']
            if is_open:
                cmd = f"nmcli dev wifi connect '{ssid}'"
            elif self.does_connection_exist(ssid):
                print(f"Connecting to saved network: {ssid}")
                cmd = f"nmcli c up '{ssid}'"
            else:
                if widget: widget.set_loading(False)
                self._pending_action = False
                self.show_password_dialog(ssid)
                return
            
            # Optimistic UI update - show as connected immediately
            self.connected_network = {'ssid': ssid, 'signal': network_info.get('signal', 80), 'security': 'Connected'}
            self.available_networks = [n for n in self.available_networks if n['ssid'] != ssid]
        else:
            cmd = f"nmcli c down '{ssid}'"
            # Optimistic UI update - show as disconnected immediately
            if self.connected_network and self.connected_network.get('ssid') == ssid:
                # Move to available networks with original security type
                orig_security = network_info.get('security', 'WPA2')
                if orig_security == 'Connected':
                    orig_security = 'WPA2'  # Default for previously connected
                self.available_networks.insert(0, {
                    'ssid': ssid, 
                    'signal': network_info.get('signal', 80), 
                    'security': orig_security
                })
                self.connected_network = None
        
        # Update UI immediately
        self.update_ui()

        def do_action():
            try:
                subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            except Exception as e:
                print(f"WiFi command error: {e}")
            finally:
                # Always refresh after command completes
                def finish():
                    self._pending_action = False
                    self.fetch_all_data(show_spinner=False)
                    return False
                GLib.timeout_add(300, finish)  # Small delay for nmcli to settle
        threading.Thread(target=do_action, daemon=True).start()

    # This is triggered when a user clicks the "Connect" or "Disconnect" button for an Ethernet connection.
    def on_ethernet_connect(self, connection_info, connect=True):
        conn_name = connection_info['name']
        widget = self.ethernet_widgets.get(conn_name)
        if widget: widget.set_loading(True)
        
        # Set pending flag
        self._pending_action = True

        if connect:
            # Optimistic UI update
            self.connected_ethernet = connection_info
            self.available_ethernet = [e for e in self.available_ethernet if e['name'] != conn_name]
        else:
            # Optimistic UI update
            if self.connected_ethernet and self.connected_ethernet.get('name') == conn_name:
                self.available_ethernet.insert(0, connection_info)
                self.connected_ethernet = None
        
        # Update UI immediately
        self.update_ui()

        cmd = f"nmcli c up '{conn_name}'" if connect else f"nmcli c down '{conn_name}'"
        
        def do_action():
            try:
                subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            except Exception as e:
                print(f"Ethernet command error: {e}")
            finally:
                def finish():
                    self._pending_action = False
                    self.fetch_all_data(show_spinner=False)
                    return False
                GLib.timeout_add(300, finish)
        threading.Thread(target=do_action, daemon=True).start()

    # Creates and displays the password dialog for a specific network.
    def show_password_dialog(self, ssid):
        dialog = WiFiPasswordDialog(self.get_root(), ssid)
        dialog.connect("response", self.on_password_dialog_response, ssid)
        dialog.present()

    # Handles the response from the password dialog (e.g., user clicked "Connect").
    def on_password_dialog_response(self, dialog, response, ssid):
        if response == "connect":
            password = dialog.get_password()
            if password:
                # Set pending flag
                self._pending_action = True
                
                # Find network info for optimistic update
                network_info = next((n for n in self.available_networks if n['ssid'] == ssid), None)
                
                widget = self.network_widgets.get(ssid)
                if widget: widget.set_loading(True)
                
                # Optimistic UI update
                if network_info:
                    self.connected_network = {'ssid': ssid, 'signal': network_info.get('signal', 80), 'security': 'Connected'}
                    self.available_networks = [n for n in self.available_networks if n['ssid'] != ssid]
                    self.update_ui()
                
                connect_cmd = self.get_connect_and_save_command(ssid, password)
                def do_connect():
                    try:
                        subprocess.run(connect_cmd, shell=True, capture_output=True, text=True, timeout=15)
                    except Exception as e:
                        print(f"WiFi connect error: {e}")
                    finally:
                        def finish():
                            self._pending_action = False
                            self.fetch_all_data(show_spinner=False)
                            return False
                        GLib.timeout_add(300, finish)
                threading.Thread(target=do_connect, daemon=True).start()
        dialog.destroy()

    # Clears and redraws the list of network widgets based on the latest scan data.
    # Now also includes Ethernet connections in the same widget.
    def update_ui(self):
        # Don't update UI if we're still loading data
        if not self.wifi_data_loaded or not self.ethernet_data_loaded:
            return
            
        while child := self.content_box.get_first_child():
            self.content_box.remove(child)
        self.network_widgets.clear()
        self.ethernet_widgets.clear()
        
        # Show connected WiFi network
        if self.connected_network:
            self.content_box.append(Gtk.Label(label="Connected WiFi Network", xalign=0, css_classes=["section-title"]))
            widget = WiFiNetworkWidget(self.connected_network, is_connected=True)
            widget.connect_btn.connect("clicked", lambda b, n=self.connected_network: self.on_network_connect(n, connect=True))
            widget.disconnect_btn.connect("clicked", lambda b, n=self.connected_network: self.on_network_connect(n, connect=False))
            self.network_widgets[self.connected_network['ssid']] = widget
            self.content_box.append(widget)

        # Show connected Ethernet connection
        if self.connected_ethernet:
            margin_top = 16 if self.connected_network else 0
            self.content_box.append(Gtk.Label(label="Connected Ethernet", xalign=0, css_classes=["section-title"], margin_top=margin_top))
            widget = EthernetConnectionWidget(self.connected_ethernet, is_connected=True)
            widget.connect_btn.connect("clicked", lambda b, n=self.connected_ethernet: self.on_ethernet_connect(n, connect=True))
            widget.disconnect_btn.connect("clicked", lambda b, n=self.connected_ethernet: self.on_ethernet_connect(n, connect=False))
            self.ethernet_widgets[self.connected_ethernet['name']] = widget
            self.content_box.append(widget)

        # Show available WiFi networks if WiFi is enabled
        if self.wifi_enabled and self.available_networks:
            margin_top = 16 if (self.connected_network or self.connected_ethernet) else 0
            self.content_box.append(Gtk.Label(label="Available WiFi Networks", xalign=0, css_classes=["section-title"], margin_top=margin_top))
            for network in self.available_networks:
                widget = WiFiNetworkWidget(network)
                widget.connect_btn.connect("clicked", lambda b, n=network: self.on_network_connect(n, connect=True))
                widget.disconnect_btn.connect("clicked", lambda b, n=network: self.on_network_connect(n, connect=False))
                self.network_widgets[network['ssid']] = widget
                self.content_box.append(widget)

        # Show available Ethernet connections
        if self.available_ethernet:
            margin_top = 16 if (self.connected_network or self.connected_ethernet or (self.wifi_enabled and self.available_networks)) else 0
            self.content_box.append(Gtk.Label(label="Available Ethernet Connections", xalign=0, css_classes=["section-title"], margin_top=margin_top))
            for connection in self.available_ethernet:
                widget = EthernetConnectionWidget(connection)
                widget.connect_btn.connect("clicked", lambda b, n=connection: self.on_ethernet_connect(n, connect=True))
                widget.disconnect_btn.connect("clicked", lambda b, n=connection: self.on_ethernet_connect(n, connect=False))
                self.ethernet_widgets[connection['name']] = widget
                self.content_box.append(widget)
        
        # Show appropriate placeholders if nothing is available
        if not self.wifi_enabled:
            if not self.connected_ethernet and not self.available_ethernet:
                self.show_wifi_disabled()
        elif not self.connected_network and not self.available_networks and not self.connected_ethernet and not self.available_ethernet:
            self.show_no_networks()

    # A general function to display a placeholder message with an icon and text.
    def show_placeholder(self, icon_name, title, subtitle):
        while child := self.content_box.get_first_child(): self.content_box.remove(child)
        placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, vexpand=True, valign=Gtk.Align.CENTER, css_classes=["dim-label"])
        placeholder.append(Gtk.Image.new_from_icon_name(icon_name))
        placeholder.append(Gtk.Label(label=title, css_classes=["title-large"]))
        placeholder.append(Gtk.Label(label=subtitle))
        for child in placeholder: child.set_pixel_size(64) if isinstance(child, Gtk.Image) else None
        self.content_box.append(placeholder)
        
    # Shows a specific message for when no WiFi networks are found.
    def show_no_networks(self):
        self.show_placeholder("network-wireless-symbolic", "No Networks Found", "Try clicking the scan button or check ethernet connections")

    # Shows a specific message for when the WiFi radio is turned off.
    def show_wifi_disabled(self):
        self.show_placeholder("network-wireless-disabled-symbolic", "WiFi is Disabled", "Enable WiFi to see available networks")

# The main window of the application that holds the WiFi widget.
class MainWindow(Gtk.ApplicationWindow):
    # Sets up the window and places the main WiFiWidget inside it.
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("WiFi Manager")
        self.set_default_size(420, 600)

        self.wifi_widget = WiFiWidget()

        toolbar_view = Adw.ToolbarView()
        header_bar = Adw.HeaderBar()
        toolbar_view.add_top_bar(header_bar)
        toolbar_view.set_content(self.wifi_widget)

        self.set_content(toolbar_view)
        
        self.connect("map", self.on_map)
        self.connect("unmap", self.on_unmap)

    # Activates the WiFi widget's updates when the window is shown.
    def on_map(self, *args):
        self.wifi_widget.activate()

    # Deactivates the WiFi widget's updates when the window is hidden or closed.
    def on_unmap(self, *args):
        self.wifi_widget.deactivate()