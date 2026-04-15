# Discord Music Bot

Ein Discord Bot, der Musik von YouTube streamt mit Queue-System, Loop, Lautstärkeregelung und mehr.

## Features

- `/play <query>`: Suche nach YouTube-Videos und füge sie zur Queue hinzu. Spielt automatisch ab.
- `/stop`: Stoppt die Musik und verlässt den Voice-Kanal.
- Steuerungs-Buttons: Skip ⏭️, Loop 🔁, Stop ⏹️, Volume 🔊 🔉
- Queue-System
- Loop-Funktion
- Lautstärkeregelung
- Automatisches Disconnect nach 5 Minuten Inaktivität
- Unterstützt mehrere Voice-Kanäle (pro Server)

## Installation

1. Stelle sicher, dass Python 3.8+ installiert ist.
2. Installiere die Abhängigkeiten: `pip install -r requirements.txt`
3. Installiere FFmpeg (für Audio-Streaming):
   - Windows: Lade von https://ffmpeg.org/download.html herunter und füge zum PATH hinzu.
4. Setze die Umgebungsvariable `DISCORD_BOT_TOKEN` auf deinen Bot-Token.
5. Starte den Bot: `python main.py`

## Verwendung

Lade den Bot zu deinem Server ein und verwende die Slash-Befehle.

Stelle sicher, dass der Bot die Berechtigung für Voice hat.
