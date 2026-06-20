# PoolLab Local

Lokale Bluetooth-Integration für **PoolLab 1.0** Wassertester in Home
Assistant – über die offizielle BLE-API, ganz ohne Cloud.

> **Status:** Dieser Code wurde anhand der offiziellen [PoolLab 1.0
> Bluetooth API Dokumentation](https://poollab.org/static/api/BLE.pdf)
> (Water-i.d. GmbH, Version 2) implementiert, aber **noch nicht an
> echter Hardware getestet**. Bitte beim ersten Einsatz die Logs im
> Auge behalten (`custom_components.poollab_local: debug` in
> `configuration.yaml` unter `logger.logs`) und Probleme als Issue
> melden.

## Funktionen

- Automatische Erkennung des PoolLab 1.0 über Home Assistants
  Bluetooth-Integration (Service-UUID-Match)
- Liest beim Polling alle gespeicherten Messergebnisse vom Gerät aus
  (`PCMD_API_GET_INFO` + `PCMD_API_GET_MEASURES`)
- Legt pro gefundenem Messwert-Typ (pH, freies Chlor, Brom, …)
  automatisch einen eigenen Sensor an – nur die jeweils neueste
  Messung pro Typ wird als aktueller Wert übernommen
- Batterie-Sensor
- Volle Funktion ohne Internet/Cloud – funktioniert auch über einen
  ESPHome-Bluetooth-Proxy, wenn der HA-Host selbst keinen Bluetooth-
  Empfang hat

## Voraussetzungen

- Home Assistant mit aktivierter Bluetooth-Integration
- Bluetooth-Empfang in Reichweite des PoolLab-Geräts (eingebauter
  Adapter am HA-Host oder ein ESPHome Bluetooth-Proxy)
- `bleak-retry-connector` (wird automatisch über `manifest.json`
  installiert)

## Installation über HACS

1. HACS → drei Punkte oben rechts → **"Custom repositories"**
2. Repository-URL eintragen:
   `https://github.com/mf76130/ha-poollab-local`
3. Kategorie: **Integration**
4. In HACS nach "PoolLab Local" suchen, installieren, Home Assistant
   neu starten
5. **Einstellungen → Geräte & Dienste**: Wird das PoolLab-Gerät per
   Bluetooth erkannt, erscheint automatisch ein Vorschlag zum
   Einrichten. Andernfalls über "Integration hinzufügen" → "PoolLab
   Local" manuell aus der Liste der sichtbaren Geräte auswählen.

## Manuelle Installation

Den Ordner `custom_components/poollab_local` in das
`custom_components`-Verzeichnis deiner Home-Assistant-Konfiguration
kopieren und Home Assistant neu starten.

## Wie es technisch funktioniert

Das PoolLab 1.0 implementiert einen eigenen GATT-Service
(`PoolLabSvc`) mit drei Characteristics für ein
Command-and-Response-Schema:

1. Befehl wird auf `CommandMOSI` geschrieben (Preamble `0xAB` + 16-Bit
   Command-ID + Parameter)
2. Das Gerät meldet per Notification auf `MISO_Signal`, dass eine
   Antwort bereit ist
3. Die eigentliche Antwort wird von `CommandMISO` gelesen

Diese Integration ruft beim Polling zunächst `PCMD_API_GET_INFO` ab
(liefert u.a. die Anzahl gespeicherter Ergebnisse und den
Batteriestand) und liest anschließend alle Messergebnisse über
`PCMD_API_GET_MEASURES` aus den 16 Flash-Zellen des Geräts.

## Bekannte Einschränkungen

- Es wird nur **gelesen** – Schreibbefehle wie Kontrast oder
  Einheiten-Umschaltung (ppm/mg-L) sind im Code vorbereitet
  (`const.py`), aber noch nicht als Services/Entities exponiert
- Das Gerät erlaubt nur eine aktive BLE-Verbindung gleichzeitig –
  während des Pollings kann sich z.B. die PoolLab-App nicht
  gleichzeitig verbinden
- Standard-Poll-Intervall: 5 Minuten (`UPDATE_INTERVAL_SECONDS` in
  `const.py`)

## Lizenz

Siehe `LICENSE` im Repository-Root.
