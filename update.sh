#!/bin/bash
# Aktualizuje kod z GitHuba i przeladowuje aplikacje na PythonAnywhere.
# Wymaga pliku ~/.pa_token z tokenem API (patrz README w repo) - NIE trzymac tokenu w repo.

set -e

PA_USERNAME="schabowyxxx"
PA_DOMAIN="schabowyxxx.pythonanywhere.com"
TOKEN_FILE="$HOME/.pa_token"

if [ ! -f "$TOKEN_FILE" ]; then
  echo "Brak pliku $TOKEN_FILE z tokenem API. Utworz go: echo 'TWOJ_TOKEN' > $TOKEN_FILE"
  exit 1
fi

PA_TOKEN=$(cat "$TOKEN_FILE")

cd "$(dirname "$0")"
git pull

curl -s -X POST \
  -H "Authorization: Token ${PA_TOKEN}" \
  "https://www.pythonanywhere.com/api/v0/user/${PA_USERNAME}/webapps/${PA_DOMAIN}/reload/" \
  -o /dev/null -w "Reload status: %{http_code}\n"
