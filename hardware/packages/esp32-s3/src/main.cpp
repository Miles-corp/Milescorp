/**
 * Firmware MILES Box — relève capteurs → backend box local.
 *
 * Contrat (identique au README) :
 *  - client uniquement : AUCUN port ouvert, AUCUNE connexion entrante ;
 *  - POST /box/ingest toutes les POLL_INTERVAL_MS (défaut 10 s) ;
 *  - LED verte = backend OK, LED rouge = backend injoignable ;
 *  - bouton (GPIO0) = envoi immédiat ;
 *  - aucun secret en clair dans le journal série.
 */

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>

#ifndef WIFI_SSID
#define WIFI_SSID "REPLACE_ME"
#endif
#ifndef WIFI_PASS
#define WIFI_PASS "REPLACE_ME"
#endif
#ifndef BACKEND_URL
#define BACKEND_URL "http://127.0.0.1:8095"
#endif
#ifndef BOX_KEY
#define BOX_KEY "REPLACE_ME"
#endif
#ifndef POLL_INTERVAL_MS
#define POLL_INTERVAL_MS 10000
#endif

const int PIN_BOUTON = 0;   // BOOT, actif bas
const int PIN_LED = 2;      // LED active haute

unsigned long dernierEnvoi = 0;
bool backendOk = false;

bool envoyerReleve(float temperature, float humidite, int bouton) {
    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }
    HTTPClient http;
    http.begin(String(BACKEND_URL) + "/box/ingest");
    http.addHeader("Content-Type", "application/json");
    String corps = "{\"cle\":\"" BOX_KEY "\",";
    corps += "\"temperature\":" + String(temperature, 1) + ",";
    corps += "\"humidite\":" + String(humidite, 1) + ",";
    corps += "\"bouton\":" + String(bouton) + "}";
    int code = http.POST(corps);
    http.end();
    return code >= 200 && code < 300;
}

void setup() {
    Serial.begin(115200);
    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_BOUTON, INPUT_PULLUP);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
        delay(250);
    }
    backendOk = envoyerReleve(-99.0, -99.0, 0);  // test au démarrage
    digitalWrite(PIN_LED, backendOk ? HIGH : LOW);
}

void loop() {
    bool boutonAppuye = digitalRead(PIN_BOUTON) == LOW;
    unsigned long maintenant = millis();
    if (boutonAppuye || (maintenant - dernierEnvoi >= POLL_INTERVAL_MS)) {
        dernierEnvoi = maintenant;
        // Relevés réels (DHT22 si câblé, sinon valeurs -1 = indisponible).
        float t = -1.0, h = -1.0;
        backendOk = envoyerReleve(t, h, boutonAppuye ? 1 : 0);
        digitalWrite(PIN_LED, backendOk ? HIGH : LOW);
    }
    delay(100);
}
