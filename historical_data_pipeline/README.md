# Historical Weather, Holiday, and Disaster Data Collector

A Python script and data pipeline for gathering daily historical weather data, public holidays, and nearby natural disaster events for any given city and date range. This is especially useful for building machine learning datasets, time-series forecasting, or environmental risk analysis.

---

## Features

- **Geocoding:** Automatically fetches latitude, longitude, and timezone for any city using the Open-Meteo Geocoding API.
- **Meteorological Seasonality:** Dynamically calculates seasonal indicators based on the northern or southern hemisphere.
- **Historical Weather:** Pulls daily metrics (temperatures, apparent temperatures, precipitation, rain, snowfall, and max wind speeds) via Open-Meteo.
- **Holiday Calendar:** Identifies local public holidays and occasions using the Python `holidays` library.
- **Natural Disasters:** Queries the GDACS (Global Disaster Alert and Coordination System) API to track nearby earthquakes, tropical cyclones, floods, volcanoes, wildfires, and droughts within a specified radius and date window.
- **Flexible Execution:** Supports both **Command-Line Interface (CLI)** arguments and **Jupyter Notebook** integration.

---

## Prerequisites & Installation

Make sure you have Python 3.8+ installed. Then install the required dependencies:

```bash
pip install pandas requests holidays tqdm

## Usage

You can use this pipeline either via the **Command-Line Interface (CLI)** for quick exports or by importing it directly into a **Jupyter Notebook** for data analysis and machine learning workflows.

### 1. Command-Line Interface (CLI)

Run the script from your terminal to collect data day-by-day, preview the results, and save them automatically to a CSV file.

```bash
python dataset_builder/pipeline.py --city "Multan" --country "Pakistan" --start "2026-01-01" --end "2026-01-07" --output "multan_data.csv"