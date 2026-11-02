# The Mummy

A first-person 3D tomb-escape game that runs in the browser (Three.js), with an optional Python server for a shared leaderboard.

You are trapped in a randomly generated labyrinth. Collect every **golden scarab** to unseal the exit door, then step through it to go deeper. Your torch burns down over time, so grab **oil jars** to refuel. The dimmer your torch, the less you can see, but the harder you are for mummies to spot. Mummies wander until they see you, then hunt you through the corridors, following your last known position.

Each level is bigger, with more scarabs, more mummies, and faster mummies.

## Run it

**With the leaderboard server (Python 3.8+, standard library only):**

```bash
cd games/the_mummy
python server.py          # then open http://localhost:8000
```

Options: `--host 0.0.0.0` to allow other machines on your network to connect, `--port 9000` to change the port.

**Without a server:** open `static/index.html` directly in a browser. Scores are then kept in that browser's local storage.

An internet connection is needed the first time, because Three.js loads from cdnjs.

## Controls

| Key | Action |
|---|---|
| W A S D / arrows | Move |
| Mouse | Look (click the game to capture the mouse) |
| Shift | Sprint (uses stamina) |
| Esc / P | Pause |

Desktop with keyboard and mouse only; there are no touch controls yet.

## Scoring

- Scarab: 100
- Oil jar: 25
- Escaping a level: 500 × level, plus a time bonus for beating par (60 s + 30 s per level)

## Files

- `server.py`: static file server plus `GET/POST /api/scores` (SQLite, `scores.db`)
- `static/index.html`, `static/style.css`: page, HUD and menus
- `static/game.js`: everything else (maze generation, procedural textures, mummy AI, audio)

Scores are computed in the browser, so the leaderboard is for fun and is not cheat-proof.
