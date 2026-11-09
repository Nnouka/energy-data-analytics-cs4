"""CS4: spend the USD 1,000,000 down the final ranking, compare lens-only plans, run cost sensitivity.

Reads facility_ranking.csv (from rank_facilities.py). Outputs budget_*.csv and budget_report.txt.
Cost model (ALL ASSUMPTIONS, flagged in the report):
  base cost per facility = BASE_COST (USD 17,700 = UNDP Zimbabwe Solar-for-Health programme,
      USD 18.5M / 1,044 systems, as reported by search results; NOT verified against the primary release)
  scaled by the facility's daily energy need relative to the pool median, clipped to [0.5, 4]
  GRID_DISCOUNT: facilities within GRID_ROUTE_KM of the grid cost less (grid extension) - assumption
  MAINT_RESERVE: share of the budget held back for maintenance (assumption)
"""
import os
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
BUDGET = 1_000_000
BASE_COST = 17_700
MAINT_RESERVE = 0.10
GRID_DISCOUNT = 1.0           # base case: no discount (conservative, one sourced number). Tested in sensitivity.
SCALE_CLIP = (0.4, 3.0)
SCALE_EXP = 0.6               # economies of scale: cost ~ energy^0.6 (assumption)

df = pd.read_csv(os.path.join(HERE, "facility_ranking.csv"), encoding="utf-8-sig")

# energy need: fill missing by level median, then by pool median
lvl_med = df.groupby("LEVEL").Avg_kWh_d.transform("median")
df["kwh_d"] = df.Avg_kWh_d.fillna(lvl_med).fillna(df.Avg_kWh_d.median())
df["energy_scale"] = ((df.kwh_d / df.kwh_d.mean()) ** SCALE_EXP).clip(*SCALE_CLIP)   # anchored so pool-average cost ~ BASE_COST
df["is_grid"] = df.route.eq("grid extension")


def cost_vector(mult=1.0, grid_discount=GRID_DISCOUNT):
    c = BASE_COST * mult * df.energy_scale
    return np.where(df.is_grid, c * grid_discount, c)


def select(order_col, ascending, cost, budget):
    """fund in order, skipping facilities that no longer fit"""
    idx = df.sort_values(order_col, ascending=ascending).index
    left, chosen = budget, []
    for i in idx:
        if cost[i] <= left:
            chosen.append(i); left -= cost[i]
    return chosen, budget - left


def summarize(name, chosen, spent, cost):
    s = df.loc[chosen]
    return {"plan": name, "facilities": len(chosen), "spent": round(spent), "people_reached(pop)": int(s["pop"].sum()),
            "births_idx": int(s.births_idx.sum()), "poor_people_idx": int(s.poor_people.sum()),
            "cost_per_person": round(spent / s["pop"].sum(), 2), "avg_cost": round(spent / len(chosen)),
            "grid_route": int(s.is_grid.sum()), "solar_route": int((~s.is_grid).sum()),
            **{f"n_{r}": int((s.REGION == r).sum()) for r in sorted(df.REGION.unique())}}


usable = BUDGET * (1 - MAINT_RESERVE)
cost = cost_vector()
df["est_cost"] = cost
df["value_pop_per_usd"] = df["pop"] / df.est_cost
plans = {}
plans["FINAL (2P+3B+1R)"] = select("rank_final", True, cost, usable)
plans["Lens P: poorest"] = select("rank_P", True, cost, usable)
plans["Lens B: births"] = select("rank_B", True, cost, usable)
plans["Lens R: regional"] = select("rank_R", True, cost, usable)
plans["Value for money (pop per USD)"] = select("value_pop_per_usd", False, cost, usable)

rows = [summarize(k, v[0], v[1], cost) for k, v in plans.items()]
summ = pd.DataFrame(rows)
summ.to_csv(os.path.join(HERE, "budget_plans_comparison.csv"), index=False)

