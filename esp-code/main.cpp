#include <Arduino.h> // Include this if using PlatformIO; optional for Arduino IDE
#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>
#include <Bluepad32.h>

// ---------- I2C / PCA9685 CONFIG ----------

#define I2C_SDA 4
#define I2C_SCL 5

#define PCA9685_ADDR 0x40
Adafruit_PWMServoDriver pca9685 = Adafruit_PWMServoDriver(PCA9685_ADDR);

#define SERVOMIN  80
#define SERVOMAX  600

// PCA9685 channels for servos
#define SERVO0_CH 0    // "servo 1" in your wording
#define SERVO1_CH 1    // "servo 2"
#define SERVO2_CH 2    // "servo 3"

// ---------- SERVO / PRESET CONFIG ----------

// Homes
const int HOME0_ANGLE = 134;  // servo 1 home
const int HOME1_ANGLE = 70;   // servo 2 home
const int HOME2_ANGLE = 90;   // servo 3 home (adjust as needed)

int servo0Angle = HOME0_ANGLE;
int servo1Angle = HOME1_ANGLE;
int servo2Angle = HOME2_ANGLE;

const int JOYSTICK_DEADZONE = 32;

// Joystick ranges around home
const int MAX_DELTA0 = 60;
const int MAX_DELTA1 = 60;
const int MAX_DELTA2 = 60;

// Preset offsets
const int PRESET_OFFSET01_DEG   = 30;  // ±30° for servos 1 & 2 during preset
const int PRESET_OFFSET2_DEG    = 30;  // +30° CW for servo 3
const int PRESET_STEP_DEG       = 2;
const uint16_t PRESET_STEP_MS   = 15;

// Preset state machine:
//   1) servo 3 out
//   2) servos 1 & 2 out
//   3) servo 3 back
//   4) servos 1 & 2 back
enum PresetPhase {
  PRESET_IDLE = 0,
  PRESET_MOVING_OUT_2,
  PRESET_MOVING_OUT_01,
  PRESET_MOVING_BACK_2,
  PRESET_MOVING_BACK_01
};

bool         presetActive      = false;
PresetPhase  presetPhase       = PRESET_IDLE;
int          presetTargetOut0  = HOME0_ANGLE;
int          presetTargetOut1  = HOME1_ANGLE;
int          presetTargetOut2  = HOME2_ANGLE;
uint32_t     lastPresetStepMs  = 0;

// ---------- BLUEPAD32 STATE ----------

ControllerPtr myControllers[BP32_MAX_GAMEPADS];

// ---------- HELPERS ----------

void setServoAngle(uint8_t channel, int angleDeg) {
  angleDeg = constrain(angleDeg, 0, 180);
  uint16_t pulse = map(angleDeg, 0, 180, SERVOMIN, SERVOMAX);
  pca9685.setPWM(channel, 0, pulse);
}

int applyDeadzoneInt(int v, int dz) {
  if (abs(v) < dz) return 0;
  return v;
}

// ---------- PRESET MOTION LOGIC ----------
//
// Sequence when a D-pad preset is triggered:
//   1) servo 3: home -> +30° (CW)
//   2) servos 1 & 2: home -> ±30°
//   3) servo 3: +30° -> home
//   4) servos 1 & 2: ±30° -> home

void startPresetForDpad(int dpadValue) {
  if (presetActive) return;

  int offset0 = 0;
  int offset1 = 0;

  // D-pad behavior for servos 1 & 2:
  if (dpadValue == 1) {
    // Up: servo0 +30°, servo1 -30°
    offset0 = +PRESET_OFFSET01_DEG;
    offset1 = -PRESET_OFFSET01_DEG;
  } else if (dpadValue == 2) {
    // Right: both +30°
    offset0 = +PRESET_OFFSET01_DEG;
    offset1 = +PRESET_OFFSET01_DEG;
  } else if (dpadValue == 8) {
    // Left: both -30°
    offset0 = -PRESET_OFFSET01_DEG;
    offset1 = -PRESET_OFFSET01_DEG;
  } else {
    return;  // ignore other D-pad values
  }

  // Start all servos at home
  servo0Angle = HOME0_ANGLE;
  servo1Angle = HOME1_ANGLE;
  servo2Angle = HOME2_ANGLE;
  setServoAngle(SERVO0_CH, servo0Angle);
  setServoAngle(SERVO1_CH, servo1Angle);
  setServoAngle(SERVO2_CH, servo2Angle);

  // Targets for servos 1 & 2
  presetTargetOut0 = constrain(HOME0_ANGLE + offset0, 0, 180);
  presetTargetOut1 = constrain(HOME1_ANGLE + offset1, 0, 180);

  // Target for servo 3: +30° CW
  presetTargetOut2 = constrain(HOME2_ANGLE + PRESET_OFFSET2_DEG, 0, 180);

  // New sequence: start with servo 3 out
  presetPhase      = PRESET_MOVING_OUT_2;
  presetActive     = true;
  lastPresetStepMs = millis();

  Serial.printf("Preset started: dpad=%d, out0=%d, out1=%d, out2=%d\n",
                dpadValue, presetTargetOut0, presetTargetOut1, presetTargetOut2);
}

