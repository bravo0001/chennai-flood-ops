# 🌊 Chennai Flood Early Warning & Emergency Navigation System

Real-time flood depth simulation and flood-aware safe routing for Chennai roads with hospital navigation.

## Features
- 🗺️ 74,425 Chennai roads with organic IDW elevation model
- 🌧️ Live weather ingestion via Open-Meteo API
- 💧 Real-time waterlogging depth simulation
- 🏥 Flood-aware A\* routing to 1,224 hospitals
- 🔧 Municipal manhole/drain incident tracking

## Tech Stack
- **Backend**: FastAPI + Uvicorn
- **Routing**: Custom A\* flood-aware graph algorithm
- **Elevation Model**: Inverse Distance Weighting (18 real Chennai basin anchors)
- **Data**: OpenStreetMap (OSM) + Open-Meteo weather API
- **Frontend**: Vanilla JS + Leaflet.js

## Run Locally
```bash
pip install -r requirements.txt
python enrich_roads.py   # Generate elevation data (first time only)
python app.py
```
Visit: http://localhost:8000

## Deploy to Google Cloud Run
```bash
gcloud run deploy chennai-flood-map \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 1
```

## API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/roads` | GET | All road features with elevation |
| `/api/hospitals` | GET | All medical centers |
| `/api/live-weather` | GET | Real-time Chennai weather |
| `/api/route` | POST | Flood-aware safe route |
| `/api/simulate` | POST | Run flood simulation |
| `/api/manholes` | GET | Drainage asset locations |
| `/api/manhole/report` | POST | Report a blocked drain |
