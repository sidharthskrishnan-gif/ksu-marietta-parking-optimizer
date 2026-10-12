"""KSU Marietta Parking Optimizer V2 — final calibrated MVP.

Core schedule input: day, building, start_time, end_time.
The permit ranking is deterministic. Confidence is evaluated separately by
sensitivity analysis.
"""
from pathlib import Path
import csv, random
from collections import defaultdict, Counter

ROOT=Path(__file__).resolve().parent
DATA_DIR=ROOT/"data"
def rows(name):
    with open(DATA_DIR/name,newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))

WR=rows("walking_distances.csv")
AR=rows("parking_areas.csv")
PR=rows("permits.csv")
RR=rows("search_risk_modifiers.csv")
walking={(r["Parking Lot"],r["Building"]):int(float(r["Duration (Seconds)"])) for r in WR}
areas={r["display_name"]:r for r in AR}; permits={r["permit_id"]:r for r in PR}
rules={r["rule_id"]:float(r["value"]) for r in RR}
occ={r["condition"].split("==",1)[1].strip():float(r["value"]) for r in RR if r["rule_type"]=="occupancy_base"}
P2L={"central_area":["Central Lot 1","Central Lot 2"],"east_area":["East Lot 1","East Lot 2"],
     "marietta_west":["West Deck"],"south_lot":["West Lot"],
     "east_economy":["East Economy Lot","East Economy Central","East Economy Southeast"],"shuttle_lot":["Shuttle Lot"]}
prices={pid:float(p["fall_2026_rate_usd"]) for pid,p in permits.items()}
lo,hi=min(prices.values()),max(prices.values())
pricecost={pid:0 if hi==lo else (v-lo)/(hi-lo)*50 for pid,v in prices.items()}

DEFAULT_PREFERENCES={"walking":50,"reliability":35,"shade":10,"price":5}

def list_buildings(data_dir=None):
    return sorted({r["Building"] for r in WR})

def validate_schedule(schedule,data_dir=None):
    valid_days=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    day_order={d:i for i,d in enumerate(valid_days)}
    buildings=set(list_buildings())
    clean=[]
    for i,row in enumerate(schedule,1):
        if not row:continue
        r={
            "day":str(row.get("day","")).strip(),
            "building":str(row.get("building","")).strip(),
            "start_time":str(row.get("start_time","")).strip(),
            "end_time":str(row.get("end_time","")).strip(),
        }
        if not all(r.values()):raise ValueError(f"Schedule row {i} is incomplete.")
        if r["day"] not in day_order:raise ValueError(f"Unknown day: {r['day']}")
        if r["building"] not in buildings:raise ValueError(f"Unknown building: {r['building']}")
        try:
            start=clock(r["start_time"]);end=clock(r["end_time"])
        except Exception:
            raise ValueError(f"Invalid time on row {i}.")
        if end<=start:raise ValueError(f"End time must be after start time on row {i}.")
        clean.append(r)
    if not clean:raise ValueError("Enter at least one class.")
    clean.sort(key=lambda r:(day_order[r["day"]],clock(r["start_time"])))
    grouped=defaultdict(list)
    for r in clean:grouped[r["day"]].append(r)
    for day,rs in grouped.items():
        for a,b in zip(rs,rs[1:]):
            if clock(b["start_time"])<clock(a["end_time"]):
                raise ValueError(f"{day} contains overlapping classes.")
    return clean

def detect_long_gaps(schedule,minimum_gap_minutes=120,data_dir=None):
    rows_=validate_schedule(schedule)
    grouped=defaultdict(list)
    for r in rows_:grouped[r["day"]].append(r)
    out=[]
    for day,rs in grouped.items():
        for a,b in zip(rs,rs[1:]):
            gap=clock(b["start_time"])-clock(a["end_time"])
            if gap>=minimum_gap_minutes:
                out.append({
                    "day":day,
                    "after_end_time":a["end_time"],
                    "before_start_time":b["start_time"],
                    "minutes":gap,
                    "hours":gap/60,
                    "before_building":a["building"],
                    "after_building":b["building"],
                })
    return out

