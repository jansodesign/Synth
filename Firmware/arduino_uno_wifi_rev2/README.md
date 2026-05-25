## Arduino UNO WiFi Rev2 Adaptation - Quick Start

### Overview

This directory contains firmware and software for running eTextile-Synthesizer on an **Arduino UNO WiFi Rev2** instead of the original Teensy 4.0. The key difference is a **client-server architecture**:

- **Arduino**: Acts as a sensor I/O client
  - Reads 5 analog inputs (A0-A4)
  - Controls 6 digital outputs (pins 2, 3, 4, 7, 8, 9)
  - Communicates via USB Serial at 115200 baud

- **Laptop**: Performs heavy signal processing
  - Bilinear interpolation (upsampling to 64×64 grid)
  - Blob detection and tracking
  - Velocity calculation
  - MIDI output and digital command generation

### Hardware Requirements

- **Arduino UNO WiFi Rev2** (SAMD21 MCU, 48 MHz, 256 KB flash)
- 5 analog sensors (FSRs, resistive sensors, etc.)
- 6 digital outputs (relays, solenoids, LEDs, etc.)
- USB cable for power and serial communication
- Laptop running Python 3.8+ (Windows, macOS, or Linux)

### Pin Mapping

| Purpose | Arduino Pin | Type |
|---------|-------------|------|
| Sensor 0 | A0 | ADC (10-bit) |
| Sensor 1 | A1 | ADC (10-bit) |
| Sensor 2 | A2 | ADC (10-bit) |
| Sensor 3 | A3 | ADC (10-bit) |
| Sensor 4 | A4 | ADC (10-bit) |
| Output 0 | 2 | GPIO |
| Output 1 | 3 | GPIO |
| Output 2 | 4 | GPIO |
| Output 3 | 7 | GPIO |
| Output 4 | 8 | GPIO |
| Output 5 | 9 | GPIO |

**Important**: Arduino UNO WiFi Rev2 uses **3.3V** I/O. Scale your sensor circuits accordingly (do NOT use 5V FSRs without level shifting).

### Arduino Firmware Setup

1. **Open Arduino IDE** and go to **Sketch → Include Library → Manage Libraries**
   - No external libraries required for basic functionality

2. **Copy firmware files**:
   ```bash
   cp -r arduino_uno_wifi_rev2/ ~/Arduino/sketches/etextile_sensor_client/
   ```

3. **Upload firmware**:
   - Select **Board**: Arduino UNO WiFi Rev2
   - Select **Port**: /dev/ttyACM0 (Linux/Mac) or COM3/COM4 (Windows)
   - Click **Upload**

4. **Verify**:
   - Open Serial Monitor (115200 baud)
   - You should see startup message: `=== Arduino UNO WiFi Rev2 - ETEXTILE SENSOR CLIENT ===`

### Laptop Software Setup

#### 1. Install Python Dependencies

```bash
pip install pyserial numpy scipy python-rtmidi
```

#### 2. Configure Serial Port

Edit `etextile_receiver.py` line 19:
```python
SERIAL_PORT = "/dev/ttyACM0"  # Linux/Mac
# SERIAL_PORT = "COM3"        # Windows
```

#### 3. Run Receiver

```bash
cd Software/Python
python3 etextile_receiver.py
```

Expected output:
```
=== eTextile-Synthesizer: Arduino UNO WiFi Rev2 Receiver ===
Port: /dev/ttyACM0
Baud: 115200
Sensors: 5
Outputs: 6

[SensorReceiver] Started
[MIDI] Opened port: IAC Driver Bus 1
[ETextileSynth] Started
Frame 30: 4 blobs detected, sensors: [128, 64, 200, 32, 90]
...
```

### Communication Protocol

#### Arduino → Laptop (Sensor Data)

**9-byte packet, 30 Hz rate**:
```
[0xAA] [A0] [A1] [A2] [A3] [A4] [TS_HI] [TS_LO] [0xBB]

0xAA      = Header marker
A0-A4     = 8-bit sensor values (0-255, converted from 10-bit ADC)
TS_HI/LO  = 16-bit timestamp (milliseconds)
0xBB      = Terminator marker
```

**Example packet (hex)**:
```
AA 80 40 C8 20 5A 00 15 BB
   ^  ^  ^  ^  ^  ^  ^  ^  ^
   |  +--+--+--+--+  |  |  |
   |     sensors    |  |  |
   |              time |
   |                   |
   header          terminator
```

