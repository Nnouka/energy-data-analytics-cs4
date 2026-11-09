"""CS4: rank unelectrified Ugandan health facilities under three lenses and a weighted merge.

Lenses (each scored 0-1 by percentile within the candidate pool, higher = fund first):
  P  poorest patients    : pop x poverty weight (from Relative Wealth Index at the facility)
  B  most births         : pop x maternity-capacity weight by facility level (births proxy)
  R  regional balance    : population-share quotas by region, filled in best-first order
Final = (WEIGHTS) merge of the three percentile scores.

Supply columns (distance to grid etc.) are reported and decide the electrification route,
but do not change the rank (agreed design).
Run:  python rank_facilities.py
"""
import json, os
import numpy as np, pandas as pd, tifffile, shapely
from shapely.geometry import shape
from pyproj import Transformer
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "evidence", "data")
OUT = HERE

# ---- parameters (all assumptions are visible here) -------------------------------------
WEIGHTS = {"P": 2, "B": 3, "R": 1}
CANDIDATE_STATUS = ["No", "Off-grid"]          # "Data unavailable" excluded
EXCLUDE_ERT = True                              # ERT1/2/3 = already in ERT programme (assumption)
REGION_COL = "REGION"                           # try "SUB_REGION" for finer balance
# births proxy: maternity capacity by level of care (assumption; HC III+ run maternity wards)
LEVEL_BIRTH_W = {"HC II": 0.25, "Clinic": 0.5, "HC III": 1.0, "HC IV": 2.0,
                 "Hospital": 3.0, "RRH": 4.0, "NRH": 4.0, "SC": 0.25}
GRID_ROUTE_KM = 5.0                             # <= this from a line/transformer -> grid extension
# ----------------------------------------------------------------------------------------