def clamp(x):return max(0,min(100,x))
def clock(s):h,m=map(int,s.split(":"));return h*60+m
def tmod(t):
    if t<510:return rules["TIME_BEFORE_0830"]
    if t<570:return rules["TIME_0830_0929"]
    if t<630:return rules["TIME_0930_1029"]
    if t<840:return rules["TIME_1030_1359"]
    if t<900:return rules["TIME_1400_1459"]
    if t<1020:return rules["TIME_1500_1659"]
    return rules["TIME_AFTER_1700"]
def smod(w):
    if w<=2:return rules["SEM_WEEKS_1_2"]
    if w<=4:return rules["SEM_WEEKS_3_4"]
    if w<=12:return rules["SEM_WEEKS_5_12"]
    if w<=15:return rules["SEM_WEEKS_13_15"]
    return rules["SEM_FINALS"]
def reserve(r):
    if r<=29:return 3
    if r<=39:return 5
    if r<=49:return 7
    if r<=59:return 10
    if r<=69:return 14
    return 18
def search_risk(lot,t,week,perturb=0):
    a=areas[lot]
    pre=occ[a["occupancy_pressure"]]+tmod(t)+smod(week)+perturb
    x=pre
    if lot=="Central Lot 1":
        if pre<40:x+=rules["CENTRAL1_SEARCHABILITY_QUIET"]
        elif pre<50:x+=rules["CENTRAL1_SEARCHABILITY_MODERATE"]
        elif pre<60:x+=rules["CENTRAL1_SEARCHABILITY_BUSY"]
        else:x+=rules["CENTRAL1_SEARCHABILITY_PEAK"]
    elif lot=="West Deck" and pre>=50:
        x+=rules["WEST_DECK_CIRCULATION"]
    else:
        x+=float(a["searchability_penalty_points"])
    return clamp(x)
def walk_cost(sec):return min(sec/900,1)*100
def raw_shade_penalty(lot,perturb=0):
    a=areas[lot]
    if not a["shade_potential_0_5"] or not a["shade_reliability_0_5"]:return clamp(50+perturb)
    return clamp(100-100*(float(a["shade_potential_0_5"])/5)*(float(a["shade_reliability_0_5"])/5)+perturb)
def shade_exposure(session):
    return max(.20,min((session["last_end"]-session["first_start"])/360,1.0))
def arrival(lot,b,start,week,perturb=0):
    wm=walking[(lot,b)]/60;a=start-wm-5
    for _ in range(4):
        r=search_risk(lot,a,week,perturb);a=start-wm-5-reserve(r)
    r=search_risk(lot,a,week,perturb)
    return a,r,reserve(r)

def make_sessions(schedule,leave_after=None):
    leave_after=leave_after or set();d=defaultdict(list)
    for x in schedule:d[x["day"]].append(x)
    out=[]
    for day in ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]:
        arr=sorted(d.get(day,[]),key=lambda x:clock(x["start_time"]));cur=[];idx=1
        for x in arr:
            cur.append(x)
            if (day,x["end_time"]) in leave_after:
                out.append({"day":day,"session_index":idx,"first_building":cur[0]["building"],
                            "first_start":clock(cur[0]["start_time"]),"last_building":cur[-1]["building"],
                            "last_end":clock(cur[-1]["end_time"])})
                cur=[];idx+=1
        if cur:
            out.append({"day":day,"session_index":idx,"first_building":cur[0]["building"],
                        "first_start":clock(cur[0]["start_time"]),"last_building":cur[-1]["building"],
                        "last_end":clock(cur[-1]["end_time"])})
    return out

