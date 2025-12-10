#include <Arduino.h>
#include "secrets.h"
#include "mbedtls/md.h"

# define STATUS_LED_PIN 2

void setup(){
  Serial.begin(115200);
  
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, LOW);
}

// this fuction takes a text string, mixes with MY KEy, and returns a signature
String calculateHMAC(String payload){
  byte hmacResult[32];

  mbedtls_md_context_t ctx;
  mbedtls_md_type_t md_type = MBEDTLS_MD_SHA256;

  const size_t keyLength = strlen(SECRET_KEY);
  const size_t payloadLength = payload.length();

  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, mbedtls_md_info_from_type(md_type), 1);
  mbedtls_md_hmac_starts(&ctx, (const unsigned char*) SECRET_KEY, keyLength);
  mbedtls_md_hmac_update(&ctx, (const unsigned char*) payload.c_str(), payloadLength);
  mbedtls_md_hmac_finish(&ctx, hmacResult);
  mbedtls_md_free(&ctx);

  String hexString = "";
  for (int i = 0; i < 32; i++) {
    if (hmacResult[i] < 16) hexString += "0";
    hexString += String(hmacResult[i], HEX);
  }

  return hexString;
}

void loop(){
  if(Serial.available() > 0){
    String challenge = Serial.readStringUntil('\n');
    challenge.trim();

    if (challenge.length() > 0){
      digitalWrite(STATUS_LED_PIN, HIGH);
      String signature = calculateHMAC(challenge);
      Serial.println(signature);
      delay(2000);
      digitalWrite(STATUS_LED_PIN, LOW);
    }
  }
}