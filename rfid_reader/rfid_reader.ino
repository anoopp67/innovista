#include <SPI.h>
#include <MFRC522.h>
#include <LiquidCrystal_I2C.h>

#define SS_PIN  10
#define RST_PIN 9

const int GREEN_LED = A0;
const int RED_LED   = A1;
const int BUZZER    = A2;

MFRC522 rfid(SS_PIN, RST_PIN);
LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();
  
  lcd.init();
  lcd.backlight();
  lcd.clear();
  
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED_LED,   OUTPUT);
  pinMode(BUZZER,    OUTPUT);
  
  lcd.print("Attendance Sys");
  lcd.setCursor(0, 1);
  lcd.print("Scan your card");
  
  Serial.println("[ARDUINO] System ready. Waiting for cards...");
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) {
    return;
  }
  
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) {
      uid += "0";
    }
    uid += String(rfid.uid.uidByte[i], HEX);
    if (i < rfid.uid.size - 1) {
      uid += ":";
    }
  }
  uid.toUpperCase();
  
  Serial.println(uid);
  
  lcd.clear();
  lcd.print("Card detected");
  lcd.setCursor(0, 1);
  lcd.print(uid);
  
  unsigned long start = millis();
  String response = "";
  
  while (millis() - start < 3000) {
    if (Serial.available()) {
      response = Serial.readStringUntil('\n');
      response.trim();
      break;
    }
  }
  
  if (response == "OK") {
    digitalWrite(GREEN_LED, HIGH);
    tone(BUZZER, 1000, 200);
    lcd.clear();
    lcd.print("Welcome!");
    delay(2000);
    digitalWrite(GREEN_LED, LOW);
  } else if (response == "FAIL") {
    digitalWrite(RED_LED, HIGH);
    tone(BUZZER, 300, 500);
    lcd.clear();
    lcd.print("Unregistered");
    lcd.setCursor(0, 1);
    lcd.print("Card!");
    delay(2000);
    digitalWrite(RED_LED, LOW);
  } else {
    digitalWrite(RED_LED, HIGH);
    tone(BUZZER, 200, 1000);
    lcd.clear();
    lcd.print("Error: no");
    lcd.setCursor(0, 1);
    lcd.print("response");
    delay(2000);
    digitalWrite(RED_LED, LOW);
  }
  
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  
  lcd.clear();
  lcd.print("Attendance Sys");
  lcd.setCursor(0, 1);
  lcd.print("Scan your card");
  
  delay(500);
}