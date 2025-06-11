#!/usr/bin/env python3

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

# Ignore benign warnings from gi
warnings.filterwarnings("ignore")

class WiFiNetworkWidget(Gtk.Box):
    """A widget to display information about a single WiFi network."""
    def __init__(self, network_info, is_connected=False):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.network_info = network_info
        self.is_connected = is_connected
        self.is_loading = False
        self.create_ui()

    def create_ui(self):
        self.add_css_class("info-tile")
        self.set_margin_top(4)
        self.set_margin_bottom(4)

        # WiFi signal icon
        signal_strength = self.network_info.get('signal', 0)
        icon_name = self.get_signal_icon(signal_strength)
        signal_icon = Gtk.Image.new_from_icon_name(icon_name)
        signal_icon.set_pixel_size(32)

        # Network info box
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)

        # Network name with security indicator
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

        # Status and signal info label
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

        # Connection button with loading spinner
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

    def set_loading(self, loading):
        """Show/hide loading spinner and update button state."""
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
            # Restore original labels
            signal = self.network_info.get('signal', 0)
            if self.is_connected:
                self.connect_button.set_label("Disconnect")
                self.status_label.set_text(f"Connected • {signal}% signal")
            else:
                self.connect_button.set_label("Connect")
                security = self.network_info.get('security', 'Open')
                self.status_label.set_text(f"{security} • {signal}% signal")

    def get_signal_icon(self, strength):
        if strength >= 75: return "network-wireless-signal-excellent-symbolic"
        if strength >= 50: return "network-wireless-signal-good-symbolic"
        if strength >= 25: return "network-wireless-signal-ok-symbolic"
        return "network-wireless-signal-weak-symbolic"

class WiFiPasswordDialog(Adw.MessageDialog):
    """A dialog to ask the user for a WiFi password."""
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

    def on_icon_pressed(self, entry, *args):
        is_visible = not entry.get_visibility()
        entry.set_visibility(is_visible)
        icon = "view-reveal-symbolic" if is_visible else "view-conceal-symbolic"
        entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, icon)

    def get_password(self):
        return self.password_entry.get_text()

class WiFiWidget(Gtk.Box):
    """The main widget for managing WiFi connections."""
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

        self.command_thread = threading.Thread(target=self.command_worker, daemon=True)
        self.command_thread.start()
        self.create_ui()

    def activate(self):
        if self.is_active: return
        self.is_active = True
        print("WiFiWidget Activated")
        self.update_wifi_status()
        if self.update_timer_id is None:
            self.update_timer_id = GLib.timeout_add_seconds(5, self.update_wifi_status)
        if self.scan_timer_id is None:
            self.scan_timer_id = GLib.timeout_add_seconds(20, self.scan_networks)

    def deactivate(self):
        if not self.is_active: return
        self.is_active = False
        print("WiFiWidget Deactivated")
        if self.update_timer_id: GLib.source_remove(self.update_timer_id); self.update_timer_id = None
        if self.scan_timer_id: GLib.source_remove(self.scan_timer_id); self.scan_timer_id = None

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

    def run_wifi_command(self, command):
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            print(f"Run command error: {e}")
            return ""

    def update_wifi_status(self):
        if not self.is_active: return False
        radio_output = self.run_wifi_command("nmcli radio wifi")
        self.wifi_enabled = radio_output.strip() == "enabled"
        self.wifi_switch.handler_block_by_func(self.on_wifi_toggled)
        self.wifi_switch.set_active(self.wifi_enabled)
        self.wifi_switch.handler_unblock_by_func(self.on_wifi_toggled)
        GLib.idle_add(self.update_networks if self.wifi_enabled else self.show_wifi_disabled)
        return True

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

    def scan_networks(self):
        if self.wifi_enabled: self.command_queue.put("nmcli dev wifi rescan")
        return True

    def on_wifi_toggled(self, switch, *args):
        self.command_queue.put(f"nmcli radio wifi {'on' if switch.get_active() else 'off'}")

    def does_connection_exist(self, ssid):
        return ssid in self.run_wifi_command("nmcli -t -f NAME c").split('\n')

    def get_connect_and_save_command(self, ssid, password):
        # This is the most reliable method. It creates a persistent connection
        # that NetworkManager saves, handling security details automatically.
        return f"nmcli device wifi connect '{ssid}' password '{password}'"

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
                if widget: widget.set_loading(False) # Stop loading while dialog is open
                self.show_password_dialog(ssid)
                return
        else:
            self.command_queue.put(f"nmcli c down '{ssid}'")

        GLib.timeout_add_seconds(8, self.update_wifi_status)

    def show_password_dialog(self, ssid):
        dialog = WiFiPasswordDialog(self.get_root(), ssid)
        dialog.connect("response", self.on_password_dialog_response, ssid)
        dialog.present()

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

    def update_ui(self):
        # Clear previous widgets
        while child := self.content_box.get_first_child():
            self.content_box.remove(child)
        self.network_widgets.clear()
        
        # Add connected network section
        if self.connected_network:
            self.content_box.append(Gtk.Label(label="Connected Network", xalign=0, css_classes=["section-title"]))
            widget = WiFiNetworkWidget(self.connected_network, is_connected=True)
            widget.connect_button.connect("clicked", lambda b, n=self.connected_network: self.on_network_connect(n, connect=False))
            self.network_widgets[self.connected_network['ssid']] = widget
            self.content_box.append(widget)

        # Add available networks section
        if self.available_networks:
            self.content_box.append(Gtk.Label(label="Available Networks", xalign=0, css_classes=["section-title"], margin_top=16 if self.connected_network else 0))
            for network in self.available_networks:
                widget = WiFiNetworkWidget(network)
                widget.connect_button.connect("clicked", lambda b, n=network: self.on_network_connect(n, connect=True))
                self.network_widgets[network['ssid']] = widget
                self.content_box.append(widget)
        
        if not self.connected_network and not self.available_networks:
            self.show_no_networks()

    def show_placeholder(self, icon_name, title, subtitle):
        while child := self.content_box.get_first_child(): self.content_box.remove(child)
        placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, vexpand=True, valign=Gtk.Align.CENTER, css_classes=["dim-label"])
        placeholder.append(Gtk.Image.new_from_icon_name(icon_name))
        placeholder.append(Gtk.Label(label=title, css_classes=["title-large"]))
        placeholder.append(Gtk.Label(label=subtitle))
        for child in placeholder: child.set_pixel_size(64) if isinstance(child, Gtk.Image) else None
        self.content_box.append(placeholder)
        
    def show_no_networks(self):
        self.show_placeholder("network-wireless-symbolic", "No WiFi Networks Found", "Try clicking the scan button")

    def show_wifi_disabled(self):
        self.show_placeholder("network-wireless-disabled-symbolic", "WiFi is Disabled", "Enable WiFi to see available networks")

class MainWindow(Gtk.ApplicationWindow):
    """The main application window."""
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
        
        # When the window is shown, activate the widget's timers
        self.connect("map", self.on_map)
        # When the window is closed/hidden, deactivate them
        self.connect("unmap", self.on_unmap)

    def on_map(self, *args):
        self.wifi_widget.activate()

    def on_unmap(self, *args):
        self.wifi_widget.deactivate()

