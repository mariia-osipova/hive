# Hive

Browser-playable Hive board game. The app is intentionally static: open
`index.html` from a web server and it is ready to deploy.

## Run locally

```bash
python3 -m http.server 4173
```

Open <http://localhost:4173>.

## Deploy

Import this repository into Google AI Studio Build mode, or deploy the
repository root as a static site. No build command is required. The browser
version contains the interactive board, hand selection, placement, stacking,
and movement for the main Hive pieces.

The placement sound is loaded from
`sounds/ElevenLabs_satisfying_card_flip_asmr.mp3`. Add that file before
deploying if audio is needed.
