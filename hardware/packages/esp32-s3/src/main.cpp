/**
 * Firmware MILES Box — relève capteurs → backend box local.
 *
 * Contrat (identique au README) :
 *  - client uniquement : AUCUN port ouvert, AUCUNE connexion entrante ;
 *  - POST /box/ingest toutes les POLL_INTERVAL_MS (défaut 10 s) ;
 *  - LED verte = backend OK, LED rouge = backend injoignable ou config
 *    incomplète ;
 *  - bouton (GPIO0) = envoi immédiat ;
 *  - aucun secret en clair dans le journal série ;
 *  - **aucune valeur inventée** : un capteur absent n'est pas envoyé du tout,
 *    il n'est jamais remplacé par un -1 ou un -99 (DEC-014).
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
#define BACKEND_URL ""
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
bool configurationOk = false;

/** Valeur absente ou laissée à l'état d'exemple. */
bool estPlaceholder(const char *valeur) {
    if (valeur == nullptr || valeur[0] == '\0') {
        return true;
    }
    return strstr(valeur, "REPLACE_ME") != nullptr;
}

/**
 * Une URL de bouclage désigne l'ESP32 lui-même : le PC ne serait jamais
 * joint. C'est l'erreur par défaut d'origine, désormais refusée.
 */
bool urlJoignableDepuisLeBoitier(const char *url) {
    if (strstr(url, "://127.") != nullptr) {
        return false;
    }
    if (strstr(url, "://localhost") != nullptr) {
        return false;
    }
    if (strstr(url, "://0.0.0.0") != nullptr) {
        return false;
    }
    return strncmp(url, "http://", 7) == 0;
}

/** Corps JSON : seuls les relevés réellement mesurés sont inclus. */
String construireCorps(float temperature, bool aTemperature,
                       float humidite, bool aHumidite, int bouton) {
    String corps = "{\"cle\":\"" BOX_KEY "\",\"bouton\":";
    corps += String(bouton);
    if (aTemperature) {
        corps += ",\"temperature\":" + String(temperature, 1);
    }
    if (aHumidite) {
        corps += ",\"humidite\":" + String(humidite, 1);
    }
    corps += "}";
    return corps;
}

/** Envoyer un relevé. Retourner vrai si le backend l'a accepté. */
bool envoyerReleve(float temperature, bool aTemperature,
                   float humidite, bool aHumidite, int bouton) {
    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }
    HTTPClient http;
    http.begin(String(BACKEND_URL) + "/box/ingest");
    http.addHeader("Content-Type", "application/json");
    int code = http.POST(construireCorps(temperature, aTemperature,
                                         humidite, aHumidite, bouton));
    http.end();
    return code >= 200 && code < 300;
}

/**
 * Vérifier que le backend répond, sans rien lui envoyer.
 * Au démarrage, on ne fabrique pas un faux relevé pour tester la liaison.
 */
bool verifierBackend() {
    if (WiFi.status() != WL_CONNECTED) {
        return false;
    }
    HTTPClient http;
    http.begin(String(BACKEND_URL) + "/box/telemetry");
    int code = http.GET();
    http.end();
    return code >= 200 && code < 300;
}

void setup() {
    Serial.begin(115200);
    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_BOUTON, INPUT_PULLUP);
    digitalWrite(PIN_LED, LOW);

    if (estPlaceholder(WIFI_SSID) || estPlaceholder(WIFI_PASS) ||
        estPlaceholder(BOX_KEY) || estPlaceholder(BACKEND_URL)) {
        Serial.println("[miles-box] Configuration incomplete : renseigner "
                       "WIFI_SSID, WIFI_PASS, BACKEND_URL et BOX_KEY a la "
                       "compilation (platformio.ini local, jamais commite).");
        Serial.println("[miles-box] Aucune connexion tentee, aucune donnee "
                       "envoyee. LED rouge.");
        return;
    }
    if (!urlJoignableDepuisLeBoitier(BACKEND_URL)) {
        Serial.println("[miles-box] BACKEND_URL invalide ou de bouclage "
                       "(127.x / localhost / 0.0.0.0) : le PC ne serait "
                       "jamais joint. Indiquer http://<IP_du_PC>:8095.");
        return;
    }

    configurationOk = true;

    WiFi.begin(WIFI_SSID, WIFI_PASS);
    for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
        delay(250);
    }
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[miles-box] WiFi indisponible. LED rouge.");
        return;
    }

    backendOk = verifierBackend();
    digitalWrite(PIN_LED, backendOk ? HIGH : LOW);
    Serial.println(backendOk ? "[miles-box] Backend joignable."
                             : "[miles-box] Backend injoignable.");
}

void loop() {
    if (!configurationOk) {
        delay(1000);
        return;
    }

    bool boutonAppuye = digitalRead(PIN_BOUTON) == LOW;
    unsigned long maintenant = millis();
    if (boutonAppuye || (maintenant - dernierEnvoi >= POLL_INTERVAL_MS)) {
        dernierEnvoi = maintenant;
        // Aucun capteur de température/humidité n'est lu ici : les champs
        // sont omis tant qu'un DHT22 n'est pas câblé ET sa bibliothèque
        // ajoutée au build. Le backend conserve alors le relevé sans valeur,
        // au lieu d'enregistrer un -1 trompeur.
        backendOk = envoyerReleve(0.0f, false, 0.0f, false,
                                  boutonAppuye ? 1 : 0);
        digitalWrite(PIN_LED, backendOk ? HIGH : LOW);
    }
    delay(100);
}
