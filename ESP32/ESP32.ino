#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(0x40);

// ======================================================
// SERVO CONFIG
// ======================================================
const uint8_t NUM_SERVOS = 4;
const uint8_t servoChannels[NUM_SERVOS] = {0, 1, 2, 3};
const char* servoNames[NUM_SERVOS] = {
  "right_shoulder",
  "left_shoulder",
  "right_leg",
  "left_leg"
};

// Your limits / home positions
const uint16_t SERVO_MIN_US[NUM_SERVOS]  = {1600, 800, 2200, 800};
const uint16_t SERVO_MAX_US[NUM_SERVOS]  = {2200, 1400, 8000, 2200};
const uint16_t SERVO_HOME_US[NUM_SERVOS] = {1900, 1100, 1400, 1350};

// Direction signs
const int8_t SERVO_SIGN[NUM_SERVOS] = {+1, -1, +1, -1};

// Servo frequency
const uint16_t SERVO_FREQ = 50;

// Smooth motion settings
const unsigned long UPDATE_INTERVAL_MS = 20;
const uint16_t STEP_US = 20;

// Gait timing
const unsigned long GAIT_TOGGLE_MS = 240;

// Pose amplitudes
const int SHOULDER_SWING_US = 120;
const int LEG_SWING_US = 160;
const int TURN_SHOULDER_US = 90;
const int TURN_LEG_US = 120;

// ======================================================
// GLOBAL STATE
// ======================================================
enum MotionMode {
  MODE_STOP,
  MODE_FORWARD,
  MODE_BACKWARD,
  MODE_LEFT,
  MODE_RIGHT
};

MotionMode currentMode = MODE_STOP;

uint16_t currentUs[NUM_SERVOS];
uint16_t targetUs[NUM_SERVOS];

unsigned long lastUpdateMs = 0;
unsigned long lastGaitToggleMs = 0;
bool gaitPhase = false;

// Non-blocking serial buffer
String serialLine = "";

// ======================================================
// HELPERS
// ======================================================
uint16_t usToTicks(uint16_t us) {
  return (uint16_t)((us * 4096.0) / 20000.0);
}

uint16_t clampServoUs(uint8_t idx, int valueUs) {
  if (valueUs < SERVO_MIN_US[idx]) valueUs = SERVO_MIN_US[idx];
  if (valueUs > SERVO_MAX_US[idx]) valueUs = SERVO_MAX_US[idx];
  return (uint16_t)valueUs;
}

void writeServoUs(uint8_t idx, uint16_t us) {
  us = clampServoUs(idx, us);
  pca.setPWM(servoChannels[idx], 0, usToTicks(us));
  currentUs[idx] = us;
}

void setTargetUs(uint8_t idx, int us) {
  targetUs[idx] = clampServoUs(idx, us);
}

void setTargetHomeAll() {
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    targetUs[i] = SERVO_HOME_US[i];
  }
}

int applySignedOffset(uint8_t idx, int offsetUs) {
  return (int)SERVO_HOME_US[idx] + (SERVO_SIGN[idx] * offsetUs);
}

void printStatus() {
  Serial.println();
  Serial.println("===== CURRENT SERVO STATUS =====");
  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    Serial.print("Servo ");
    Serial.print(i);
    Serial.print(" (");
    Serial.print(servoNames[i]);
    Serial.print(") current=");
    Serial.print(currentUs[i]);
    Serial.print(" us target=");
    Serial.print(targetUs[i]);
    Serial.print(" us home=");
    Serial.print(SERVO_HOME_US[i]);
    Serial.println(" us");
  }
  Serial.println("===============================");
  Serial.println();
}

void printHelp() {
  Serial.println();
  Serial.println("===== COMMANDS =====");
  Serial.println("Fast commands:");
  Serial.println("  F  B  L  R  S");
  Serial.println("Legacy commands:");
  Serial.println("  MOVE:forward");
  Serial.println("  MOVE:backward");
  Serial.println("  MOVE:left");
  Serial.println("  MOVE:right");
  Serial.println("  MOVE:stop");
  Serial.println("Debug commands:");
  Serial.println("  home");
  Serial.println("  status");
  Serial.println("  help");
  Serial.println("====================");
  Serial.println();
}

