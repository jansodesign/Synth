# Arduino UNO WiFi Rev2 Adaptation Guide

## Overview

This document describes how to adapt the eTextile-Synthesizer firmware from a **Teensy 4.0** (600 MHz) to an **Arduino UNO WiFi Rev2** (48 MHz ARM Cortex-M0+). The key architectural change is a **client-server model** where:

- **Arduino UNO WiFi Rev2** acts as a **sensor I/O client**:
  - Reads 5 analog inputs (A0-A4)
  - Controls 6 digital outputs (pins 2, 3, 4, 7, 8, 9)
  - Sends raw sensor data over WiFi or USB serial to a laptop
  - Receives mapped MIDI commands from laptop

- **Laptop runs the signal processing**:
  - Bilinear interpolation (16×16 → 64×64)
  - Blob detection and tracking
  - Velocity calculation
  - TUI mapping logic
  - Sends digital output commands back to Arduino

## Hardware Mapping

### Arduino UNO WiFi Rev2 Pinout

| Function | Pin | Type | Notes |
|----------|-----|------|-------|
| Analog Input 0 | A0 | ADC | FSR/sensor 1 |
| Analog Input 1 | A1 | ADC | FSR/sensor 2 |
| Analog Input 2 | A2 | ADC | FSR/sensor 3 |
| Analog Input 3 | A3 | ADC | FSR/sensor 4 |
| Analog Input 4 | A4 | ADC | FSR/sensor 5 |
| Digital Output 0 | 2 | GPIO | MIDI/control output 1 |
| Digital Output 1 | 3 | GPIO | MIDI/control output 2 |
| Digital Output 2 | 4 | GPIO | MIDI/control output 3 |
| Digital Output 3 | 7 | GPIO | MIDI/control output 4 |
| Digital Output 4 | 8 | GPIO | MIDI/control output 5 |
| Digital Output 5 | 9 | GPIO | MIDI/control output 6 |

**Note**: Arduino UNO WiFi Rev2 operates at **3.3V**. Adjust your sensor circuits accordingly (FSRs should scale to 3.3V, not 5V).

## Firmware Architecture

```
Arduino UNO WiFi Rev2:
┌─────────────┬────────────────┬────────────────────────┐
│ ADC Scan    │ Serial/WiFi    │ Digital Output Control │
│ (A0-A4)     │ Communicate    │ (pins 2,3,4,7,8,9)    │
└─────────────┴────────────────┴────────────────────────┘
                     ↕
        [WiFi/Serial Connection]
                     ↕
Laptop (Python/Processing/Max/Pure Data):
┌────────────────────────────────────────────────────────┐
│ • Bilinear Interpolation (16×16 → 64×64)              │
│ • Blob Detection (Scanline Flood Fill + CCL)          │
│ • Blob Tracking & Velocity                             │
│ • Mapping Library (TUI dispatch)                        │
│ • MIDI Output Generation                               │
│ • Digital Output Command Generation                    │
└────────────────────────────────────────────────────────┘
```

## Key Differences from Teensy Version

| Feature | Teensy 4.0 | Arduino UNO WiFi Rev2 |
|---------|-----------|----------------------|
| Clock Speed | 600 MHz | 48 MHz (80× slower) |
| RAM | 1024 KB | 256 KB |
| Flash | 2 MB | 256 KB |
| ADC Resolution | 12-bit | 10-bit |
| Matrix Size | 16×16 (256 values) | 5 sensors only |
| Interpolation | On-device | On laptop |
| Blob Detection | On-device | On laptop |
| Real-time constraint | Tight (500+ FPS) | Relaxed (30+ FPS) |
| Connectivity | USB MIDI | WiFi + USB Serial |

## Communication Protocol

### Arduino → Laptop (Sensor Data)

