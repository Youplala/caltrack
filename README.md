# CalTrack 🍽️

A lightweight, self-hosted calorie & macro tracker with a clean mobile-friendly UI.

![Python](https://img.shields.io/badge/Python-3.9+-blue) ![SQLite](https://img.shields.io/badge/SQLite-3-green) ![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Daily tracking** — Log meals (breakfast, lunch, dinner, snacks) with calories & macros
- **Macro targets** — Configurable protein/carb/fat split with TDEE calculation
- **History view** — Browse past days, see trends, track streaks
- **Settings** — Weight, height, age, activity level, deficit goal
- **Dark mode** — Easy on the eyes
- **Mobile-first** — Responsive design, works great on phones
- **Zero dependencies frontend** — Pure vanilla JS, no frameworks

## Quick Start

```bash
# Clone
git clone https://github.com/Youplala/caltrack.git
cd caltrack

# Run
python3 server.py
```

Open `http://localhost:8888/calories/index.html` in your browser.

## API

The Python server exposes a simple REST API:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/calories/index.html` | Serves the web app |
| `GET` | `/api/profile` | Get user profile/settings |
| `PUT` | `/api/profile` | Update profile |
| `GET` | `/api/meals?date=YYYY-MM-DD` | Get meals for a date |
| `POST` | `/api/meals` | Add a meal |
| `DELETE` | `/api/meals/:id` | Delete a meal |

## Stack

- **Backend**: Python 3 + SQLite (single file, no dependencies)
- **Frontend**: Vanilla HTML/CSS/JS with localStorage for settings
- **Database**: SQLite (`calories.db`, auto-created)

## License

MIT
