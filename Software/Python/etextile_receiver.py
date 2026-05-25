#!/usr/bin/env python3
"""
Arduino UNO WiFi Rev2 Sensor Receiver & Processor
eTextile-Synthesizer Adaptation - Laptop Side

Receives sensor data from Arduino, processes blob detection,
and sends MIDI/digital output commands back.

Requirements:
  pip install pyserial numpy scipy python-rtmidi
"""

import serial
import struct
import threading
import time
import numpy as np
from scipy import ndimage
from collections import deque
import rtmidi

# ============================================================================
# CONFIGURATION
# ============================================================================

SERIAL_PORT = "/dev/ttyACM0"  # Change for Windows (COM3) or macOS (/dev/tty.usbserial-*)
BAUD_RATE = 115200
FRAME_TIMEOUT = 1.0  # seconds

NUM_SENSORS = 5
NUM_OUTPUTS = 6

SENSOR_HISTORY = 30  # Keep 30 frames of history for interpolation
FRAME_RATE_HZ = 30

# Blob detection parameters
INTERP_SIZE = (64, 64)      # Upsampled grid size
THRESHOLD = 50              # Binary threshold (0-255)
MIN_BLOB_SIZE = 6           # Minimum pixels per blob
MAX_BLOB_SIZE = 1024        # Maximum pixels per blob
VELOCITY_HISTORY_MS = 50    # Milliseconds of history for velocity

# Protocol markers
HEADER_MARKER = 0xAA
TERM_MARKER = 0xBB
CMD_MARKER = 0xCC
CMD_TERM = 0xDD

# ============================================================================
# SENSOR RECEIVER CLASS
# ============================================================================

