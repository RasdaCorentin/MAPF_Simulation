#!/usr/bin/env bash

FILE="$(basename "$1")"
DIR="$(dirname "$(realpath "$1")")"

if [[ -z "$FILE" ]]; then
  echo "Usage: $0 fichier.puml"
  exit 1
fi

echo "👀 Surveillance de $DIR/$FILE (Ctrl+C pour arrêter)"

inotifywait -m \
  -e close_write \
  -e moved_to \
  -e create \
  --format '%f' \
  "$DIR" | while read CHANGED; do

  if [[ "$CHANGED" == "$FILE" ]]; then
    echo "♻️  Regénération PlantUML..."
    plantuml "$DIR/$FILE"
  fi
done

