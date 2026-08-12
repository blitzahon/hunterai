# RAG Agent — React frontend

A Vite + React chat UI that talks to the Flask backend (`../api.py`).

## Setup

```cmd
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173.

Make sure the Flask backend is running in a separate terminal first:

```cmd
cd ..
python api.py
```

That serves the API on http://localhost:5000, which this frontend calls
via `fetch` (CORS is already enabled on the Flask side in `api.py`).

## Building for production

```cmd
npm run build
```

Outputs static files to `frontend/dist/`. To have Flask serve those
instead of running two separate dev servers, copy `dist/*` into the
project's `static/` folder (replacing `static/index.html`), or update
`api.py`'s `static_folder` to point at `frontend/dist`.
