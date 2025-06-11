import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango
import subprocess
import re
import threading
import queue
import sys
import warnings

warnings.filterwarnings("ignore")

# This class defines a custom GTK widget to display a single WiFi network.
# It shows the network name, signal strength, and a button to connect or disconnect.
class WiFiNetworkWidget(Gtk.Box):
    # Sets up the widget with the specific network's information.
    def __init__(self, network_info, is_connected=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.network_info = network_info
        self.is_connected = is_connected
        self.is_loading = False
        self.create_ui()

    # Builds the visual elements of the widget, like the icon, labels, and button.
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
        self.connect_button = Gtk.Button()
        self.connect_button.set_size_request(90, 36)
        self.connect_button.add_css_class("action-button")

        if self.is_connected:
            self.connect_button.set_label("Disconnect")
            self.connect_button.add_css_class("destructive-action")
        else:
            self.connect_button.set_label("Connect")
            self.connect_button.add_css_class("suggested-action")

        button_box.append(self.spinner)
        button_box.append(self.connect_button)

        self.append(signal_icon)
        self.append(info_box)
        self.append(button_box)

    # Shows or hides a loading spinner and disables the button during connection attempts.
    def set_loading(self, loading):
        self.is_loading = loading
        self.spinner.set_visible(loading)
        if loading:
            self.spinner.start()
            self.connect_button.set_sensitive(False)
            self.connect_button.set_label("...")
            status_prefix = "Connecting" if not self.is_connected else "Disconnecting"
            self.status_label.set_text(f"{status_prefix}...")
        else:
            self.spinner.stop()
            self.connect_button.set_sensitive(True)
            signal = self.network_info.get('signal', 0)
            if self.is_connected:
                self.connect_button.set_label("Disconnect")
                self.status_label.set_text(f"Connected • {signal}% signal")
            else:
                self.connect_button.set_label("Connect")
                security = self.network_info.get('security', 'Open')
                self.status_label.set_text(f"{security} • {signal}% signal")

    # Selects the appropriate WiFi icon based on signal strength percentage.
    def get_signal_icon(self, strength):
        if strength >= 75: return "network-wireless-signal-excellent-symbolic"
        if strength >= 50: return "network-wireless-signal-good-symbolic"
        if strength >= 25: return "network-wireless-signal-ok-symbolic"
        return "network-wireless-signal-weak-symbolic"

# This class defines a custom GTK widget to display Ethernet connections.
# It shows the connection name, status, and a button to connect or disconnect.
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
        self.connect_button = Gtk.Button()
        self.connect_button.set_size_request(90, 36)
        self.connect_button.add_css_class("action-button")

        if self.is_connected:
            self.connect_button.set_label("Disconnect")
            self.connect_button.add_css_class("destructive-action")
        else:
            self.connect_button.set_label("Connect")
            self.connect_button.add_css_class("suggested-action")

        button_box.append(self.spinner)
        button_box.append(self.connect_button)

        self.append(ethernet_icon)
        self.append(info_box)
        self.append(button_box)

    # Shows or hides a loading spinner and disables the button during connection attempts.
    def set_loading(self, loading):
        self.is_loading = loading
        self.spinner.set_visible(loading)
        if loading:
            self.spinner.start()
            self.connect_button.set_sensitive(False)
            self.connect_button.set_label("...")
            status_prefix = "Connecting" if not self.is_connected else "Disconnecting"
            self.status_label.set_text(f"{status_prefix}...")
        else:
            self.spinner.stop()
            self.connect_button.set_sensitive(True)
            if self.is_connected:
                self.connect_button.set_label("Disconnect")
                self.status_label.set_text("Connected • Wired")
            else:
                self.connect_button.set_label("Connect")
                self.status_label.set_text(f"Available • {self.connection_info.get('device', 'Unknown device')}")

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
    # Prepares the widget by setting up state variables and starting a background thread.
    # This thread runs shell commands so the user interface doesn't freeze.
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.connected_network = None
        self.available_networks = []
        self.wifi_enabled = False
        self.network_widgets = {}
        self.command_queue = queue.Queue()
        self.is_active = False
        self.update_timer_id = None
        self.scan_timer_id = None

        # Ethernet-related state variables
        self.connected_ethernet = None
        self.available_ethernet = []
        self.ethernet_widgets = {}

        self.command_thread = threading.Thread(target=self.command_worker, daemon=True)
        self.command_thread.start()
        self.create_ui()

    # Starts the automatic updates when the widget becomes visible.
    def activate(self):
        if self.is_active: return
        self.is_active = True
        print("WiFiWidget Activated")
        self.update_wifi_status()
        self.update_ethernet_status()
        if self.update_timer_id is None:
            self.update_timer_id = GLib.timeout_add_seconds(5, self.update_all_connections)
        if self.scan_timer_id is None:
            self.scan_timer_id = GLib.timeout_add_seconds(20, self.scan_networks)

    # Stops the automatic updates when the widget is hidden to save resources.
    def deactivate(self):
        if not self.is_active: return
        self.is_active = False
        print("WiFiWidget Deactivated")
        if self.update_timer_id: GLib.source_remove(self.update_timer_id); self.update_timer_id = None
        if self.scan_timer_id: GLib.source_remove(self.scan_timer_id); self.scan_timer_id = None

    # Updates both WiFi and Ethernet connections periodically.
    def update_all_connections(self):
        if not self.is_active: return False
        self.update_wifi_status()
        self.update_ethernet_status()
        return True

    # This function runs in a separate thread, executing shell commands from a queue.
    # This prevents the main application from freezing while waiting for commands to finish.
    def command_worker(self):
        while True:
            try:
                command = self.command_queue.get()
                print(f"Executing: {command}")
                result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=25)
                if result.returncode != 0:
                    print(f"Error: {result.stderr.strip()}")
                else:
                    print(f"Success: {result.stdout.strip()}")
                self.command_queue.task_done()
            except Exception as e:
                print(f"Command worker exception: {e}")

    # Constructs the main user interface for the WiFi widget, including the header,
    # on/off switch, and the area where networks will be listed.
    def create_ui(self):
        self.set_margin_top(15); self.set_margin_bottom(15); self.set_margin_start(15); self.set_margin_end(15)
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12); header_box.set_margin_bottom(16)
        title_label = Gtk.Label(label="WiFi"); title_label.add_css_class("title-large"); title_label.set_hexpand(True); title_label.set_halign(Gtk.Align.START)
        self.wifi_switch = Gtk.Switch(); self.wifi_switch.set_valign(Gtk.Align.CENTER); self.wifi_switch.connect("notify::active", self.on_wifi_toggled)
        scan_button = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text="Scan for networks"); scan_button.add_css_class("circular"); scan_button.connect("clicked", lambda b: self.scan_networks())
        header_box.append(title_label); header_box.append(scan_button); header_box.append(self.wifi_switch)
        scrolled_window = Gtk.ScrolledWindow(); scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC); scrolled_window.set_vexpand(True); scrolled_window.add_css_class("invisible-scroll")
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8); scrolled_window.set_child(self.content_box)
        self.append(header_box); self.append(scrolled_window)

    # A simple helper to run a shell command and return its output.
    def run_wifi_command(self, command):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            print(f"Run command error: {e}")
            return ""

    # Checks if the computer's WiFi is enabled or disabled and updates the UI accordingly.
    def update_wifi_status(self):
        if not self.is_active: return False
        radio_output = self.run_wifi_command("nmcli radio wifi")
        self.wifi_enabled = radio_output.strip() == "enabled"
        self.wifi_switch.handler_block_by_func(self.on_wifi_toggled)
        self.wifi_switch.set_active(self.wifi_enabled)
        self.wifi_switch.handler_unblock_by_func(self.on_wifi_toggled)
        if self.wifi_enabled:
            GLib.idle_add(self.update_networks)
        else:
            GLib.idle_add(self.update_ui)
        return True

    # Updates the Ethernet connection status and available connections.
    def update_ethernet_status(self):
        if not self.is_active: return
        
        # Get active Ethernet connections
        active_conn = self.run_wifi_command("nmcli -t -f NAME,TYPE,DEVICE c show --active")
        current_ethernet = None
        for line in active_conn.split('\n'):
            if ':802-3-ethernet:' in line:
                parts = line.split(':')
                if len(parts) >= 3:
                    current_ethernet = {'name': parts[0], 'device': parts[2]}
                    break
        
        self.connected_ethernet = current_ethernet
        
        # Get all Ethernet connections
        all_conns_output = self.run_wifi_command("nmcli -t -f NAME,TYPE c show")
        self.available_ethernet = []
        for line in all_conns_output.split('\n'):
            if ':802-3-ethernet' in line:
                conn_name = line.split(':')[0]
                if not current_ethernet or conn_name != current_ethernet['name']:
                    # Get available Ethernet devices
                    devices_output = self.run_wifi_command("nmcli -t -f DEVICE,TYPE,STATE device status")
                    device_name = "Unknown device"
                    for device_line in devices_output.split('\n'):
                        if ':ethernet:' in device_line:
                            device_name = device_line.split(':')[0]
                            break
                    self.available_ethernet.append({'name': conn_name, 'device': device_name})
        
        GLib.idle_add(self.update_ui)

    # Fetches the current connected network and a list of all other available networks.
    def update_networks(self):
        active_conn = self.run_wifi_command("nmcli -t -f NAME,TYPE,DEVICE c show --active")
        current_name = next((line.split(':')[0] for line in active_conn.split('\n') if ':802-11-wireless:' in line), None)
        
        self.connected_network = None
        if current_name:
            signal_out = self.run_wifi_command(f"nmcli -t -f SSID,SIGNAL dev wifi | grep '^{re.escape(current_name)}:' | cut -d: -f2 | head -n1")
            self.connected_network = {'ssid': current_name, 'signal': int(signal_out) if signal_out.isdigit() else 50, 'security': 'Connected'}

        all_nets_out = self.run_wifi_command("nmcli -f SSID,SIGNAL,SECURITY dev wifi")
        self.available_networks = self.parse_networks_output(all_nets_out)
        
        if self.connected_network:
            self.available_networks = [n for n in self.available_networks if n['ssid'] != self.connected_network['ssid']]
        
        self.update_ui()

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
        if self.wifi_enabled: self.command_queue.put("nmcli dev wifi rescan")
        return True

    # This function is called when the user clicks the main WiFi on/off switch.
    def on_wifi_toggled(self, switch, *args):
        self.command_queue.put(f"nmcli radio wifi {'on' if switch.get_active() else 'off'}")

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

        if connect:
            is_open = network_info.get('security', '') in ['Open', '--', '']
            if is_open:
                self.command_queue.put(f"nmcli dev wifi connect '{ssid}'")
            elif self.does_connection_exist(ssid):
                print(f"Connecting to saved network: {ssid}")
                self.command_queue.put(f"nmcli c up '{ssid}'")
            else:
                if widget: widget.set_loading(False)
                self.show_password_dialog(ssid)
                return
        else:
            self.command_queue.put(f"nmcli c down '{ssid}'")

        GLib.timeout_add_seconds(8, self.update_wifi_status)

    # This is triggered when a user clicks the "Connect" or "Disconnect" button for an Ethernet connection.
    def on_ethernet_connect(self, connection_info, connect=True):
        conn_name = connection_info['name']
        widget = self.ethernet_widgets.get(conn_name)
        if widget: widget.set_loading(True)

        if connect:
            self.command_queue.put(f"nmcli c up '{conn_name}'")
        else:
            self.command_queue.put(f"nmcli c down '{conn_name}'")

        GLib.timeout_add_seconds(5, self.update_ethernet_status_callback)

    # Callback for updating Ethernet status after connection attempts.
    def update_ethernet_status_callback(self):
        self.update_ethernet_status()
        return False

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
                widget = self.network_widgets.get(ssid)
                if widget: widget.set_loading(True)
                connect_cmd = self.get_connect_and_save_command(ssid, password)
                self.command_queue.put(connect_cmd)
                GLib.timeout_add_seconds(12, self.update_wifi_status)
        dialog.destroy()

    # Clears and redraws the list of network widgets based on the latest scan data.
    # Now also includes Ethernet connections in the same widget.
    def update_ui(self):
        while child := self.content_box.get_first_child():
            self.content_box.remove(child)
        self.network_widgets.clear()
        self.ethernet_widgets.clear()
        
        # Show connected WiFi network
        if self.connected_network:
            self.content_box.append(Gtk.Label(label="Connected WiFi Network", xalign=0, css_classes=["section-title"]))
            widget = WiFiNetworkWidget(self.connected_network, is_connected=True)
            widget.connect_button.connect("clicked", lambda b, n=self.connected_network: self.on_network_connect(n, connect=False))
            self.network_widgets[self.connected_network['ssid']] = widget
            self.content_box.append(widget)

        # Show connected Ethernet connection
        if self.connected_ethernet:
            margin_top = 16 if self.connected_network else 0
            self.content_box.append(Gtk.Label(label="Connected Ethernet", xalign=0, css_classes=["section-title"], margin_top=margin_top))
            widget = EthernetConnectionWidget(self.connected_ethernet, is_connected=True)
            widget.connect_button.connect("clicked", lambda b, n=self.connected_ethernet: self.on_ethernet_connect(n, connect=False))
            self.ethernet_widgets[self.connected_ethernet['name']] = widget
            self.content_box.append(widget)

        # Show available WiFi networks if WiFi is enabled
        if self.wifi_enabled and self.available_networks:
            margin_top = 16 if (self.connected_network or self.connected_ethernet) else 0
            self.content_box.append(Gtk.Label(label="Available WiFi Networks", xalign=0, css_classes=["section-title"], margin_top=margin_top))
            for network in self.available_networks:
                widget = WiFiNetworkWidget(network)
                widget.connect_button.connect("clicked", lambda b, n=network: self.on_network_connect(n, connect=True))
                self.network_widgets[network['ssid']] = widget
                self.content_box.append(widget)

        # Show available Ethernet connections
        if self.available_ethernet:
            margin_top = 16 if (self.connected_network or self.connected_ethernet or (self.wifi_enabled and self.available_networks)) else 0
            self.content_box.append(Gtk.Label(label="Available Ethernet Connections", xalign=0, css_classes=["section-title"], margin_top=margin_top))
            for connection in self.available_ethernet:
                widget = EthernetConnectionWidget(connection)
                widget.connect_button.connect("clicked", lambda b, n=connection: self.on_ethernet_connect(n, connect=True))
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