chosen, spent = plans["FINAL (2P+3B+1R)"]
sel = df.loc[chosen].copy().sort_values("rank_final")
sel["cum_cost"] = sel.est_cost.cumsum()
sel.to_csv(os.path.join(HERE, "budget_selected_facilities.csv"), index=False, encoding="utf-8-sig")
dist = sel.groupby(["REGION", "DISTRICT"]).agg(facilities=("FID", "count"), cost=("est_cost", "sum"),
                                               people=("pop", "sum")).reset_index().sort_values("cost", ascending=False)
dist.to_csv(os.path.join(HERE, "budget_selected_by_district.csv"), index=False)

# overlaps with final plan
final_set = set(chosen)
overlap = {k: len(final_set & set(v[0])) for k, v in plans.items()}

# sensitivity
sens = []
base_set = final_set
for label, mult, gd, res in [("cost x0.5", 0.5, GRID_DISCOUNT, MAINT_RESERVE), ("cost x0.75", 0.75, GRID_DISCOUNT, MAINT_RESERVE),
                             ("BASE", 1.0, GRID_DISCOUNT, MAINT_RESERVE), ("cost x1.5", 1.5, GRID_DISCOUNT, MAINT_RESERVE),
                             ("cost x2", 2.0, GRID_DISCOUNT, MAINT_RESERVE), ("grid-route facilities at 50% cost", 1.0, 0.5, MAINT_RESERVE),
                             ("maintenance reserve 20%", 1.0, GRID_DISCOUNT, 0.20), ("no reserve", 1.0, GRID_DISCOUNT, 0.0)]:
    c = cost_vector(mult, gd)
    ch, sp = select("rank_final", True, c, BUDGET * (1 - res))
    vm, vsp = select("value_pop_per_usd", False, c, BUDGET * (1 - res))   # note: value order uses base cost column
    s = df.loc[ch]
    sens.append({"scenario": label, "facilities": len(ch), "people": int(s["pop"].sum()), "cost_per_person": round(sp / s["pop"].sum(), 2),
                 "overlap_with_base_plan": len(set(ch) & base_set), "solar_route": int((~s.is_grid).sum()),
                 "regions": {r: int((s.REGION == r).sum()) for r in sorted(df.REGION.unique())}})
sens = pd.DataFrame(sens)
sens.to_csv(os.path.join(HERE, "budget_sensitivity.csv"), index=False)

# need vs value for money: facilities in top-100 final rank that are expensive per person
top = df.nsmallest(100, "rank_final")
conflict = top.sort_values("value_pop_per_usd").head(10)[["rank_final", "FACILITY_N", "LEVEL", "DISTRICT", "pop", "est_cost", "value_pop_per_usd", "route"]]

rep = []
rep.append(f"BUDGET {BUDGET:,}; maintenance reserve {MAINT_RESERVE:.0%} = {BUDGET*MAINT_RESERVE:,.0f}; investable {usable:,.0f}")
rep.append(f"Base cost {BASE_COST:,}/facility scaled by (energy need / pool mean {df.kwh_d.mean():.1f} kWh/d)^{SCALE_EXP}; clip {SCALE_CLIP}")
rep.append(f"Mean est cost in pool: {df.est_cost.mean():,.0f}; min {df.est_cost.min():,.0f}; max {df.est_cost.max():,.0f}")
rep.append("Plans:\n" + summ.to_string(index=False))
rep.append("Facilities shared with the FINAL plan: " + str(overlap))
rep.append("Sensitivity:\n" + sens.to_string(index=False))
rep.append("Top-100-ranked facilities with the lowest people-per-USD (need vs value for money):\n" + conflict.round(2).to_string(index=False))
rep.append("Final plan by region:\n" + sel.groupby("REGION").agg(facilities=("FID", "count"), people=("pop", "sum"), cost=("est_cost", "sum")).round(0).to_string())
rep.append("Final plan by level:\n" + sel.groupby("LEVEL").agg(facilities=("FID", "count"), people=("pop", "sum"), cost=("est_cost", "sum")).round(0).to_string())
rep.append("Final plan top districts:\n" + dist.head(12).to_string(index=False))
open(os.path.join(HERE, "budget_report.txt"), "w", encoding="utf-8").write("\n\n".join(rep))
print("\n\n".join(rep))