void updatePresetMotion() {
  if (!presetActive) return;

  uint32_t now = millis();
  if (now - lastPresetStepMs < PRESET_STEP_MS) return;
  lastPresetStepMs = now;

  switch (presetPhase) {

    case PRESET_MOVING_OUT_2:
      // Step servo 3 toward +30° target
      if (servo2Angle < presetTargetOut2)      servo2Angle += PRESET_STEP_DEG;
      else if (servo2Angle > presetTargetOut2) servo2Angle -= PRESET_STEP_DEG;

      servo2Angle = constrain(servo2Angle, 0, 180);
      setServoAngle(SERVO2_CH, servo2Angle);

      if (abs(servo2Angle - presetTargetOut2) <= PRESET_STEP_DEG) {
        presetPhase = PRESET_MOVING_OUT_01;
      }
      break;

    case PRESET_MOVING_OUT_01:
      // Step servos 1 & 2 toward their ±30° targets
      if (servo0Angle < presetTargetOut0)      servo0Angle += PRESET_STEP_DEG;
      else if (servo0Angle > presetTargetOut0) servo0Angle -= PRESET_STEP_DEG;

      if (servo1Angle < presetTargetOut1)      servo1Angle += PRESET_STEP_DEG;
      else if (servo1Angle > presetTargetOut1) servo1Angle -= PRESET_STEP_DEG;

      servo0Angle = constrain(servo0Angle, 0, 180);
      servo1Angle = constrain(servo1Angle, 0, 180);

      setServoAngle(SERVO0_CH, servo0Angle);
      setServoAngle(SERVO1_CH, servo1Angle);

      if (abs(servo0Angle - presetTargetOut0) <= PRESET_STEP_DEG &&
          abs(servo1Angle - presetTargetOut1) <= PRESET_STEP_DEG) {
        presetPhase = PRESET_MOVING_BACK_2;
      }
      break;

    case PRESET_MOVING_BACK_2:
      // Return servo 3 back to home
      if (servo2Angle < HOME2_ANGLE)      servo2Angle += PRESET_STEP_DEG;
      else if (servo2Angle > HOME2_ANGLE) servo2Angle -= PRESET_STEP_DEG;

      servo2Angle = constrain(servo2Angle, 0, 180);
      setServoAngle(SERVO2_CH, servo2Angle);

      if (abs(servo2Angle - HOME2_ANGLE) <= PRESET_STEP_DEG) {
        presetPhase = PRESET_MOVING_BACK_01;
      }
      break;

    case PRESET_MOVING_BACK_01:
      // Return servos 1 & 2 back to home
      if (servo0Angle < HOME0_ANGLE)      servo0Angle += PRESET_STEP_DEG;
      else if (servo0Angle > HOME0_ANGLE) servo0Angle -= PRESET_STEP_DEG;

      if (servo1Angle < HOME1_ANGLE)      servo1Angle += PRESET_STEP_DEG;
      else if (servo1Angle > HOME1_ANGLE) servo1Angle -= PRESET_STEP_DEG;

      servo0Angle = constrain(servo0Angle, 0, 180);
      servo1Angle = constrain(servo1Angle, 0, 180);

      setServoAngle(SERVO0_CH, servo0Angle);
      setServoAngle(SERVO1_CH, servo1Angle);

      if (abs(servo0Angle - HOME0_ANGLE) <= PRESET_STEP_DEG &&
          abs(servo1Angle - HOME1_ANGLE) <= PRESET_STEP_DEG) {
        presetActive = false;
        presetPhase  = PRESET_IDLE;
        Serial.println("Preset finished: all servos at home.");
      }
      break;

    case PRESET_IDLE:
    default:
      break;
  }
}

// ---------- BLUEPAD32 CALLBACKS ----------

void onConnectedController(ControllerPtr ctl) {
  for (int i = 0; i < BP32_MAX_GAMEPADS; i++) {
    if (myControllers[i] == nullptr) {
      Serial.printf("Controller connected, index=%d\n", i);
      ControllerProperties properties = ctl->getProperties();
      Serial.printf("Model: %s, VID=0x%04x, PID=0x%04x\n",
                    ctl->getModelName().c_str(),
                    properties.vendor_id,
                    properties.product_id);
      myControllers[i] = ctl;
      return;
    }
  }
  Serial.println("Controller connected, but no free slot!");
}

void onDisconnectedController(ControllerPtr ctl) {
  for (int i = 0; i < BP32_MAX_GAMEPADS; i++) {
    if (myControllers[i] == ctl) {
      Serial.printf("Controller disconnected, index=%d\n", i);
      myControllers[i] = nullptr;
      return;
    }
  }
  Serial.println("Controller disconnected, but not found in array");
}

// ---------- GAMEPAD PROCESSING ----------

void processGamepad(ControllerPtr ctl) {
  int dpad = ctl->dpad();

  // Trigger preset on D-pad
  if (!presetActive && dpad != 0) {
    startPresetForDpad(dpad);
  }

  // During presets, ignore joystick control
  if (presetActive) {
    return;
  }

  // Normal joystick behavior:
  //  - left stick Y  -> servo 1 (channel 0)
  //  - right stick Y -> servo 2 (channel 1)
  //  - right stick X -> servo 3 (channel 2)
  int ly = ctl->axisY();
  int ry = ctl->axisRY();
  int rx = ctl->axisRX();

  ly = applyDeadzoneInt(ly, JOYSTICK_DEADZONE);
  ry = applyDeadzoneInt(ry, JOYSTICK_DEADZONE);
  rx = applyDeadzoneInt(rx, JOYSTICK_DEADZONE);

  if (ly != 0) {
    int delta0 = map(ly, -512, 512, -MAX_DELTA0, MAX_DELTA0);
    servo0Angle = HOME0_ANGLE + delta0;
  }

  if (ry != 0) {
    int delta1 = map(ry, -512, 512, -MAX_DELTA1, MAX_DELTA1);
    servo1Angle = HOME1_ANGLE + delta1;
  }