#### Laptop → Arduino (Digital Output Commands)

**4-byte command packet**:
```
[0xCC] [PIN_IDX] [STATE] [0xDD]

0xCC      = Command marker
PIN_IDX   = 0-5 (maps to pins 2, 3, 4, 7, 8, 9)
STATE     = 0 (LOW) or 1 (HIGH)
0xDD      = Terminator marker
```

**Example: Set pin 2 HIGH**:
```
CC 00 01 DD
   ^  ^  ^
   |  |  |
   |  |  state HIGH
   |  output 0 (pin 2)
   command marker
```

### Customization

#### Adding More Sensors

Use an analog multiplexer (4051 or 4067) to expand beyond 5 inputs:

```cpp
// In config.h
#define NUM_SENSORS 16  // Use multiplexer for 16 inputs

// In sensor_client.ino
void read_sensors() {
  for (int i = 0; i < NUM_SENSORS; i++) {
    // Select channel i on multiplexer
    digitalWrite(S0, (i >> 0) & 1);
    digitalWrite(S1, (i >> 1) & 1);
    digitalWrite(S2, (i >> 2) & 1);
    
    delayMicroseconds(10);
    sensorValues[i] = analogRead(A0) >> 2;
  }
}
```

#### Tuning Blob Detection

In `etextile_receiver.py`:

```python
THRESHOLD = 50           # Lower = more sensitive (0-255)
MIN_BLOB_SIZE = 6        # Minimum pixels per blob
MAX_BLOB_SIZE = 1024     # Maximum pixels per blob
INTERP_SIZE = (64, 64)   # Upsampling resolution
```

#### Custom MIDI Mapping

Edit the `_handle_blobs()` method in `etextile_receiver.py`:

```python
def _handle_blobs(self, blobs):
    for blob in blobs:
        # Map blob properties to MIDI
        note = 36 + (blob['cx'] % 60)        # X position → note
        velocity = min(127, blob['z'])       # Pressure → velocity
        pan = (blob['cy'] * 127) // 64       # Y position → pan
        
        self.midi.send_note_on(note, velocity)
        self.midi.send_cc(10, pan)  # CC #10 = Pan
```

### Troubleshooting

#### Arduino won't upload

- Ensure correct board selected: **Arduino UNO WiFi Rev2**
- Try double-clicking reset button on Arduino before uploading
- Check USB cable and port

#### No sensor data received

```bash
# Check serial port on Linux
ls -la /dev/ttyACM*

# Monitor raw serial output
cat /dev/ttyACM0 | od -t x1
```

#### Slow/choppy blob detection

- Reduce `THRESHOLD` (more responsive but noisier)
- Reduce `INTERP_SIZE` (faster but lower resolution)
- Use C++ Processing script instead of Python for ~3-5× speedup

#### MIDI output not working

```bash
# List available MIDI ports on Linux
aconnect -l

# Use MIDI Through port or DAW as destination
aconnect 'eTextile-Synth' 'Synth Input'
```

### Performance

| Metric | Value | Notes |
|--------|-------|-------|
| Sensor read rate | ~100 Hz | Arduino ADC + serial overhead |
| Processing latency | 30-50 ms | Python interpolation + blob detection |
| Total latency | 50-100 ms | End-to-end (sensor → MIDI → synth) |
| RAM usage (Arduino) | ~100 bytes | Just sensor buffer |
| RAM usage (Laptop) | ~20 MB | Sensor history + interpolation |

### Next Steps

1. **WiFi Support**: Replace USB serial with WiFi using `<WiFi.h>` library
2. **More Sensors**: Add 4051 multiplexer for 16+ sensors
3. **Interpolation Accuracy**: Implement proper bilinear interpolation for 16×16 matrix
4. **Audio Integration**: Stream audio to Arduino or laptop synthesizer
5. **Gesture Recognition**: Add pattern matching on blob trajectories

### References

- [Arduino UNO WiFi Rev2 Documentation](https://docs.arduino.cc/hardware/uno-wifi-rev2)
- [SciPy blob detection](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.label.html)
- [Python-rtmidi documentation](https://spotlightkid.github.io/python-rtmidi/)
- Original eTextile-Synthesizer: https://github.com/eTextile/Synth

### License

CC-BY-SA 4.0 (same as eTextile-Synthesizer project)

---

**Questions?** Create an issue at https://github.com/jansodesign/Synth/issues