def load_fac():
    g = json.load(open(os.path.join(DATA, "uganda_health_facilities_eae.geojson"), encoding="utf-8"))
    df = pd.DataFrame([f["properties"] for f in g["features"]])
    for c in ["LAT", "LONG", "pop", "Catch_pop", "Avg_kWh_d", "Peak_pw_kW", "Beds"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def read_geojson_geoms(path):
    g = json.load(open(path, encoding="utf-8"))
    return [shape(f["geometry"]) for f in g["features"]], [f["properties"] for f in g["features"]]

def pct(s):  # 0-1 percentile, higher value -> higher score
    return s.rank(pct=True, method="average")

fac = load_fac()
fac["in_pool"] = fac.ELECTRIFIC.isin(CANDIDATE_STATUS)
if EXCLUDE_ERT:
    fac["in_pool"] &= fac.ERT_status.eq("No")
pool_n = int(fac.in_pool.sum())

# ---- projections ------------------------------------------------------------------------
to_utm = Transformer.from_crs(4326, 32636, always_xy=True)   # metres for distances
to_merc = Transformer.from_crs(4326, 3857, always_xy=True)   # for rasters
fac["x"], fac["y"] = to_utm.transform(fac.LONG.values, fac.LAT.values)
fac["mx"], fac["my"] = to_merc.transform(fac.LONG.values, fac.LAT.values)

# ---- Relative Wealth Index sample -------------------------------------------------------
rwi_path = os.path.join(DATA, "relative-wealth-index", "4f4d79cf-0af3-4bd5-8e4f-173f224851b1")
t = tifffile.TiffFile(rwi_path); pg = t.pages[0]
arr = pg.asarray().astype(float)[..., 0]
sx, sy, _ = pg.tags[33550].value; _, _, _, ox, oy, _ = pg.tags[33922].value
col = np.floor((fac.mx - ox) / sx).astype(int); row = np.floor((oy - fac.my) / sy).astype(int)
ok = (row >= 0) & (row < arr.shape[0]) & (col >= 0) & (col < arr.shape[1])
rwi = np.full(len(fac), np.nan)
rwi[ok] = arr[row[ok], col[ok]]
rwi[rwi <= -2.0] = np.nan                      # -2 is the raster's no-data value
fac["rwi_raw"] = rwi
# fallback: district median, then region median, then global median
fac["rwi"] = fac.rwi_raw
fac["rwi_src"] = np.where(fac.rwi_raw.notna(), "pixel", "")
for lvl in ["DISTRICT", REGION_COL]:
    med = fac.groupby(lvl).rwi_raw.transform("median")
    m = fac.rwi.isna() & med.notna()
    fac.loc[m, "rwi"] = med[m]; fac.loc[m, "rwi_src"] = lvl.lower() + "_median"
m = fac.rwi.isna(); fac.loc[m, "rwi"] = fac.rwi_raw.median(); fac.loc[m, "rwi_src"] = "national_median"

# ---- Supply side: distance to grid -------------------------------------------------------
def to_utm_geom(geoms):
    return [shapely.transform(g, lambda c: np.column_stack(to_utm.transform(c[:, 0], c[:, 1]))) for g in geoms]

pts = shapely.points(fac.x.values, fac.y.values)
def min_dist_to_geoms(geoms):
    d = np.full(len(fac), np.inf)
    for g in to_utm_geom(geoms):
        d = np.minimum(d, shapely.distance(pts, g))
    return d / 1000.0

lines, _ = read_geojson_geoms(os.path.join(DATA, "distribution-lines", "76e5647f-70fb-4912-bbcb-6c0cab08bb77"))
plan, _ = read_geojson_geoms(os.path.join(DATA, "distribution-lines-planned", "4979ffa7-ec12-4d7b-98a2-564866b92103"))
mini, mini_p = read_geojson_geoms(os.path.join(DATA, "mini-grid", "e552667e-f13f-4822-b19b-5caab0e00f4e"))
tx, _ = read_geojson_geoms(os.path.join(DATA, "transformers", "7e8fe6db-13d9-4685-8bcb-03bd1baccd23"))
fac["km_dist_line"] = min_dist_to_geoms(lines)
fac["km_planned_line"] = min_dist_to_geoms(plan)
fac["km_minigrid"] = min_dist_to_geoms(mini)
txp = []
for g in tx:
    for p in (g.geoms if hasattr(g, "geoms") else [g]): txp.append((p.x, p.y))
txp = np.array(txp); tx_xy = np.column_stack(to_utm.transform(txp[:, 0], txp[:, 1]))
fac["km_transformer"] = cKDTree(tx_xy).query(np.column_stack([fac.x, fac.y]))[0] / 1000.0
fac["km_grid"] = fac[["km_dist_line", "km_transformer"]].min(axis=1)
fac["route"] = np.where(fac.km_grid <= GRID_ROUTE_KM, "grid extension", "solar + battery")
fac.loc[(fac.route == "solar + battery") & (fac.km_minigrid <= 3), "route"] = "solar + battery (minigrid nearby)"

# ---- Lenses -------------------------------------------------------------------------------
P = fac[fac.in_pool].copy()
lo, hi = fac.rwi_raw.min(), fac.rwi_raw.max()
P["poverty_w"] = (hi - P.rwi) / (hi - lo)                   # 0 (richest) .. 1 (poorest)
P["poor_people"] = P["pop"] * P.poverty_w
P["birth_w"] = P.LEVEL.map(LEVEL_BIRTH_W).fillna(0.25)
P["births_idx"] = P["pop"] * P.birth_w
P["P_score"] = pct(P.poor_people)
P["B_score"] = pct(P.births_idx)

# regional balance: region quota share = region's share of ALL facility-catchment population
reg_pop = fac.groupby(REGION_COL)["pop"].sum(); share = reg_pop / reg_pop.sum()
P["region_share"] = P[REGION_COL].map(share)
P["rank_in_region"] = P.groupby(REGION_COL)["pop"].rank(ascending=False, method="first")
P["fill_ratio"] = (P.rank_in_region - 0.5) / (P.region_share * pool_n)   # lower = earlier in a fair fill
P["R_score"] = 1 - P.fill_ratio.rank(pct=True, method="first") + 1.0 / len(P)

W = WEIGHTS; tot = sum(W.values())
P["final_score"] = (W["P"] * P.P_score + W["B"] * P.B_score + W["R"] * P.R_score) / tot
for k in ["P", "B", "R"]:
    P[f"rank_{k}"] = P[f"{k}_score"].rank(ascending=False, method="first").astype(int)
P["rank_final"] = P.final_score.rank(ascending=False, method="first").astype(int)
P = P.sort_values("rank_final")

keep = ["rank_final", "final_score", "rank_P", "rank_B", "rank_R", "P_score", "B_score", "R_score", "FID",
        "FACILITY_N", "LEVEL", "OWNERSHIP", "ELECTRIFIC", "ELECTRICIT", "ERT_status", REGION_COL, "SUB_REGION",
        "DISTRICT", "COUNTY", "SUBCOUNTY", "LAT", "LONG", "pop", "Catch_pop", "Beds", "rwi", "rwi_src",
        "poor_people", "births_idx", "Avg_kWh_d", "Peak_pw_kW", "km_dist_line", "km_transformer", "km_grid",
        "km_planned_line", "km_minigrid", "route"]
keep = list(dict.fromkeys(keep))
P[keep].to_csv(os.path.join(OUT, "facility_ranking.csv"), index=False, encoding="utf-8-sig")

# ---- district roll-up (sum of final scores of facilities in the top 500, plus counts) ------
top = P.head(500)
dist = P.groupby("DISTRICT").agg(region=(REGION_COL, "first"), candidates=("FID", "count"),
                                 pop=("pop", "sum"), mean_final=("final_score", "mean"),
                                 in_top500=("rank_final", lambda s: int((s <= 500).sum())),
                                 mean_rwi=("rwi", "mean"), mean_km_grid=("km_grid", "mean")).reset_index()
dist = dist.sort_values(["in_top500", "mean_final"], ascending=False)
dist.to_csv(os.path.join(OUT, "district_summary.csv"), index=False, encoding="utf-8-sig")

# ---- report --------------------------------------------------------------------------------
rep = []
rep.append(f"All facilities: {len(fac)}  | candidates (No/Off-grid{', ERT=No' if EXCLUDE_ERT else ''}): {pool_n}")
rep.append("RWI source for pool: " + str(P.rwi_src.value_counts().to_dict()))
rep.append("Region shares: " + str((share*100).round(1).to_dict()))
rep.append("Pool by region: " + str(P[REGION_COL].value_counts().to_dict()))
rep.append("Route: " + str(P.route.value_counts().to_dict()))
rep.append("Spearman correlation between lens ranks:\n" + str(P[["rank_P", "rank_B", "rank_R", "rank_final"]].corr(method="spearman").round(2)))
for n in (100, 300, 500):
    s = {k: set(P.nsmallest(n, f"rank_{k}").FID) for k in "PBR"}
    f = set(P.nsmallest(n, "rank_final").FID)
    rep.append(f"Top {n}: final shares with P {len(f&s['P'])}, B {len(f&s['B'])}, R {len(f&s['R'])};  P and B overlap {len(s['P']&s['B'])}")
rep.append("Top 15 districts:\n" + dist.head(15).round(2).to_string(index=False))
rep.append("Top 20 facilities:\n" + P[["rank_final", "FACILITY_N", "LEVEL", "DISTRICT", "ELECTRIFIC", "pop", "rwi", "km_grid", "route", "rank_P", "rank_B", "rank_R"]].head(20).round(2).to_string(index=False))
open(os.path.join(OUT, "run_report.txt"), "w", encoding="utf-8").write("\n\n".join(rep))
print("\n\n".join(rep))