def optimize(schedule,semester_week=5,preferences=None,leave_after=None,perturbations=None):
    preferences=preferences or {"walking":50,"reliability":35,"shade":10,"price":5}
    total=sum(preferences.values());w={k:v/total for k,v in preferences.items()}
    ss=make_sessions(schedule,leave_after);perturbations=perturbations or {};ranked=[]
    for pid in permits:
        best=[]
        for s in ss:
            lots=list(areas) if s["first_start"]>=1020 else P2L[pid];opts=[]
            for lot in lots:
                sp,hp=perturbations.get(lot,(0,0))
                aw=walking[(lot,s["first_building"])];fw=walking[(lot,s["last_building"])]
                wc=.55*walk_cost(aw)+.45*walk_cost(fw)
                ar,sr,res=arrival(lot,s["first_building"],s["first_start"],semester_week,sp)
                shade=raw_shade_penalty(lot,hp)*shade_exposure(s)
                score=w["walking"]*wc+w["reliability"]*sr+w["shade"]*shade
                opts.append({**s,"lot":lot,"session_score":score,"search_risk":sr,"arrival_by":ar,"reserve":res})
            best.append(min(opts,key=lambda x:x["session_score"]))
        vals=[x["session_score"] for x in best]
        func=.8*sum(vals)/len(vals)+.2*max(vals)
        ranked.append({"permit_id":pid,"permit_name":permits[pid]["permit_name"],"color":permits[pid]["permit_color"],
                       "score":func+w["price"]*pricecost[pid],"sessions":best})
    return sorted(ranked,key=lambda x:x["score"])

def confidence(schedule,semester_week=5,preferences=None,leave_after=None,simulations=400,seed=1234):
    nominal=optimize(schedule,semester_week,preferences,leave_after);winner=nominal[0]["permit_id"]
    rng=random.Random(seed);counts=Counter()
    for _ in range(simulations):
        p={}
        for lot,a in areas.items():
            c=a["confidence"].lower();ssd=4 if c=="moderate" else 7 if c=="low" else 2.5
            hsd=5 if c=="moderate" else 9 if c=="low" else 3
            p[lot]=(rng.gauss(0,ssd),rng.gauss(0,hsd))
        counts[optimize(schedule,semester_week,preferences,leave_after,p)[0]["permit_id"]]+=1
    return 100*counts[winner]/simulations,counts


def _fmt_clock(minutes):
    minutes=int(round(minutes))%1440
    h,m=divmod(minutes,60)
    return f"{h:02d}:{m:02d}"

def _permit_metrics(p):
    ss=p["sessions"]
    total_walk=0
    total_risk=0
    total_shade=0
    for s in ss:
        aw=walking[(s["lot"],s["first_building"])]
        fw=walking[(s["lot"],s["last_building"])]
        total_walk+=(aw+fw)/60
        total_risk+=s["search_risk"]
        total_shade+=raw_shade_penalty(s["lot"])*shade_exposure(s)
    n=max(1,len(ss))
    return {
        "weekly_walk_minutes":total_walk,
        "average_search_risk":total_risk/n,
        "average_effective_shade_penalty":total_shade/n,
        "price":prices[p["permit_id"]],
    }

def _normalize_ranked(ranked):
    out=[]
    for p in ranked:
        sessions=[]
        for s in p["sessions"]:
            x=dict(s)
            x["arrival_walk_seconds"]=walking[(s["lot"],s["first_building"])]
            x["final_walk_seconds"]=walking[(s["lot"],s["last_building"])]
            x["arrival_by_text"]=_fmt_clock(s["arrival_by"])
            sessions.append(x)
        q={
            "permit_id":p["permit_id"],
            "permit_name":p["permit_name"],
            "permit_color":permits[p["permit_id"]]["permit_color"],
            "price":prices[p["permit_id"]],
            "score":p["score"],
            "sessions":sessions,
        }
        q["weekly_metrics"]=_permit_metrics(q)
        out.append(q)
    return out

def tilt_preferences(preferences,focus,target_weight=60):
    p={k:float(preferences[k]) for k in DEFAULT_PREFERENCES}
    total=sum(p.values())
    if total<=0:raise ValueError("At least one preference must be positive.")
    p={k:100*v/total for k,v in p.items()}
    target=min(75,max(float(target_weight),p[focus]+20))
    others=[k for k in p if k!=focus]
    other_total=sum(p[k] for k in others)
    result={focus:target}
    for k in others:
        result[k]=(100-target)*(p[k]/other_total if other_total else 1/len(others))
    return result