// ======================================================
// MODE SETTERS
// ======================================================
void applyStopPose() {
  setTargetHomeAll();
  currentMode = MODE_STOP;
  Serial.println("ACK:S");
}

void applyForwardPose() {
  currentMode = MODE_FORWARD;
  Serial.println("ACK:F");
}

void applyBackwardPose() {
  currentMode = MODE_BACKWARD;
  Serial.println("ACK:B");
}

void applyLeftPose() {
  currentMode = MODE_LEFT;
  Serial.println("ACK:L");
}

void applyRightPose() {
  currentMode = MODE_RIGHT;
  Serial.println("ACK:R");
}

// ======================================================
// COMMAND HANDLERS
// ======================================================
void handleMoveWord(String moveCmd) {
  moveCmd.trim();
  moveCmd.toLowerCase();

  if (moveCmd == "forward") {
    applyForwardPose();
  }
  else if (moveCmd == "backward") {
    applyBackwardPose();
  }
  else if (moveCmd == "left") {
    applyLeftPose();
  }
  else if (moveCmd == "right") {
    applyRightPose();
  }
  else if (moveCmd == "stop") {
    applyStopPose();
  }
  else {
    Serial.print("ERR:UNKNOWN_MOVE:");
    Serial.println(moveCmd);
  }
}

void handleFastCommand(String cmd) {
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "F") {
    applyForwardPose();
    return;
  }
  if (cmd == "B") {
    applyBackwardPose();
    return;
  }
  if (cmd == "L") {
    applyLeftPose();
    return;
  }
  if (cmd == "R") {
    applyRightPose();
    return;
  }
  if (cmd == "S") {
    applyStopPose();
    return;
  }
}

void handleDebugCommand(String cmd) {
  String lc = cmd;
  lc.trim();
  lc.toLowerCase();

  if (lc == "help") {
    printHelp();
  }
  else if (lc == "status") {
    printStatus();
  }
  else if (lc == "home") {
    applyStopPose();
    Serial.println("Moved to home pose");
  }
  else {
    Serial.print("ERR:UNKNOWN_CMD:");
    Serial.println(cmd);
  }
}

void handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  // Fast single-letter commands
  if (cmd == "F" || cmd == "B" || cmd == "L" || cmd == "R" || cmd == "S") {
    handleFastCommand(cmd);
    return;
  }

  // Legacy format
  if (cmd.startsWith("MOVE:")) {
    String moveCmd = cmd.substring(5);
    handleMoveWord(moveCmd);
    return;
  }

  // Also allow just words
  String lowerWord = cmd;
  lowerWord.toLowerCase();
  if (lowerWord == "forward" || lowerWord == "backward" || lowerWord == "left" || lowerWord == "right" || lowerWord == "stop") {
    handleMoveWord(lowerWord);
    return;
  }

  handleDebugCommand(cmd);
}

// ======================================================
// NON-BLOCKING SERIAL
// ======================================================
void serviceSerialInput() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();

    if (c == '\r') {
      continue;
    }

    if (c == '\n') {
      String line = serialLine;
      serialLine = "";
      line.trim();
      if (line.length() > 0) {
        handleCommand(line);
      }
      continue;
    }

    if (serialLine.length() < 128) {
      serialLine += c;
    } else {
      serialLine = "";
      Serial.println("ERR:LINE_TOO_LONG");
    }
  }
}