class SensorReceiver:
    """Manages serial communication with Arduino"""
    
    def __init__(self, port, baud):
        self.ser = serial.Serial(port, baud, timeout=0.5)
        self.running = False
        self.thread = None
        self.latest_sensors = np.zeros(NUM_SENSORS, dtype=np.uint8)
        self.latest_timestamp = 0
        self.frame_count = 0
        self.error_count = 0
        
    def start(self):
        """Start background receiver thread"""
        self.running = True
        self.thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.thread.start()
        print("[SensorReceiver] Started")
    
    def stop(self):
        """Stop receiver thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        self.ser.close()
        print("[SensorReceiver] Stopped")
    
    def _receive_loop(self):
        """Background thread: read and parse serial packets"""
        buffer = bytearray()
        
        while self.running:
            if self.ser.in_waiting > 0:
                chunk = self.ser.read(self.ser.in_waiting)
                buffer.extend(chunk)
                
                # Look for complete packets: [0xAA, 5 sensors, 2 timestamp, 0xBB]
                while len(buffer) >= 9:
                    if buffer[0] != HEADER_MARKER:
                        buffer.pop(0)
                        continue
                    
                    if buffer[8] != TERM_MARKER:
                        buffer.pop(0)
                        continue
                    
                    # Valid packet found
                    try:
                        sensors = np.frombuffer(buffer[1:6], dtype=np.uint8)
                        timestamp = (buffer[6] << 8) | buffer[7]
                        
                        self.latest_sensors[:] = sensors
                        self.latest_timestamp = timestamp
                        self.frame_count += 1
                        
                        buffer = buffer[9:]  # Remove processed packet
                    except Exception as e:
                        print(f"[SensorReceiver] Parse error: {e}")
                        self.error_count += 1
                        buffer.pop(0)
            else:
                time.sleep(0.001)
    
    def get_sensors(self):
        """Return current sensor values and timestamp"""
        return self.latest_sensors.copy(), self.latest_timestamp
    
    def send_output(self, pin_idx, state):
        """Send digital output command to Arduino"""
        if not (0 <= pin_idx < NUM_OUTPUTS):
            return False
        
        cmd = bytes([CMD_MARKER, pin_idx, 1 if state else 0, CMD_TERM])
        try:
            self.ser.write(cmd)
            return True
        except Exception as e:
            print(f"[SensorReceiver] Send error: {e}")
            return False

# ============================================================================
# SIGNAL PROCESSING CLASS
# ============================================================================

class BlobProcessor:
    """Performs interpolation, blob detection, and tracking"""
    
    def __init__(self, num_sensors, interp_size, threshold):
        self.num_sensors = num_sensors
        self.interp_size = interp_size
        self.threshold = threshold
        self.sensor_history = deque(maxlen=SENSOR_HISTORY)
        self.blobs = []
        self.blob_id_counter = 0
        
    def process_frame(self, sensors):
        """
        Process sensor frame through pipeline:
        1. Interpolate to 64×64 grid
        2. Apply threshold
        3. Detect blobs
        4. Track blobs over time
        """
        # Store in history
        self.sensor_history.append(sensors.copy())
        
        # Simple interpolation: map 5 sensors to a sparse grid
        # For a full 16×16 matrix, use scipy.interpolate.RegularGridInterpolator
        # Here we'll create a simple demonstration
        
        interp_frame = self._simple_interpolate(sensors)
        
        # Apply threshold
        binary_image = interp_frame > self.threshold
        
        # Blob detection
        labeled_array, num_blobs = ndimage.label(binary_image)
        
        # Extract blob properties
        self.blobs = []
        if num_blobs > 0:
            for blob_id in range(1, num_blobs + 1):
                blob_mask = labeled_array == blob_id
                blob_pixels = np.argwhere(blob_mask)
                
                if len(blob_pixels) < MIN_BLOB_SIZE or len(blob_pixels) > MAX_BLOB_SIZE:
                    continue
                
                # Calculate centroid and properties
                cy, cx = blob_pixels.mean(axis=0)
                height, width = blob_pixels.max(axis=0) - blob_pixels.min(axis=0) + 1
                z = int(interp_frame[blob_mask].mean())
                
                self.blobs.append({
                    'id': self.blob_id_counter,
                    'cx': int(cx),
                    'cy': int(cy),
                    'z': int(z),
                    'w': int(width),
                    'h': int(height),
                    'size': len(blob_pixels)
                })
                
                self.blob_id_counter += 1
        
        return interp_frame, self.blobs
    
    def _simple_interpolate(self, sensors):
        """
        Simple 2D interpolation for 5-sensor input
        Maps to 64×64 output grid
        
        For a real 16×16 matrix, use:
          from scipy.interpolate import RegularGridInterpolator
        """
        # Create a sparse representation and upsample
        frame = np.zeros(self.interp_size, dtype=np.uint8)
        
        # Simple: place sensors at grid intersections and blur
        if len(sensors) >= 5:
            # Map 5 sensors to 5 points in the grid
            sensor_positions = [
                (10, 10),  # Top-left
                (10, 54),  # Top-right
                (32, 32),  # Center
                (54, 10),  # Bottom-left
                (54, 54),  # Bottom-right
            ]
            
            for i, (y, x) in enumerate(sensor_positions):
                frame[max(0, y-2):min(64, y+3), max(0, x-2):min(64, x+3)] = sensors[i]
            
            # Gaussian blur for smooth interpolation
            frame = ndimage.gaussian_filter(frame.astype(float), sigma=5).astype(np.uint8)
        
        return frame

# ============================================================================
# MIDI OUTPUT CLASS
# ============================================================================

class MIDIOutput:
    """Sends MIDI messages to synthesizer"""
    
    def __init__(self):
        self.midiout = rtmidi.MidiOut()
        self.port = None
        self._open_port()
    
    def _open_port(self):
        """List available MIDI ports and open one"""
        ports = self.midiout.get_ports()
        
        if not ports:
            print("[MIDI] No output ports found. Creating virtual port...")
            self.port = self.midiout.open_virtual_port("eTextile-Synth")
        else:
            print("[MIDI] Available ports:")
            for i, p in enumerate(ports):
                print(f"  {i}: {p}")
            
            # Try to open first port
            self.port = self.midiout.open_port(0)
            print(f"[MIDI] Opened port: {ports[0]}")
    
    def send_note_on(self, note, velocity=127, channel=0):
        """Send MIDI Note On"""
        msg = [0x90 | (channel & 0x0F), note & 0x7F, velocity & 0x7F]
        self.midiout.send_message(msg)
    
    def send_note_off(self, note, channel=0):
        """Send MIDI Note Off"""
        msg = [0x80 | (channel & 0x0F), note & 0x7F, 0]
        self.midiout.send_message(msg)
    
    def send_cc(self, cc_num, value, channel=0):
        """Send MIDI Control Change"""
        msg = [0xB0 | (channel & 0x0F), cc_num & 0x7F, value & 0x7F]
        self.midiout.send_message(msg)
    
    def close(self):
        """Close MIDI port"""
        del self.midiout

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class ETextileSynth:
    """Main orchestrator"""
    
    def __init__(self):
        self.receiver = SensorReceiver(SERIAL_PORT, BAUD_RATE)
        self.processor = BlobProcessor(NUM_SENSORS, INTERP_SIZE, THRESHOLD)
        self.midi = MIDIOutput()
        self.running = False
        
    def start(self):
        """Start processing"""
        self.receiver.start()
        self.running = True
        print("[ETextileSynth] Started")
        
        try:
            while self.running:
                sensors, timestamp = self.receiver.get_sensors()
                
                # Process frame
                interp_frame, blobs = self.processor.process_frame(sensors)
                
                # Generate MIDI/output from blobs
                self._handle_blobs(blobs)
                
                # Display status periodically
                if self.receiver.frame_count % 30 == 0:
                    print(f"Frame {self.receiver.frame_count}: "
                          f"{len(blobs)} blobs detected, "
                          f"sensors: {sensors[:5]}")
                
                time.sleep(1.0 / FRAME_RATE_HZ)
        
        except KeyboardInterrupt:
            print("\n[ETextileSynth] Interrupted by user")
        
        finally:
            self.stop()
    
    def _handle_blobs(self, blobs):
        """Convert blobs to MIDI/digital output commands"""
        for blob in blobs:
            # Example: Map blob centroid to MIDI note
            note = 36 + (blob['cx'] % 60)  # Map X position to note range
            velocity = min(127, blob['z'])
            
            # Send Note On
            self.midi.send_note_on(note, velocity)
            
            # Example: Map blob to digital outputs
            # Output 0: ON if blob size > threshold
            if blob['size'] > 30:
                self.receiver.send_output(0, True)
            else:
                self.receiver.send_output(0, False)
    
    def stop(self):
        """Shutdown"""
        self.running = False
        self.receiver.stop()
        self.midi.close()
        print("[ETextileSynth] Stopped")

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("=== eTextile-Synthesizer: Arduino UNO WiFi Rev2 Receiver ===")
    print(f"Port: {SERIAL_PORT}")
    print(f"Baud: {BAUD_RATE}")
    print(f"Sensors: {NUM_SENSORS}")
    print(f"Outputs: {NUM_OUTPUTS}")
    print()
    
    app = ETextileSynth()
    app.start()