def analyze_priority_tradeoffs(schedule,preferences,semester_week=5,leave_after=None,data_dir=None):
    schedule=validate_schedule(schedule)
    out=[]
    for focus in DEFAULT_PREFERENCES:
        tilted=tilt_preferences(preferences,focus)
        ranked=_normalize_ranked(optimize(schedule,semester_week,tilted,leave_after))
        win=ranked[0]
        out.append({
            "focus":focus,
            "label":f"Prioritize {focus} more",
            "preferences":tilted,
            "winner":win["permit_name"],
            "permit_color":win["permit_color"],
            "score":win["score"],
            "weekly_metrics":win["weekly_metrics"],
        })
    return out

def recommend_permit(schedule,preferences=None,semester_week=5,leave_after=None,
                     data_dir=None,confidence_simulations=300,include_tradeoffs=True):
    schedule=validate_schedule(schedule)
    preferences=preferences or dict(DEFAULT_PREFERENCES)
    ranked=_normalize_ranked(optimize(schedule,semester_week,preferences,leave_after))
    stability,_=confidence(schedule,semester_week,preferences,leave_after,
                           simulations=max(1,int(confidence_simulations)))
    gap=ranked[1]["score"]-ranked[0]["score"]
    confidence_score=max(0,min(100,0.75*stability+0.25*min(100,gap*12)-(5 if semester_week<=2 else 0)))
    confidence_label="High" if confidence_score>=75 else "Moderate" if confidence_score>=50 else "Low"

    win,runner=ranked[0],ranked[1]
    wm,rm=win["weekly_metrics"],runner["weekly_metrics"]
    advantages={
        "shorter weekly walking":rm["weekly_walk_minutes"]-wm["weekly_walk_minutes"],
        "lower expected search difficulty":(rm["average_search_risk"]-wm["average_search_risk"])/2,
        "better shade":(rm["average_effective_shade_penalty"]-wm["average_effective_shade_penalty"])/4,
        "lower permit cost":(rm["price"]-wm["price"])/5,
    }
    main=max(advantages,key=advantages.get)
    explanation=(
        f"{win['permit_name']} ranks first mainly because it provides {main} "
        f"for this schedule under your current priorities. "
        f"{runner['permit_name']} is the closest alternative."
    )

    days=len({r["day"] for r in schedule})
    lowfreq=None
    if days<=2:
        cheaper=[p for p in ranked[1:] if p["price"]<win["price"]]
        if cheaper:
            c=min(cheaper,key=lambda p:p["score"])
            lowfreq=(
                f"You only commute {days} day{'s' if days!=1 else ''} per week. "
                f"{c['permit_name']} costs ${win['price']-c['price']:.0f} less, "
                "so it may be worth comparing if you are willing to trade convenience for lower cost."
            )

    result={
        "recommended_permit":win["permit_name"],
        "permit_id":win["permit_id"],
        "permit_color":win["permit_color"],
        "price":win["price"],
        "score":win["score"],
        "confidence":{
            "label":confidence_label,
            "score":confidence_score,
            "winner_stability_percent":stability,
            "runner_up_gap":gap,
        },
        "sessions":win["sessions"],
        "weekly_metrics":win["weekly_metrics"],
        "runner_up":runner,
        "ranked_permits":[
            {
                "rank":i,
                "permit_id":p["permit_id"],
                "permit_name":p["permit_name"],
                "permit_color":p["permit_color"],
                "price":p["price"],
                "score":p["score"],
                "weekly_metrics":p["weekly_metrics"],
            }
            for i,p in enumerate(ranked,1)
        ],
        "explanation":explanation,
        "low_frequency_guidance":lowfreq,
    }
    if include_tradeoffs:
        result["priority_tradeoffs"]=analyze_priority_tradeoffs(
            schedule,preferences,semester_week,leave_after
        )
    return result
