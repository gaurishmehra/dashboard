import json
import os
import subprocess
import re
import sys
import signal
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass

try:
    from PIL import Image
    import numpy as np
except ImportError as e:
    print(f"Error: Required dependencies not installed: {e}")
    print("Install with: pip install Pillow numpy")
    sys.exit(1)

# Configuration
CONFIG = {
    'log_file': Path.home() / '.local/share/dunst/notifications.json',
    'image_dir': Path.home() / '.local/share/dunst/images',
    'max_log_entries': 10000,
    'image_quality': 95,
    'debug_mode': False,
    'save_all_formats': False,  # Set to True for debugging color issues
}

@dataclass
class ImageMetadata:
    """Container for image metadata from D-Bus"""
    width: Optional[int] = None
    height: Optional[int] = None
    rowstride: Optional[int] = None
    has_alpha: Optional[bool] = None
    bits_per_sample: Optional[int] = None
    channels: Optional[int] = None

@dataclass
class Notification:
    """Container for notification data"""
    timestamp: str
    app_name: str
    summary: str
    body: str
    icon: str = ""
    replaces_id: Optional[int] = None

class NotificationLogger:
    def __init__(self):
        self.setup_logging()
        self.ensure_directories()
        self.process = None
        self.running = False
        
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = logging.DEBUG if CONFIG['debug_mode'] else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(CONFIG['log_file'].parent / 'logger.log')
            ]
        )
        self.logger = logging.getLogger(__name__)

    def ensure_directories(self):
        """Create necessary directories and initialize log file"""
        try:
            CONFIG['log_file'].parent.mkdir(parents=True, exist_ok=True)
            CONFIG['image_dir'].mkdir(parents=True, exist_ok=True)
            
            if not CONFIG['log_file'].exists():
                with open(CONFIG['log_file'], 'w') as f:
                    json.dump([], f)
                    
            self.logger.info(f"Logging to: {CONFIG['log_file']}")
            self.logger.info(f"Images saved to: {CONFIG['image_dir']}")
            
        except Exception as e:
            self.logger.error(f"Failed to create directories: {e}")
            sys.exit(1)

    def extract_image_metadata_and_data(self, lines: List[str]) -> Tuple[Optional[bytes], ImageMetadata]:
        """Extract image metadata and binary data from D-Bus output"""
        in_image_data = False
        image_bytes = []
        metadata = ImageMetadata()
        
        try:
            for i, line in enumerate(lines):
                if 'string "image-data"' in line:
                    in_image_data = True
                    # Look for the struct metadata in the next few lines
                    for j in range(i+1, min(i+15, len(lines))):
                        metadata_line = lines[j]
                        if 'struct {' in metadata_line:
                            # Extract metadata from subsequent lines
                            metadata_values = []
                            for k in range(j+1, min(j+20, len(lines))):
                                meta_line = lines[k].strip()
                                if meta_line.startswith('int32 '):
                                    metadata_values.append(int(meta_line.split()[1]))
                                elif meta_line.startswith('boolean '):
                                    metadata_values.append(meta_line.split()[1] == 'true')
                                elif '}' in meta_line:
                                    break
                            
                            # Assign metadata values in typical order
                            if len(metadata_values) >= 6:
                                metadata.width = metadata_values[0]
                                metadata.height = metadata_values[1] 
                                metadata.rowstride = metadata_values[2]
                                metadata.has_alpha = metadata_values[3]
                                metadata.bits_per_sample = metadata_values[4]
                                metadata.channels = metadata_values[5]
                            break
                    continue
                
                if in_image_data:
                    # Stop when we hit the next dict entry or end of array
                    if ('dict entry(' in line or 
                        (']' in line.strip() and line.strip() == ']') or
                        'int32 -1' in line):
                        break
                    
                    # Extract hex bytes from lines
                    hex_match = re.findall(r'\b[0-9a-f]{2}\b', line.lower())
                    if hex_match:
                        for hex_byte in hex_match:
                            image_bytes.append(int(hex_byte, 16))
            
            image_data = bytes(image_bytes) if image_bytes else None
            
            if image_data and metadata.width:
                self.logger.debug(f"Extracted image: {len(image_data)} bytes, "
                                f"{metadata.width}x{metadata.height}, "
                                f"{metadata.channels} channels")
            
            return image_data, metadata
            
        except Exception as e:
            self.logger.error(f"Error extracting image data: {e}")
            return None, ImageMetadata()

    def detect_color_format(self, img_array: np.ndarray, channels: int) -> str:
        """Detect the most likely color format based on image analysis"""
        try:
            if channels == 4:
                # Check alpha channel - if it's mostly 255, likely RGBA/BGRA
                alpha_channel = img_array[:, :, 3]
                alpha_mean = np.mean(alpha_channel)
                
                # Check red vs blue channel variance to detect BGR vs RGB
                red_var = np.var(img_array[:, :, 0])
                blue_var = np.var(img_array[:, :, 2])
                
                # If blue channel has more variance, likely BGR format
                if blue_var > red_var * 1.5:
                    return 'BGRA'
                else:
                    return 'RGBA'
                    
            elif channels == 3:
                # Similar logic for RGB vs BGR
                red_var = np.var(img_array[:, :, 0])
                blue_var = np.var(img_array[:, :, 2])
                
                if blue_var > red_var * 1.5:
                    return 'BGR'
                else:
                    return 'RGB'
                    
        except Exception as e:
            self.logger.debug(f"Color format detection failed: {e}")
            
        # Default assumptions (most common on Linux)
        return 'BGRA' if channels == 4 else 'BGR'

    def save_image_as_png(self, image_data: bytes, metadata: ImageMetadata, 
                         app_name: str, timestamp: str) -> Optional[str]:
        """Convert raw image data to PNG with proper color handling"""
        if not image_data or not metadata.width or not metadata.height:
            return None
        
        try:
            width = metadata.width
            height = metadata.height
            channels = metadata.channels or 4
            rowstride = metadata.rowstride
            
            # Validate data size
            expected_size = width * height * channels
            if rowstride:
                expected_size = height * rowstride
                
            if len(image_data) < expected_size:
                self.logger.warning(f"Insufficient image data. Expected {expected_size}, got {len(image_data)}")
                # Try with available data
                expected_size = len(image_data)
            
            # Handle rowstride padding
            if rowstride and rowstride > width * channels:
                self.logger.debug(f"Handling rowstride padding: {rowstride} vs {width * channels}")
                img_array = np.frombuffer(image_data, dtype=np.uint8)
                rows = []
                
                for row in range(height):
                    start_idx = row * rowstride
                    end_idx = start_idx + (width * channels)
                    if end_idx <= len(img_array):
                        row_data = img_array[start_idx:end_idx]
                        rows.append(row_data)
                
                if len(rows) == height:
                    img_array = np.concatenate(rows)
                else:
                    self.logger.warning("Failed to handle rowstride, using simple approach")
                    img_array = np.frombuffer(image_data, dtype=np.uint8)[:width * height * channels]
            else:
                img_array = np.frombuffer(image_data, dtype=np.uint8)[:width * height * channels]
            
            # Reshape the data
            if len(img_array) < width * height * channels:
                self.logger.warning(f"Reshaping with available data: {len(img_array)}")
                # Pad with zeros if necessary
                padding_needed = width * height * channels - len(img_array)
                img_array = np.pad(img_array, (0, padding_needed), mode='constant')
            
            img_array = img_array.reshape((height, width, channels))
            
            # Create safe filename
            safe_timestamp = re.sub(r'[^\w\-_.]', '_', timestamp)
            safe_app_name = re.sub(r'[^\w\-_.]', '_', app_name)
            
            if CONFIG['save_all_formats']:
                return self._save_all_color_formats(img_array, channels, safe_app_name, safe_timestamp)
            else:
                return self._save_best_format(img_array, channels, safe_app_name, safe_timestamp)
                
        except Exception as e:
            self.logger.error(f"Error converting image: {e}")
            return None

    def _save_best_format(self, img_array: np.ndarray, channels: int, 
                         app_name: str, timestamp: str) -> Optional[str]:
        """Save image in the most likely correct color format"""
        try:
            detected_format = self.detect_color_format(img_array, channels)
            self.logger.debug(f"Detected color format: {detected_format}")
            
            if channels == 4:
                if detected_format == 'BGRA':
                    # Convert BGRA to RGBA
                    converted_array = img_array[:, :, [2, 1, 0, 3]]
                else:
                    # Assume already RGBA
                    converted_array = img_array.copy()
                
                image = Image.fromarray(converted_array, 'RGBA')
                
            elif channels == 3:
                if detected_format == 'BGR':
                    # Convert BGR to RGB
                    converted_array = img_array[:, :, [2, 1, 0]]
                else:
                    # Assume already RGB
                    converted_array = img_array.copy()
                
                image = Image.fromarray(converted_array, 'RGB')
            else:
                self.logger.error(f"Unsupported channel count: {channels}")
                return None
            
            filename = f"{app_name}_{timestamp}.png"
            filepath = CONFIG['image_dir'] / filename
            
            # Save with high quality
            image.save(filepath, 'PNG', optimize=True)
            
            self.logger.info(f"Saved image ({detected_format}): {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Error saving image: {e}")
            return None

    def _save_all_color_formats(self, img_array: np.ndarray, channels: int,
                               app_name: str, timestamp: str) -> Optional[str]:
        """Save image in all possible color formats for debugging"""
        saved_files = []
        
        formats_to_try = []
        if channels == 4:
            formats_to_try = [
                ('RGBA', img_array, 'RGBA'),
                ('BGRA', img_array[:, :, [2, 1, 0, 3]], 'RGBA'),
                ('ARGB', img_array[:, :, [1, 2, 3, 0]], 'RGBA'),
                ('ABGR', img_array[:, :, [3, 2, 1, 0]], 'RGBA'),
            ]
        elif channels == 3:
            formats_to_try = [
                ('RGB', img_array, 'RGB'),
                ('BGR', img_array[:, :, [2, 1, 0]], 'RGB'),
            ]
        
        for format_name, array, pil_mode in formats_to_try:
            try:
                image = Image.fromarray(array, pil_mode)
                filename = f"{app_name}_{timestamp}_{format_name}.png"
                filepath = CONFIG['image_dir'] / filename
                image.save(filepath, 'PNG', optimize=True)
                saved_files.append(str(filepath))
                self.logger.debug(f"Saved {format_name} version: {filepath}")
            except Exception as e:
                self.logger.debug(f"Failed to save {format_name} version: {e}")
        
        return saved_files[0] if saved_files else None

    def log_notification(self, notification: Notification):
        """Log notification to JSON file with rotation"""
        try:
            # Read existing logs
            logs = []
            if CONFIG['log_file'].exists():
                try:
                    with open(CONFIG['log_file'], 'r') as f:
                        content = f.read().strip()
                        if content:
                            logs = json.loads(content)
                        if not isinstance(logs, list):
                            logs = []
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning(f"Corrupted JSON file, reinitializing: {e}")
                    logs = []
            
            # Add new notification
            notification_dict = {
                "timestamp": notification.timestamp,
                "app_name": notification.app_name,
                "summary": notification.summary,
                "body": notification.body,
                "icon": notification.icon,
                "replaces_id": notification.replaces_id
            }
            
            logs.append(notification_dict)
            
            # Rotate logs if too many entries
            if len(logs) > CONFIG['max_log_entries']:
                logs = logs[-CONFIG['max_log_entries']:]
                self.logger.info(f"Rotated log file, kept last {CONFIG['max_log_entries']} entries")
            
            # Write back to file atomically
            temp_file = CONFIG['log_file'].with_suffix('.tmp')
            try:
                with open(temp_file, 'w') as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
                temp_file.replace(CONFIG['log_file'])
            except Exception as write_error:
                if temp_file.exists():
                    temp_file.unlink()
                raise write_error
            
            icon_info = f" (icon: {notification.icon})" if notification.icon else ""
            self.logger.info(f"✓ Logged: {notification.app_name} - {notification.summary}{icon_info}")
            
        except Exception as e:
            self.logger.error(f"Error logging notification: {e}")

    def parse_notification_strings(self, strings: List[str]) -> Notification:
        """Parse notification data from D-Bus strings"""
        timestamp = datetime.now().isoformat()
        
        if len(strings) < 4:
            raise ValueError(f"Insufficient notification data: {len(strings)} strings")
        
        # Check if second element is a uint32 placeholder (replaces_id)
        if len(strings) >= 5 and strings[1].startswith('__UINT32_'):
            # Format: app_name, replaces_id, icon, summary, body, ...
            app_name = strings[0]
            replaces_id = int(strings[1].replace('__UINT32_', '').replace('__', '')) if '__UINT32_' in strings[1] else None
            icon = strings[2] if strings[2] else ""
            summary = strings[3]
            body = strings[4] if len(strings) > 4 else ""
        else:
            # Format: app_name, icon, summary, body (simple notify-send format)
            app_name = strings[0]
            replaces_id = None
            icon = strings[1] if strings[1] else ""
            summary = strings[2]
            body = strings[3] if len(strings) > 3 else ""
        
        return Notification(
            timestamp=timestamp,
            app_name=app_name,
            summary=summary,
            body=body,
            icon=icon,
            replaces_id=replaces_id
        )

    def process_notification(self, notification_lines: List[str], strings: List[str]):
        """Process a complete notification"""
        try:
            if len(strings) < 4:
                self.logger.warning(f"Incomplete notification data: {len(strings)} strings")
                return
            
            self.logger.debug(f"Processing strings: {strings}")
            
            # Parse basic notification data
            notification = self.parse_notification_strings(strings)
            
            # Check for embedded image data
            has_image_data = any('string "image-data"' in line for line in notification_lines)
            
            if has_image_data:
                self.logger.info("Found embedded image data, extracting...")
                image_data, metadata = self.extract_image_metadata_and_data(notification_lines)
                
                if image_data and metadata.width and metadata.height:
                    saved_image_path = self.save_image_as_png(
                        image_data, metadata, notification.app_name, notification.timestamp
                    )
                    if saved_image_path:
                        notification.icon = saved_image_path
                        self.logger.info(f"Successfully saved embedded image: {saved_image_path}")
                    else:
                        self.logger.warning("Failed to save embedded image")
                else:
                    self.logger.warning("Failed to extract image data or metadata")
            
            # Log the notification
            self.log_notification(notification)
            
        except Exception as e:
            self.logger.error(f"Error processing notification: {e}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
        if self.process:
            self.process.terminate()
        sys.exit(0)

    def run(self):
        """Main monitoring loop"""
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        self.logger.info("Starting notification logger...")
        self.logger.info("Press Ctrl+C to stop")
        
        try:
            self.process = subprocess.Popen([
                'dbus-monitor', 
                "interface='org.freedesktop.Notifications',member='Notify'"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            self.running = True
            in_notify_call = False
            notification_lines = []
            strings = []
            current_string = ""
            in_string = False
            processed_this_notification = False
            
            for line in self.process.stdout:
                if not self.running:
                    break
                    
                line = line.rstrip()
                
                if 'method call' in line and 'member=Notify' in line:
                    # Process previous notification if we have one
                    if notification_lines and strings and not processed_this_notification:
                        self.process_notification(notification_lines, strings)
                    
                    self.logger.debug("=== New notification ===")
                    in_notify_call = True
                    notification_lines = [line]
                    strings = []
                    current_string = ""
                    in_string = False
                    processed_this_notification = False
                    continue
                
                if not in_notify_call:
                    continue
                
                notification_lines.append(line)
                
                # Parse strings and other data types
                if re.match(r'\s+string "', line):
                    # If we were already in a string, save the previous one
                    if in_string:
                        strings.append(current_string)
                        self.logger.debug(f"String {len(strings)}: '{current_string}'")
                    
                    # Start new string
                    string_content = re.sub(r'\s+string "', '', line)
                    if string_content.endswith('"'):
                        # Single line string
                        strings.append(string_content[:-1])
                        self.logger.debug(f"String {len(strings)}: '{string_content[:-1]}'")
                        in_string = False
                        current_string = ""
                    else:
                        # Multi-line string starts
                        current_string = string_content
                        in_string = True
                    continue
                
                # Handle uint32 (replaces_id) - treat as placeholder
                elif re.match(r'\s+uint32 ', line):
                    if in_string:
                        strings.append(current_string)
                        self.logger.debug(f"String {len(strings)}: '{current_string}'")
                        in_string = False
                        current_string = ""
                    # Add placeholder for uint32
                    uint_value = line.strip().split()[1]
                    strings.append(f"__UINT32_{uint_value}__")
                    self.logger.debug(f"UInt32 {len(strings)}: {uint_value}")
                    continue
                
                # If we're in a multi-line string, continue building it
                if in_string:
                    if line.endswith('"'):
                        # End of multi-line string
                        current_string += "\n" + line[:-1]
                        strings.append(current_string)
                        self.logger.debug(f"String {len(strings)}: '{current_string}'")
                        current_string = ""
                        in_string = False
                    else:
                        # Continue multi-line string
                        current_string += "\n" + line
                    continue
                
                # Process when we see the end marker (int32 -1) or method return
                if (('int32 -1' in line or 'method return' in line) and 
                    len(strings) >= 4 and 
                    not processed_this_notification):
                    
                    self.process_notification(notification_lines, strings)
                    processed_this_notification = True
                    in_notify_call = False
                    notification_lines = []
        
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}")
        finally:
            if self.process:
                self.process.terminate()
            self.logger.info("Notification logger stopped")

def main():
    """Entry point"""
    try:
        # Check for dbus-monitor
        if subprocess.run(['which', 'dbus-monitor'], capture_output=True).returncode != 0:
            print("Error: dbus-monitor not found. Please install dbus-tools package.")
            sys.exit(1)
        
        # Parse command line arguments
        if len(sys.argv) > 1:
            if sys.argv[1] in ['--debug', '-d']:
                CONFIG['debug_mode'] = True
            elif sys.argv[1] in ['--save-all-formats', '-a']:
                CONFIG['save_all_formats'] = True
                CONFIG['debug_mode'] = True
            elif sys.argv[1] in ['--help', '-h']:
                print("Usage: notification_logger.py [--debug|-d] [--save-all-formats|-a] [--help|-h]")
                print("  --debug: Enable debug logging")
                print("  --save-all-formats: Save images in all color formats for debugging")
                print("  --help: Show this help message")
                sys.exit(0)
        
        logger = NotificationLogger()
        logger.run()
        
    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()