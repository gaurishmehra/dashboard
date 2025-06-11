import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, Gio
import subprocess
import json
import threading
import queue
import warnings
import re

warnings.filterwarnings("ignore")

# This widget displays the basic information about a connected device,
# like its name, ID, Android version, and battery level.
class DeviceInfoWidget(Gtk.Box):
    # Sets up the widget when it's first created.
    def __init__(self, device_info):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.device_info = device_info
        self.create_ui()
    
    # Builds the visual parts of the device info card, like the icon,
    # name, and info tiles.
    def create_ui(self):
        header_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        header_card.add_css_class("device-header")
        header_card.set_margin_top(16)
        header_card.set_margin_bottom(16)
        header_card.set_margin_start(20)
        header_card.set_margin_end(20)
        
        device_icon = Gtk.Image()
        device_icon.set_from_icon_name("phone-symbolic")
        device_icon.set_pixel_size(40)
        device_icon.add_css_class("device-icon")
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        info_box.set_hexpand(True)
        
        device_name = self.device_info.get('model', 'Unknown Device')
        name_label = Gtk.Label(label=device_name)
        name_label.set_halign(Gtk.Align.START)
        name_label.add_css_class("device-name")
        
        device_id = self.device_info.get('device_id', 'Unknown')
        id_label = Gtk.Label(label=f"ID: {device_id}")
        id_label.set_halign(Gtk.Align.START)
        id_label.add_css_class("device-id")
        
        info_box.append(name_label)
        info_box.append(id_label)
        
        header_card.append(device_icon)
        header_card.append(info_box)
        
        tiles_grid = Gtk.Grid()
        tiles_grid.set_row_spacing(12)
        tiles_grid.set_column_spacing(12)
        tiles_grid.set_halign(Gtk.Align.CENTER)
        tiles_grid.set_margin_start(20)
        tiles_grid.set_margin_end(20)
        
        android_version = self.device_info.get('android_version', 'Unknown')
        android_tile = self.create_info_tile("Android", android_version, "computer-symbolic")
        tiles_grid.attach(android_tile, 0, 0, 1, 1)
        
        battery_level = self.device_info.get('battery_level', 'Unknown')
        battery_tile = self.create_info_tile("Battery", battery_level, "battery-good-symbolic")
        tiles_grid.attach(battery_tile, 1, 0, 1, 1)
        
        self.append(header_card)
        self.append(tiles_grid)
    
    # A helper function to create a small, stylish tile for displaying a single
    # piece of information (e.g., 'Battery' -> '85%').
    def create_info_tile(self, title, value, icon_name):
        tile = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        tile.add_css_class("info-tile")
        tile.set_size_request(140, 80)
        
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(24)
        icon.add_css_class("tile-icon")
        
        title_label = Gtk.Label(label=title)
        title_label.add_css_class("tile-title")
        
        value_label = Gtk.Label(label=value)
        value_label.add_css_class("tile-value")
        value_label.set_ellipsize(Pango.EllipsizeMode.END)
        value_label.set_max_width_chars(12)
        
        tile.append(icon)
        tile.append(title_label)
        tile.append(value_label)
        
        return tile

# This widget provides a grid of buttons for common ADB actions like
# locking the screen, going home, or rebooting the device.
class QuickActionsWidget(Gtk.Box):
    # Initializes the widget with the specific device ID it will control.
    def __init__(self, device_id, command_callback):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.device_id = device_id
        self.command_callback = command_callback
        self.create_ui()
    
    # Lays out the grid of action buttons and connects them to their
    # respective commands.
    def create_ui(self):
        actions_label = Gtk.Label(label="Quick Actions")
        actions_label.add_css_class("section-title")
        actions_label.set_halign(Gtk.Align.CENTER)
        actions_label.set_margin_top(16)
        actions_label.set_margin_start(20)
        
        actions_grid = Gtk.Grid()
        actions_grid.set_row_spacing(8)
        actions_grid.set_column_spacing(8)
        actions_grid.set_margin_start(16)
        actions_grid.set_margin_end(16)
        actions_grid.set_halign(Gtk.Align.CENTER)
        
        actions = [
            ("Lock Screen", "changes-prevent-symbolic", "input keyevent 26"),
            ("Wake Screen", "changes-allow-symbolic", "input keyevent 82"),
            ("Home", "go-home-symbolic", "input keyevent 3"),
            ("Back", "go-previous-symbolic", "input keyevent 4"),
            ("Recent Apps", "view-grid-symbolic", "input keyevent 187"),
            ("Restart", "view-refresh-symbolic", "reboot"),
        ]
        
        for i, (name, icon, command) in enumerate(actions):
            button = Gtk.Button()
            button.set_size_request(120, 80)
            button.add_css_class("action-button")
            
            button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            
            button_icon = Gtk.Image.new_from_icon_name(icon)
            button_icon.set_pixel_size(24)
            
            button_label = Gtk.Label(label=name)
            button_label.add_css_class("action-label")
            button_label.set_wrap(True)
            button_label.set_justify(Gtk.Justification.CENTER)
            
            button_box.append(button_icon)
            button_box.append(button_label)
            button.set_child(button_box)
            
            button.connect("clicked", lambda b, cmd=command: self.command_callback(self.device_id, cmd))
            
            row = i // 3
            col = i % 3
            actions_grid.attach(button, col, row, 1, 1)
        
        self.append(actions_label)
        self.append(actions_grid)