// ======================================================
// GAIT LOGIC
// ======================================================
void serviceGait() {
  unsigned long now = millis();

  if (currentMode == MODE_STOP) return;
  if (now - lastGaitToggleMs < GAIT_TOGGLE_MS) return;

  lastGaitToggleMs = now;
  gaitPhase = !gaitPhase;

  if (currentMode == MODE_FORWARD) {
    if (!gaitPhase) {
      setTargetUs(0, applySignedOffset(0, +SHOULDER_SWING_US));
      setTargetUs(1, applySignedOffset(1, -SHOULDER_SWING_US));
      setTargetUs(2, applySignedOffset(2, +LEG_SWING_US));
      setTargetUs(3, applySignedOffset(3, -LEG_SWING_US));
    } else {
      setTargetUs(0, applySignedOffset(0, -SHOULDER_SWING_US));
      setTargetUs(1, applySignedOffset(1, +SHOULDER_SWING_US));
      setTargetUs(2, applySignedOffset(2, -LEG_SWING_US));
      setTargetUs(3, applySignedOffset(3, +LEG_SWING_US));
    }
  }
  else if (currentMode == MODE_BACKWARD) {
    if (!gaitPhase) {
      setTargetUs(0, applySignedOffset(0, -SHOULDER_SWING_US));
      setTargetUs(1, applySignedOffset(1, +SHOULDER_SWING_US));
      setTargetUs(2, applySignedOffset(2, -LEG_SWING_US));
      setTargetUs(3, applySignedOffset(3, +LEG_SWING_US));
    } else {
      setTargetUs(0, applySignedOffset(0, +SHOULDER_SWING_US));
      setTargetUs(1, applySignedOffset(1, -SHOULDER_SWING_US));
      setTargetUs(2, applySignedOffset(2, +LEG_SWING_US));
      setTargetUs(3, applySignedOffset(3, -LEG_SWING_US));
    }
  }
  else if (currentMode == MODE_LEFT) {
    if (!gaitPhase) {
      setTargetUs(0, applySignedOffset(0, +TURN_SHOULDER_US));
      setTargetUs(1, applySignedOffset(1, -TURN_SHOULDER_US));
      setTargetUs(2, applySignedOffset(2, -TURN_LEG_US));
      setTargetUs(3, applySignedOffset(3, +TURN_LEG_US));
    } else {
      setTargetUs(0, SERVO_HOME_US[0]);
      setTargetUs(1, SERVO_HOME_US[1]);
      setTargetUs(2, SERVO_HOME_US[2]);
      setTargetUs(3, SERVO_HOME_US[3]);
    }
  }
  else if (currentMode == MODE_RIGHT) {
    if (!gaitPhase) {
      setTargetUs(0, applySignedOffset(0, -TURN_SHOULDER_US));
      setTargetUs(1, applySignedOffset(1, +TURN_SHOULDER_US));
      setTargetUs(2, applySignedOffset(2, +TURN_LEG_US));
      setTargetUs(3, applySignedOffset(3, -TURN_LEG_US));
    } else {
      setTargetUs(0, SERVO_HOME_US[0]);
      setTargetUs(1, SERVO_HOME_US[1]);
      setTargetUs(2, SERVO_HOME_US[2]);
      setTargetUs(3, SERVO_HOME_US[3]);
    }
  }
}

// ======================================================
// SMOOTH SERVO UPDATE
// ======================================================
void serviceServoMotion() {
  unsigned long now = millis();
  if (now - lastUpdateMs < UPDATE_INTERVAL_MS) return;
  lastUpdateMs = now;

  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    int cur = currentUs[i];
    int tgt = targetUs[i];

    if (cur < tgt) {
      cur += STEP_US;
      if (cur > tgt) cur = tgt;
    } else if (cur > tgt) {
      cur -= STEP_US;
      if (cur < tgt) cur = tgt;
    }

    writeServoUs(i, cur);
  }
}

// ======================================================
// SETUP / LOOP
// ======================================================
void setup() {
  Serial.begin(115200);
  Serial.setTimeout(10);

  Wire.begin();
  pca.begin();
  pca.setPWMFreq(SERVO_FREQ);
  delay(300);

  for (uint8_t i = 0; i < NUM_SERVOS; i++) {
    currentUs[i] = clampServoUs(i, SERVO_HOME_US[i]);
    targetUs[i] = currentUs[i];
    writeServoUs(i, currentUs[i]);
  }

  currentMode = MODE_STOP;

  Serial.println();
  Serial.println("ESP32 servo controller ready");
  printHelp();
}

void loop() {
  serviceSerialInput();
  serviceGait();
  serviceServoMotion();
}