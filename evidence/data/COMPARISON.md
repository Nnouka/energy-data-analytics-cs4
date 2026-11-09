# Facility data: EAE download vs class CSV

Files
- `uganda_health_facilities_eae.geojson` (copy of downloaded `c1e04dd8-fb9b-4baa-8521-67dad14f1303`): the Health facilities layer from Energy Access Explorer, 4,938 point features.
- `92d86705-bc3b-495d-bd32-b45ee5c46072`: a GeoTIFF raster (not facility data).
- `shared-in-class-group/Uganda_Health_Facilities_Converted.csv`: class-shared CSV, 4,938 rows.

## Verdict: same dataset
- Same 4,938 facilities, same FID keys, same 34 attribute columns. The CSV adds only `long/lat` (a string of the coordinates).
- Identical on district, coordinates, electrification status, level, ownership and catchment population (0 differences).
- Only differences:
  - FID 4935 (last row): the CSV has blank Beds, Peak_pw_kW, Avg_kWh_d, Avg_kWh_y and pop. The GeoJSON has them (20 beds, 24.17 kW peak, 229.29 kWh/day, 83,694 kWh/yr, pop 12,632). Use the GeoJSON values.
  - 2 facility names differ by whitespace only (FID 4125, 3967: double space vs single space).

## Electrification status (all 4,938)
| Status | Facilities | Share |
|---|---|---|
| On-grid | 2,673 | 54% |
| Off-grid | 1,553 | 31% |
| No | 582 | 12% |
| Data unavailable | 130 | 3% |

Candidates for intervention: "No" (582, of which 547 are HC II and 33 HC III) and "Off-grid" (1,553, mostly HC II/III; the 1,109 HC II dominate). Off-grid may mean unreliable solar; check `ELECTRICIT` source.

## Data-quality flags for the report
- `Catch_pop` is a coarse, rounded field (minimum 5,000, 340 missing, odd values up to 10,000,000, e.g. 500,000 for one hospital). Do not sum it as people reached.
- `pop` (0 missing) looks like a GIS-derived population near the facility (median ~3,000). Prefer `pop` for people-reached, and state the assumption.
- Energy fields (`Avg_kWh_d`, `Peak_pw_kW`) are missing for 514 facilities (mostly the ones not assessed by the demand model); a fallback by facility level is needed.
- `ERT_status`: 4,130 "No", 486 ERT2, 184 ERT3, 138 ERT1 (ERT = Energy for Rural Transformation programme; check whether ERT facilities are already funded and exclude them).
- Distance to grid is not in this file; compute it from the Distribution Lines layer (not yet obtained).
