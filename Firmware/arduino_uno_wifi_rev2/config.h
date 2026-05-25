/*
  Arduino UNO WiFi Rev2 - Configuration Header
  eTextile-Synthesizer Adaptation
  
  Pin assignments and protocol definitions
*/

#ifndef __CONFIG_H__
#define __CONFIG_H__

// ============================================================================
// HARDWARE CONFIGURATION
// ============================================================================

// Analog Input Pins (A0-A4, 10-bit ADC)
#define ANALOG_PIN_0 A0
#define ANALOG_PIN_1 A1
#define ANALOG_PIN_2 A2
#define ANALOG_PIN_3 A3
#define ANALOG_PIN_4 A4

// Digital Output Pins
// Maps to OUTPUT_PINS array below
#define OUTPUT_PIN_0 2
#define OUTPUT_PIN_1 3
#define OUTPUT_PIN_2 4
#define OUTPUT_PIN_3 7
#define OUTPUT_PIN_4 8
#define OUTPUT_PIN_5 9

// ============================================================================
// FIRMWARE CONSTANTS
// ============================================================================

#define PROJECT "ETEXTILE-SYNTHESIZER"
#define PLATFORM "ARDUINO_UNO_WIFI_REV2"
#define VERSION "0.1.0"
#define SENSOR_UID 1  // Unique sensor/device ID

// Number of sensors and outputs
#define NUM_SENSORS 5
#define NUM_OUTPUTS 6

// Output pins array (indexed 0-5, maps to pins 2, 3, 4, 7, 8, 9)
const uint8_t OUTPUT_PINS[NUM_OUTPUTS] = {
  OUTPUT_PIN_0,  // index 0 -> pin 2
  OUTPUT_PIN_1,  // index 1 -> pin 3
  OUTPUT_PIN_2,  // index 2 -> pin 4
  OUTPUT_PIN_3,  // index 3 -> pin 7
  OUTPUT_PIN_4,  // index 4 -> pin 8
  OUTPUT_PIN_5   // index 5 -> pin 9
};

// ============================================================================
// COMMUNICATION PROTOCOL
// ============================================================================

// Serial Configuration
#define SERIAL_BAUD_RATE 115200

// Packet structure:
//   HEADER: 0xAA (1 byte)
//   PAYLOAD: sensor_0 sensor_1 sensor_2 sensor_3 sensor_4 (5 bytes)
//   TIMESTAMP: timestamp_hi timestamp_lo (2 bytes, big-endian)
//   TERMINATOR: 0xBB (1 byte)
// Total: 9 bytes per frame

#define SERIAL_HEADER_MARKER    0xAA
#define SERIAL_TERM_MARKER      0xBB
#define SERIAL_CMD_MARKER       0xCC  // Incoming command marker
#define SERIAL_CMD_TERM_MARKER  0xDD  // Incoming command terminator

// Timing
#define FRAME_RATE_HZ 30
#define FRAME_INTERVAL_MS (1000 / FRAME_RATE_HZ)  // ~33 ms

// ============================================================================
// ADC CONFIGURATION
// ============================================================================

// Arduino UNO WiFi Rev2 ADC:
// - 10-bit resolution (0-1023)
// - 3.3V reference (important: NOT 5V)
// - Scaling: reading >> 2 converts to 8-bit (0-255) for transmission

#define ADC_BITS 10
#define ADC_MAX ((1 << ADC_BITS) - 1)  // 1023
#define ADC_TO_8BIT_SHIFT 2             // Divide by 4 to convert 10-bit to 8-bit

// ============================================================================
// DEBUG FLAGS
// ============================================================================

// Uncomment to enable debug output
// #define DEBUG_SERIAL_CMD        // Print incoming commands
// #define DEBUG_SENSOR_VALUES     // Print raw sensor readings
// #define DEBUG_FRAME_RATE        // Print FPS
// #define DEBUG_TIMESTAMP         // Print timestamp info

#endif  // __CONFIG_H__
