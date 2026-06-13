#!/bin/bash

COMPOSE_FILE="./compose.yaml"
# Tjek om config-filen IKKE eksisterer
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Fandt ikke $COMPOSE_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./compose.yaml.example" "$COMPOSE_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $COMPOSE_FILE findes allerede. Gør intet."
fi

#nodered
sudo chown 1000:1000 ./runtime/nodered/data/

# FSR_listener
CONFIG_FILE="./runtime/FSR_listener/config.json"
# Tjek om config-filen IKKE eksisterer
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Fandt ikke $CONFIG_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./runtime/FSR_listener/config.json.example" "$CONFIG_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $CONFIG_FILE findes allerede. Gør intet."
fi

# FSR_telegram
CONFIG_FILE="./runtime/FSR_telegram/data/config.json"
# Tjek om config-filen IKKE eksisterer
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Fandt ikke $CONFIG_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./runtime/FSR_telegram/data/config.json.example" "$CONFIG_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $CONFIG_FILE findes allerede. Gør intet."
fi

#mosquitto
PASSWD_FILE="./runtime/mosquitto/passwd"
CONFIG_FILE="./runtime/mosquitto/mosquitto.conf"
SERVERCRT_FILE="./runtime/mosquitto/certs/ovhserver.crt"
SERVERKEY_FILE="./runtime/mosquitto/certs/ovhserver.key"
PSK_FILE="./runtime/mosquitto/certs/psk_file.txt"
ROOTCA_FILE="./runtime/mosquitto/certs/rootCA.crt"
# Tjek om passwd-filen IKKE eksisterer
if [ ! -f "$PASSWD_FILE" ]; then
    echo "Fandt ikke $PASSWD_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./runtime/mosquitto/example/passwd" "$PASSWD_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $PASSWD_FILE findes allerede. Gør intet."
fi
# Tjek om config-filen IKKE eksisterer
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Fandt ikke $CONFIG_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./runtime/mosquitto/example/config.conf" "$CONFIG_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $CONFIG_FILE findes allerede. Gør intet."
fi
# Tjek om servercrt-filen IKKE eksisterer
if [ ! -f "$SERVERCRT_FILE" ]; then
    echo "Fandt ikke $SERVERCRT_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./runtime/mosquitto/example/certs/ovhserver.crt" "$SERVERCRT_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $SERVERCRT_FILE findes allerede. Gør intet."
fi
# Tjek om serverkey-filen IKKE eksisterer
if [ ! -f "$SERVERKEY_FILE" ]; then
    echo "Fandt ikke $SERVERKEY_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./runtime/mosquitto/example/certs/ovhserver.key" "$SERVERKEY_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $SERVERKEY_FILE findes allerede. Gør intet."
fi
# Tjek om psk-filen IKKE eksisterer
if [ ! -f "$PSK_FILE" ]; then
    echo "Fandt ikke $PSK_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./runtime/mosquitto/example/certs/psk_file.txt" "$PSK_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $PSK_FILE findes allerede. Gør intet."
fi
# Tjek om rootca-filen IKKE eksisterer
if [ ! -f "$ROOTCA_FILE" ]; then
    echo "Fandt ikke $ROOTCA_FILE. Kopierer eksempelfil..."
    # Kopier eksempelfilen
    cp "./runtime/mosquitto/example/certs/rootCA.crt" "$ROOTCA_FILE"
    echo "✓ Filen blev kopieret."
else
    echo "✓ $ROOTCA_FILE findes allerede. Gør intet."
fi
sudo chmod 0700 ./runtime/mosquitto/certs/psk_file.txt