**Serial/WiFi packet format (per-frame):**
```
Header: 0xAA (1 byte)
Sensor values A0-A4: (5 bytes, 8-bit ADC values: 0-255)
Timestamp: (2 bytes, milliseconds)
Terminator: 0xBB (1 byte)

Total: 9 bytes per frame @ 30 Hz = 270 bytes/sec
```

**Example Python receiver:**
```python
import serial
import struct

ser = serial.Serial('/dev/ttyACM0', 115200)

while True:
    if ser.in_waiting >= 9:
        header = ser.read(1)
        if header == b'\xaa':
            a0, a1, a2, a3, a4 = struct.unpack('BBBBB', ser.read(5))
            timestamp = struct.unpack('>H', ser.read(2))[0]
            terminator = ser.read(1)
            
            if terminator == b'\xbb':
                print(f"Sensors: {[a0, a1, a2, a3, a4]}, ts={timestamp}")
```

### Laptop → Arduino (Digital Output Control)

**MIDI or custom protocol:**
```
Option A - MIDI Note On for Digital Output:
  Note: 60 + output_index (60-65 for pins 2-9)
  Velocity: 127 = HIGH, 0 = LOW

Option B - Simple ASCII commands:
  "D2H" = Set pin 2 HIGH
  "D2L" = Set pin 2 LOW
  "D3H" = Set pin 3 HIGH, etc.

Option C - Binary:
  0xCC (command marker)
  pin_index (0-5 for pins 2,3,4,7,8,9)
  state (0=LOW, 1=HIGH)
  0xDD (terminator)
```

**Arduino receiver:**
```cpp
const uint8_t OUTPUT_PINS[] = {2, 3, 4, 7, 8, 9};

void handle_serial_commands() {
  if (Serial.available() >= 3) {
    uint8_t cmd = Serial.read();
    if (cmd == 0xCC) {  // Binary command
      uint8_t pin_idx = Serial.read();
      uint8_t state = Serial.read();
      uint8_t term = Serial.read();
      
      if (term == 0xDD && pin_idx < 6) {
        digitalWrite(OUTPUT_PINS[pin_idx], state ? HIGH : LOW);
      }
    }
  }
}
```

## Reduced Sensor Configuration

Instead of a 16×16 matrix (256 sensors), this adaptation assumes a **simplified 5-sensor input** (or adaptable to more if using multiplexing).

**If you need more sensors, use:**
- **Multiplexer IC (4051/4067)** to expand analog inputs
- **I2C ADC expander** (ADS1115)
- **SPI ADC** (MCP3008/3208)

Example with 4051 multiplexer (8 channels per MUX):
```
A0 → 4051 channel select via D10-D12
Multiple multiplexers can be chained for 16+ sensors
```

## Recommended Laptop Software Stack

### Pure Data patch receiver:
```
[netreceive 9000]
|
[unpack 0 0 0 0 0 0 0]
|      |  |  |  |  |
A0    A1 A2 A3 A4 timestamp

[blob_detection]
|
[mapping_lib]
|
[netsend] → Arduino
```

### Python with SciPy (interpolation, blob detection):
```python
import numpy as np
from scipy import ndimage
import serial

class SensorInterface:
    def __init__(self, port='/dev/ttyACM0'):
        self.ser = serial.Serial(port, 115200)
    
    def read_sensors(self):
        """Read 5 ADC values from Arduino"""
        # See serial protocol above
        pass
    
    def interpolate_2d(self, sensors_5, shape=(64, 64)):
        """Upsample 5 sensors to 64×64 grid using bilinear interpolation"""
        # Use scipy.interpolate.RegularGridInterpolator
        pass
    
    def find_blobs(self, threshold=50):
        """Blob detection using scipy.ndimage.label"""
        binary_image = self.interp_frame > threshold
        blobs, num = ndimage.label(binary_image)
        return ndimage.find_objects(blobs)
    
    def send_output(self, pin_idx, state):
        """Send digital output command to Arduino"""
        cmd = bytes([0xCC, pin_idx, state, 0xDD])
        self.ser.write(cmd)
```

