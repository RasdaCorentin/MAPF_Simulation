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

  # Regenerate on the watched file itself, but also on any .iuml it
  # includes, in case a future diagram splits its model out again.
  if [[ "$CHANGED" == "$FILE" || "$CHANGED" == *.iuml ]]; then
    echo "♻️  Regénération PlantUML ($CHANGED)..."
    plantuml "$DIR/$FILE"
  fi
done

