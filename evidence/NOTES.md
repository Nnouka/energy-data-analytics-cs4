# CS4 evidence log

Tool URL: https://www.energyaccessexplorer.org/tool/a/?id=5d137d39-e46d-4abc-bfc9-76254501fa09

## Screenshots (screenshots/)
1. 01_health_facilities_layer_added.jpg - Health facilities layer toggled on (Demand category)
2. 02_health_facilities_dataset_info.jpg - dataset description/sources
3. 03_active_layers_health_facilities_demand.jpg - Active Data Layers panel
4. 04_health_facilities_status_categories.jpg - status categories: On-grid / Off-grid / No / Data unavailable
5. 05_analysis_results_panel_default.jpg - default analysis (Energy Access Potential, 1 km2): 243,316 km2 analysed, 224,246 km2 "High"
6. 06_export_options.jpg - export options (pptx, TIFF, priority areas CSV, population/area share CSV)

## Findings
- Health facilities dataset: WRI/Uganda MoH/IIASA/POLIMI/UNHCR, 2023, CC BY 4.0. Source page: https://www.wri.org/research/gis-assessment-electricity-health-care-uganda
- Attributes: name, level, ownership, coordinates, county, subcounty, electrification status, electricity sources, annual and daily electricity requirement, required power capacity, catchment population, number of beds, ERT programme status.
- Citation: Sinclair-Lecaros, Mentis, Mulepo, Falchetta, Stevanato (2023), "A GIS-based demand assessment methodology to estimate electricity requirements for healthcare facilities: a case study for Uganda".
- Prioritization indices available: Energy Access Potential, Demand, Supply, Assistance Need.
- Analysis area levels: 1 km2 raster, Region, Subregion, District, County, Subcounty.
- UI tip (from user): lower analysis opacity to read numbers on the map.

## Not yet done
- Raw facility table (needs source download or in-app data access).
- Configured analysis (layers, filters, weights) and its exports.

## Layer-to-index mapping (explored in the EAE Uganda tool)
Screenshots 07, 08.
- DEMAND index: Relative Wealth Index (-2..2), Population Count (0..20,000 people per cell), Health facilities, Education facilities, Crops, Nighttime Lights (0..68 radiance), Investment Prospectus PURE Projects.
- SUPPLY index: Global Horizontal Irradiation (500..2800 kWh/m2), Windspeed (10/50/100/150/200 m), Operating Transmission Lines, Planned Transmission Lines, Power plants, Distribution Lines, Distribution Lines Planned, Minigrids, Transformers.
- Index definitions (tool About panel):
  - Energy Access Potential = aggregate of all selected Demand + Supply layers (recommended default).
  - Demand Index = weighted aggregate of Demographics + Productive uses layers (higher = more demand).
  - Supply Index = weighted aggregate of Resources + Infrastructure layers (higher = more supply available).
  - Assistance Need Index = high demand, low economic activity, low access to infrastructure/resources (where market assistance is needed most).
- Health facilities layer is categorised by electrification status (On-grid / Off-grid / No / Data unavailable).
- The 1 km2 map shows distance-to-facility style surfaces for point layers; analysis areas can also be aggregated to District/County/Subcounty.
- Cost sources searched (no per-facility USD figure found): Uganda ~9bn UGX for ~980 health-centre solar repairs (~USD 2.6M, programme level; ~USD 2.7k/facility by own division, functionalising not new build); SEforALL/WHO/World Bank "Energizing Health" (USD 4.9bn global, ~USD 5 per person impacted). Need a defensible per-facility cost with a source.

## Ranking v1 (cs4/analysis/rank_facilities.py -> facility_ranking.csv, district_summary.csv, run_report.txt)
- Downloaded layers (evidence/data/<layer>/): relative-wealth-index (3-band float32 raster, EPSG:3857, ~1 km, nodata -2), distribution-lines, distribution-lines-planned, mini-grid, transformers (GeoJSON), global-horizontal-irradiation and nighttime-light (rasters, not yet used). The 776,883-byte int16 TIFFs next to the vector files are 1 km rasters of the same layer (not used; exact vector distances computed instead).
- Pool: status No/Off-grid and ERT_status = No -> 1,559 facilities (of 4,938).
- Lenses (percentile 0-1 inside pool): P = pop x poverty weight (RWI); B = pop x level weight (births proxy); R = region population-share quota fill order. Final = (2P + 3B + 1R) / 6.
- Lens ranks are highly correlated (Spearman 0.81-0.93) because all three use `pop`.
- Supply columns (km to line / transformer / planned line / minigrid, route) do not change the rank.

## Budget selection v1 (cs4/analysis/budget_selection.py -> budget_*.csv, budget_report.txt)
- USD 1,000,000 = 100,000 maintenance reserve (10%, assumption) + 900,000 investable.
- Cost: USD 17,700 base (derived from UNDP Zimbabwe Solar for Health: USD 18.5M / 1,044 systems, from search-result snippets; the primary release returned HTTP 403, NOT verified), scaled by (daily kWh need / pool mean 19.4)^0.6, clipped 0.4-3.0 (assumption). Pool mean cost 14.5k; capped facilities cost 53,100. Same cost used for grid-route and solar-route (no sourced grid cost) - tested at 50% in sensitivity.
- Base plan (final 2-3-1 ranking): 25 facilities, ~511k people (pop field), USD 896k, USD 1.75/person; regions C4/E3/N9/W9.
- Lens-only plans: poorest 49 fac / 940k people; births 23 / 344k; regional 49 / 929k; pure value-for-money 68 / 1.18M (USD 0.76/person).
- Sensitivity: cost x0.5 -> 54 fac; x0.75 -> 36; x1.5 -> 17; x2 -> 12; grid routes at 50% -> 42; reserve 20% -> 20.

## Explorer-run analysis (saved + exported)
- Config: layers = Health facilities (status filter: No + Off-grid only), Population Count, Relative Wealth Index, Nighttime Lights (demand); Global Horizontal Irradiation, Distribution Lines, Planned Distribution Lines, Operating Transmission Lines (supply). Analysis area = District, index = Assistance Need Index. Default layer weights/ranges (not tuned).
- Saved to My EAE as "CS4 Uganda Health Facility Electrification - District Assistance Need (No/Off-grid, demand+supply)". Shareable link: explorer-export/shareable_link.txt (https://www.energyaccessexplorer.org/tool/p?1794202549817; viewers may need permissions).
- Export zip (user-downloaded): explorer-export/202611090737-eae-export.zip, unzipped to explorer-export/unzipped/: eae-summary.pptx, eae-assistance-need-index-map.tif, eae-assistance-need-index-high-priority-areas.csv (146 districts with per-layer values), eae-population-area-share.csv.
- Explorer top-10 districts (ANI): Kalangala, Wakiso, Lamwo, Karenga, Buvuma, Amuru, Kaabong, Amudat, Isingiro, Kasese. Overlap with our facility-based top-10 districts: Isingiro, Kasese (Buvuma appears in our budget plan).
- Population in "high" Assistance Need districts: 1,351,791 people; medium-high 18.8M.
- Screenshots 09-14 document the steps. The ANI district CSV has no facility-level fields.
