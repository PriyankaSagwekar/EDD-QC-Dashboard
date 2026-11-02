# EDD QA/QC Dashboard

A Streamlit dashboard for the [Automated Environmental QA/QC & EDD Validation Engine](https://github.com/PriyankaSagwekar/EDD-Validation-Engine-and-QA-QC). It shows how laboratory EDDs fared against 36 automated QA/QC rules, where on site the problems are, and how validated results compare with UK screening criteria.

**Live demo:** _link added after deployment_

> The site, laboratory and data are fictional and simulated. Screening criteria are illustrative values, not for real assessment.

## Pages

| Page | What it answers |
|---|---|
| Overview | How many EDDs were loaded, how much was promoted, which batches were NO-GO |
| Exceptions | Which rules failed, filtered by file, family, severity and rule, with CSV download |
| Batch detail | The import decision for one EDD, qualifiers applied and rows held in staging |
| Site map | QC status (RAG) of every borehole, well and trial pit |
| Results explorer | Concentrations over the monitoring rounds, non-detects at the RL, criterion line |
| Screening | Worst exceedance per location and a location × analyte heatmap per criteria set |

## How the data gets here

```
Pipeline repo (laptop)                         This repo
SQL Server EnvDataQC  ── scripts/refresh_data.py ──►  data/envdataqc.duckdb + data/manifest.json
  reporting views (vw_*)                               │ git push
                                                       ▼
                                          Streamlit Community Cloud → public URL
```

- The hosted app never connects to SQL Server. It reads a DuckDB snapshot of the pipeline's reporting views, committed in `data/`.
- `refresh_data.py` copies each view in full, converts British National Grid coordinates to WGS84 for web maps, and writes `manifest.json` (time, pipeline commit, row counts, schema version). The app shows the "data as of" time on every page.
- The import decision on the Batch detail page uses the same rule and threshold as the pipeline's Excel report.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\refresh_data.py          # needs the pipeline's SQL Server
.\.venv\Scripts\python.exe -m streamlit run app.py
.\.venv\Scripts\python.exe -m pytest
```

To update the hosted site after new EDDs have been run through the pipeline:

```powershell
.\.venv\Scripts\python.exe scripts\refresh_data.py --push
```

## ArcGIS Online maps

The Site map, Results explorer and Screening pages embed ArcGIS Online items when their URLs are set in `config/maps.toml`. Until then they show a built-in map drawn from the same data. See the pipeline repo's `docs/ARCGIS_GUIDE.md` for building the maps from `site_qc.gpkg`.

## Deploy (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. At share.streamlit.io choose **Create app**, select this repo, branch `main`, main file `app.py`.
3. The app installs `requirements.txt` only. It does not need any secrets.

Free apps go to sleep when unused and take about 30 seconds to wake.