# A simple, circular button to represent a single connected device.
# Clicking it selects that device for viewing and control.
class DeviceButton(Gtk.Button):
    # Sets up the button with a phone icon and a helpful tooltip showing
    # the device name and ID.
    def __init__(self, device_info):
        super().__init__()
        self.device_info = device_info
        self.set_size_request(48, 48)
        self.add_css_class("circular")
        self.add_css_class("flat")
        self.add_css_class("player-icon")
        
        self.set_icon_name("phone-symbolic")
        
        device_name = device_info.get('model', 'Unknown Device')
        device_id = device_info.get('device_id', 'Unknown')
        self.set_tooltip_text(f"{device_name}\nID: {device_id}")
    
    # Changes the button's appearance to show whether it's the currently
    # selected device.
    def set_active(self, active):
        if active:
            self.add_css_class("suggested-action")
        else:
            self.remove_css_class("suggested-action")

# This is the main brain of the application. It handles discovering devices,
# displaying their info, and sending them commands. It's designed to be
# efficient by only running its device-checking logic when it's actually visible.
class ADBWidget(Gtk.Box):
    # Initializes the main widget, sets up the command queue, and prepares the UI.
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.devices = []
        self.current_device = None
        self.device_buttons = []
        
        self.command_queue = queue.Queue()
        self.command_thread = threading.Thread(target=self.command_worker, daemon=True)
        self.command_thread.start()
        
        self.is_active = False
        self.update_timer_id = None
        
        self.create_ui()
    
    # Kicks off the device monitoring process. This is called when the widget
    # becomes visible to prevent unnecessary work in the background.
    def activate(self):
        if self.is_active:
            return
        self.is_active = True
        print("ADBWidget Activated")
        self.update_devices()
        if self.update_timer_id is None:
            self.update_timer_id = GLib.timeout_add_seconds(3, self.update_devices)

    # Pauses the device monitoring process when the widget is hidden,
    # saving system resources.
    def deactivate(self):
        if not self.is_active:
            return
        self.is_active = False
        print("ADBWidget Deactivated")
        if self.update_timer_id:
            GLib.source_remove(self.update_timer_id)
            self.update_timer_id = None

    # Runs in a separate thread to handle sending ADB commands without
    # freezing the user interface.
    def command_worker(self):
        while True:
            try:
                device_id, command = self.command_queue.get(timeout=1)
                if device_id and command:
                    if command.startswith("reboot"):
                        full_command = f"adb -s {device_id} {command}"
                    else:
                        full_command = f"adb -s {device_id} shell {command}"
                    
                    result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=10)
                    if result.returncode != 0:
                        print(f"ADB command failed: {full_command}")
                        print(f"Error: {result.stderr}")
                self.command_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                print(f"ADB command error: {e}")
    
    # Builds the main layout, including the device selection bar at the top
    # and the scrollable area for content.
    def create_ui(self):
        self.set_margin_top(15)
        self.set_margin_bottom(15)
        self.set_margin_start(15)
        self.set_margin_end(15)
        
        self.devices_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.devices_box.set_halign(Gtk.Align.CENTER)
        
        scrolled_window = Gtk.ScrolledWindow()
        scrolled_window.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_window.set_vexpand(True)
        scrolled_window.add_css_class("invisible-scroll")
        
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.content_box.set_margin_start(8)
        self.content_box.set_margin_end(8)
        self.content_box.set_margin_bottom(16)
        
        scrolled_window.set_child(self.content_box)
        
        self.append(self.devices_box)
        self.append(scrolled_window)
    
    # A utility function to execute an ADB command and capture its output.
    def run_adb_command(self, command):
        try:
            result = subprocess.run(f"adb {command}", shell=True, capture_output=True, text=True, timeout=5)
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception as e:
            print(f"ADB command error: {e}")
            return ""
    
    # Fetches detailed information for a specific device by running several
    # ADB commands.
    def get_device_info(self, device_id):
        info = {'device_id': device_id}
        
        try:
            model = self.run_adb_command(f"-s {device_id} shell getprop ro.product.model")
            info['model'] = model or "Unknown Device"
            
            android_version = self.run_adb_command(f"-s {device_id} shell getprop ro.build.version.release")
            info['android_version'] = android_version or "Unknown"
            
            battery_output = self.run_adb_command(f"-s {device_id} shell dumpsys battery")
            battery_match = re.search(r'level: (\d+)', battery_output)
            battery_level = battery_match.group(1) if battery_match else "Unknown"
            info['battery_level'] = f"{battery_level}%" if battery_level != "Unknown" else "Unknown"
            
            info['state'] = 'device'
            
        except Exception as e:
            print(f"Error getting device info for {device_id}: {e}")
            info.update({
                'model': 'Unknown Device',
                'android_version': 'Unknown',
                'battery_level': 'Unknown',
                'state': 'unknown'
            })
        
        return info
    
    # Periodically checks for connected ADB devices and updates the UI if
    # the list has changed.
    def update_devices(self):
        if not self.is_active:
            return False

        devices_output = self.run_adb_command("devices")
        
        new_device_infos = []
        if devices_output:
            lines = devices_output.split('\n')[1:]
            for line in lines:
                if line.strip() and '\t' in line:
                    device_id, state = line.strip().split('\t')
                    if state == 'device':
                        device_info = self.get_device_info(device_id)
                        new_device_infos.append(device_info)
        
        current_ids = {d['device_id'] for d in self.devices}
        new_ids = {d['device_id'] for d in new_device_infos}

        if current_ids != new_ids:
            self.devices = new_device_infos
            self.update_device_buttons()
            self.update_ui()
        
        return True
    
    # Rebuilds the row of circular device buttons at the top based on the
    # current list of connected devices.
    def update_device_buttons(self):
        for button in self.device_buttons:
            self.devices_box.remove(button)
        self.device_buttons.clear()
        
        if self.devices:
            for device_info in self.devices:
                button = DeviceButton(device_info)
                button.connect("clicked", lambda b, d=device_info: self.on_device_selected(d))
                self.device_buttons.append(button)
                self.devices_box.append(button)
            
            current_device_still_connected = self.current_device and any(d['device_id'] == self.current_device['device_id'] for d in self.devices)
            if not current_device_still_connected and self.devices:
                self.current_device = self.devices[0]
            
            self.update_button_states()
    
    # Highlights the button for the currently selected device.
    def update_button_states(self):
        for i, button in enumerate(self.device_buttons):
            if i < len(self.devices):
                is_current = (self.devices[i]['device_id'] == 
                             self.current_device['device_id'] if self.current_device else False)
                button.set_active(is_current)
    
    # Handles what happens when a user clicks on a device button, making it
    # the active device.
    def on_device_selected(self, device_info):
        self.current_device = device_info
        self.update_button_states()
        self.update_ui()
    
    # Refreshes the main content area to show the information and actions
    # for the currently selected device.
    def update_ui(self):
        child = self.content_box.get_first_child()
        while child:
            self.content_box.remove(child)
            child = self.content_box.get_first_child()
        
        if not self.devices:
            self.show_no_devices()
            return
        
        if not self.current_device:
            self.show_no_devices()
            return
        
        device_widget = DeviceInfoWidget(self.current_device)
        self.content_box.append(device_widget)
        
        actions_widget = QuickActionsWidget(self.current_device['device_id'], self.execute_command)
        self.content_box.append(actions_widget)
    
    # Displays a helpful message and instructions when no ADB devices are found.
    def show_no_devices(self):
        no_devices_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        no_devices_box.set_valign(Gtk.Align.CENTER)
        no_devices_box.set_vexpand(True)
        
        icon = Gtk.Image.new_from_icon_name("phone-disabled-symbolic")
        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")
        
        message_label = Gtk.Label(label="No ADB Devices Connected")
        message_label.add_css_class("title-large")
        message_label.add_css_class("dim-label")
        
        instructions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        instructions_box.set_halign(Gtk.Align.CENTER)
        
        instructions = [
            "1. Enable Developer Options on your device.",
            "2. Enable USB Debugging in Developer Options.",
            "3. Connect your device via USB or Wi-Fi.",
            "4. Authorize the debugging connection on your device."
        ]
        
        for instruction in instructions:
            inst_label = Gtk.Label(label=instruction)
            inst_label.add_css_class("dim-label")
            instructions_box.append(inst_label)
        
        no_devices_box.append(icon)
        no_devices_box.append(message_label)
        no_devices_box.append(instructions_box)
        
        self.content_box.append(no_devices_box)
    
    # Adds a new command to the queue to be run by the background thread.
    def execute_command(self, device_id, command):
        if device_id and command:
            self.command_queue.put((device_id, command))