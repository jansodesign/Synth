/*
  Arduino UNO WiFi Rev2 - Sensor Client Firmware
  eTextile-Synthesizer Adaptation
  
  Reads 5 analog inputs (A0-A4) and transmits via Serial/WiFi to laptop
  Receives digital output commands and controls pins 2, 3, 4, 7, 8, 9
  
  License: CC-BY-SA (same as eTextile-Synthesizer)
*/

#include "config.h"

// Timing
unsigned long lastFrameTime = 0;
const unsigned long FRAME_INTERVAL_MS = 33;  // ~30 Hz

// Sensor buffers
uint8_t sensorValues[NUM_SENSORS] = {0};
uint16_t frameCounter = 0;

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  delay(100);  // Wait for serial port initialization
  
  // Initialize ADC pins as inputs (should be default)
  pinMode(A0, INPUT);
  pinMode(A1, INPUT);
  pinMode(A2, INPUT);
  pinMode(A3, INPUT);
  pinMode(A4, INPUT);
  
  // Initialize digital output pins
  for (int i = 0; i < NUM_OUTPUTS; i++) {
    pinMode(OUTPUT_PINS[i], OUTPUT);
    digitalWrite(OUTPUT_PINS[i], LOW);
  }
  
  // Debug message
  Serial.println("\n=== Arduino UNO WiFi Rev2 - eTEXTILE SENSOR CLIENT ===");
  Serial.print("Starting at ");
  Serial.print(SERIAL_BAUD_RATE);
  Serial.println(" baud");
  Serial.print("Reading ");
  Serial.print(NUM_SENSORS);
  Serial.println(" sensors");
  Serial.print("Controlling ");
  Serial.print(NUM_OUTPUTS);
  Serial.println(" digital outputs");
  Serial.println("Ready.\n");
}

void loop() {
  unsigned long now = millis();
  
  // 1. Check for incoming commands from laptop (non-blocking)
  handle_serial_commands();
  
  // 2. Read sensors at fixed interval
  if (now - lastFrameTime >= FRAME_INTERVAL_MS) {
    lastFrameTime = now;
    
    read_sensors();
    transmit_sensor_frame(now);
    frameCounter++;
  }
}

/**
 * Read all analog inputs and store in sensorValues array
 * ADC is 10-bit on Arduino, scaled to 8-bit for transmission
 */
void read_sensors() {
  // Read A0-A4 and convert from 10-bit (0-1023) to 8-bit (0-255)
  sensorValues[0] = (uint8_t)(analogRead(A0) >> 2);
  sensorValues[1] = (uint8_t)(analogRead(A1) >> 2);
  sensorValues[2] = (uint8_t)(analogRead(A2) >> 2);
  sensorValues[3] = (uint8_t)(analogRead(A3) >> 2);
  sensorValues[4] = (uint8_t)(analogRead(A4) >> 2);
}

/**
 * Transmit sensor frame over serial
 * Protocol:
 *   0xAA (header)
 *   A0 A1 A2 A3 A4 (5 bytes, 8-bit values)
 *   timestamp_hi timestamp_lo (2 bytes, big-endian)
 *   0xBB (terminator)
 */
void transmit_sensor_frame(unsigned long timestamp) {
  Serial.write(0xAA);  // Header
  
  // Sensor values
  for (int i = 0; i < NUM_SENSORS; i++) {
    Serial.write(sensorValues[i]);
  }
  
  // Timestamp (16-bit, big-endian)
  Serial.write((uint8_t)((timestamp >> 8) & 0xFF));
  Serial.write((uint8_t)(timestamp & 0xFF));
  
  Serial.write(0xBB);  // Terminator
}

/**
 * Handle incoming commands from laptop
 * Binary protocol:
 *   0xCC (command marker)
 *   pin_index (0-5 maps to OUTPUT_PINS[])
 *   state (0=LOW, 1=HIGH)
 *   0xDD (terminator)
 */
void handle_serial_commands() {
  if (Serial.available() >= 4) {
    uint8_t cmd = Serial.read();
    
    if (cmd == SERIAL_CMD_MARKER) {  // 0xCC
      uint8_t pin_idx = Serial.read();
      uint8_t state = Serial.read();
      uint8_t term = Serial.read();
      
      if (term == SERIAL_TERM_MARKER && pin_idx < NUM_OUTPUTS) {  // 0xDD
        uint8_t pin = OUTPUT_PINS[pin_idx];
        uint8_t pin_state = (state > 0) ? HIGH : LOW;
        
        digitalWrite(pin, pin_state);
        
        #ifdef DEBUG_SERIAL_CMD
        Serial.print("CMD: Pin ");
        Serial.print(pin);
        Serial.print(" -> ");
        Serial.println(pin_state ? "HIGH" : "LOW");
        #endif
      }
      else if (term != SERIAL_TERM_MARKER) {
        // Protocol error - flush buffer
        while (Serial.available()) Serial.read();
      }
    }
    else {
      // Unknown command marker - skip this byte
      // (This helps resync if packets get corrupted)
    }
  }
}

/*
  OPTIONAL: WiFi Support
  
  To enable WiFi instead of USB serial, uncomment below and modify:
  - WiFi.begin(ssid, password)
  - Replace Serial.write() with WiFi.write() or UDP/TCP socket
  - Baud rate doesn't apply to WiFi
  
  #include <WiFi.h>
  
  char ssid[] = "YOUR_SSID";
  char pass[] = "YOUR_PASSWORD";
  int status = WL_IDLE_STATUS;
  
  WiFiServer server(9000);
  WiFiClient client;
  
  void setup_wifi() {
    while (status != WL_CONNECTED) {
      status = WiFi.begin(ssid, pass);
      delay(10000);
    }
    server.begin();
  }
  
  void loop_wifi() {
    // Accept incoming connections
    if (!client.connected()) {
      client = server.available();
    } else {
      // Send sensor data via TCP
      client.write(0xAA);
      // ... rest of protocol ...
      
      // Receive commands
      while (client.available() > 0) {
        handle_wifi_command(client.read());
      }
    }
  }
*/