### Processing (for visual feedback):
```java
import processing.serial.*;

Serial mySerial;
int[] sensors = new int[5];

void setup() {
  size(512, 512);
  mySerial = new Serial(this, "/dev/ttyACM0", 115200);
  mySerial.bufferUntil(0xBB);
}

void serialEvent(Serial p) {
  byte[] data = p.readBytesUntil(0xBB);
  if (data[0] == 0xAA) {
    for (int i = 0; i < 5; i++) {
      sensors[i] = data[i+1] & 0xFF;
    }
    // Render visualization
    visualize_sensors();
  }
}
```

## Performance Considerations

### Limitations of Arduino UNO WiFi Rev2

1. **Memory**: Only 256 KB flash, 32 KB SRAM
   - Cannot store 64×64 interpolation frame (4 KB alone)
   - Solution: Keep only current sensor values in Arduino

2. **Processing Speed**: 48 MHz vs 600 MHz on Teensy
   - Cannot interpolate in real-time
   - Solution: Delegate to laptop

3. **ADC Resolution**: 10-bit (1024 levels) vs Teensy's 12-bit (4096 levels)
   - Consider using 8-bit reduced resolution for serial transfer

### Realistic Performance

- **Sensor Read Rate**: ~100 Hz (achievable with 5 analog reads + serial overhead)
- **Laptop Processing**: ~30 Hz (Python/Processing) to ~60 Hz (C++)
- **Latency**: ~50-100 ms total (Arduino + network + laptop + feedback)

## Migration Steps

1. **Phase 1**: Create Arduino firmware that reads 5 analog inputs and sends via serial
2. **Phase 2**: Create laptop Python/Processing script that:
   - Receives sensor data
   - Performs interpolation to 64×64 (optional, or use simpler 8×8 grid)
   - Detects blobs
   - Generates MIDI output
3. **Phase 3**: Add digital output feedback from laptop → Arduino
4. **Phase 4** (optional): Replace serial with WiFi using Arduino's WiFi module

## File Structure

```
Firmware/
├── arduino_uno_wifi_rev2/          # New Arduino-specific firmware
│   ├── sketches/
│   │   ├── sensor_client/
│   │   │   ├── sensor_client.ino   # Main Arduino code
│   │   │   ├── config.h            # Pin definitions
│   │   │   └── README.md
│   │   └── digital_output_control/
│   │       └── output_controller.ino
│   └── libraries/
│       └── ETextileSerial.h        # Protocol helpers
│
Software/
├── Python/
│   ├── etextile_receiver.py        # Serial sensor receiver
│   ├── blob_detector.py            # Blob detection
│   └── midi_controller.py          # MIDI output + digital commands
├── Processing/
│   └── SensorVisualizer.pde        # Real-time visualization
└── PureData/
    └── etextile_receiver.pd        # PD receiver patch
```

## Security Notes

If using WiFi:
- Arduino runs in **client mode** (connects to laptop)
- Use **WPA2/WPA3** encryption
- Keep credentials in PROGMEM or EEPROM, not in source
- Consider mDNS discovery instead of hardcoded IP

## Testing Checklist

- [ ] Arduino reads all 5 ADC inputs correctly
- [ ] Serial data transmits at 115200 baud without corruption
- [ ] Laptop receiver parses packets correctly
- [ ] Digital output commands sent from laptop work
- [ ] Latency < 100 ms end-to-end
- [ ] Stable over 10+ minute continuous operation
- [ ] Memory usage stable (no heap fragmentation)

## References

- Arduino UNO WiFi Rev2 datasheet
- eTextile-Synthesizer original firmware: `/Firmware/src/`
- Arduino serial communication: https://www.arduino.cc/reference/en/language/functions/communication/serial/
- Blob detection algorithms: https://en.wikipedia.org/wiki/Connected-component_labeling

---

**License**: CC-BY-SA (same as eTextile-Synthesizer project)
