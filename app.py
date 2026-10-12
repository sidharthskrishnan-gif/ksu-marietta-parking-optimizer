
from pathlib import Path
import pandas as pd
import streamlit as st

from ksu_parking_optimizer import (
    DEFAULT_PREFERENCES,
    detect_long_gaps,
    list_buildings,
    recommend_permit,
    validate_schedule,
)

st.set_page_config(
    page_title="KSU Marietta Parking Permit Optimizer",
    page_icon="🅿️",
    layout="wide",
)

DATA_DIR = Path(__file__).resolve().parent / "data"
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MINUTES = [0, 15, 30, 45]

st.title("KSU Marietta Parking Permit Optimizer")
st.caption(
    "Build your weekly schedule, set your priorities, and compare the permit "
    "that best fits your actual routine."
)

buildings = list_buildings(DATA_DIR)

if "classes" not in st.session_state:
    st.session_state.classes = []
if "result" not in st.session_state:
    st.session_state.result = None

def ui_time_to_24(hour_12, minute, am_pm):
    h = int(hour_12)
    m = int(minute)
    if am_pm == "AM":
        h24 = 0 if h == 12 else h
    else:
        h24 = 12 if h == 12 else h + 12
    return f"{h24:02d}:{m:02d}"

def time24_to_display(value):
    h, m = map(int, value.split(":"))
    ampm = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"

def minutes(value):
    h, m = map(int, value.split(":"))
    return h * 60 + m

def sorted_classes(rows):
    order = {d: i for i, d in enumerate(DAYS)}
    return sorted(rows, key=lambda r: (order[r["day"]], minutes(r["start_time"])))

def display_schedule(rows):
    return pd.DataFrame([
        {
            "Day": r["day"],
            "Building": r["building"],
            "Start": time24_to_display(r["start_time"]),
            "End": time24_to_display(r["end_time"]),
        }
        for r in sorted_classes(rows)
    ])

with st.expander("How this works"):
    st.write(
        "The ranking is deterministic. It uses mapped walking times, parking "
        "search difficulty, semester/time effects, shade, and permit price."
    )

st.header("1. Build your weekly schedule")
st.write(
    "Add one class at a time. You only need the day, building, start time, and end time."
)

with st.form("add_class_form"):
    c1, c2 = st.columns([1, 2])
    with c1:
        day = st.selectbox("Day", DAYS)
    with c2:
        building = st.selectbox("Building", buildings)

    st.markdown("**Start time**")
    s1, s2, s3, gap, e1, e2, e3 = st.columns([1,1,1,.3,1,1,1])

    with s1:
        start_hour = st.selectbox("Hour", list(range(1, 13)), index=8, key="sh")
    with s2:
        start_minute = st.selectbox(
            "Minute", MINUTES, index=0, key="sm",
            format_func=lambda x: f"{x:02d}"
        )
    with s3:
        start_ampm = st.selectbox("AM / PM", ["AM", "PM"], key="sap")

    with e1:
        st.markdown("**End time**")
        end_hour = st.selectbox("Hour ", list(range(1, 13)), index=9, key="eh")
    with e2:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        end_minute = st.selectbox(
            "Minute ", MINUTES, index=1, key="em",
            format_func=lambda x: f"{x:02d}"
        )
    with e3:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        end_ampm = st.selectbox("AM / PM ", ["AM", "PM"], key="eap")

    submitted = st.form_submit_button("Add class", type="primary")

if submitted:
    row = {
        "day": day,
        "building": building,
        "start_time": ui_time_to_24(start_hour, start_minute, start_ampm),
        "end_time": ui_time_to_24(end_hour, end_minute, end_ampm),
    }
    try:
        candidate = list(st.session_state.classes) + [row]
        st.session_state.classes = validate_schedule(candidate, DATA_DIR)
        st.session_state.result = None
        st.rerun()
    except Exception as exc:
        st.error(str(exc))

if st.session_state.classes:
    st.subheader("Current schedule")
    preview = display_schedule(st.session_state.classes)
    st.dataframe(preview, hide_index=True, width="stretch")
    st.caption(f"{len(st.session_state.classes)} classes entered.")

    ordered = sorted_classes(st.session_state.classes)
    labels = [
        f"{r['day']} — {r['building']} — "
        f"{time24_to_display(r['start_time'])}–{time24_to_display(r['end_time'])}"
        for r in ordered
    ]

    r1, r2, r3 = st.columns([4, 1, 1])
    with r1:
        choice = st.selectbox(
            "Remove a class",
            ["Select a class…"] + labels
        )
    with r2:
        st.write("")
        st.write("")
        if st.button("Remove"):
            if choice != "Select a class…":
                target = ordered[labels.index(choice)]
                st.session_state.classes.remove(target)
                st.session_state.result = None
                st.rerun()
    with r3:
        st.write("")
        st.write("")
        if st.button("Clear all"):
            st.session_state.classes = []
            st.session_state.result = None
            st.rerun()

    with st.expander("Show exactly what the optimizer parsed"):
        st.dataframe(preview, hide_index=True, width="stretch")
else:
    st.info("Add your first class above.")

leave_after = set()

if st.session_state.classes:
    st.header("2. Long gaps")

    try:
        gaps = detect_long_gaps(
            st.session_state.classes,
            minimum_gap_minutes=120,
            data_dir=DATA_DIR,
        )
    except Exception as exc:
        gaps = []
        st.error(str(exc))

    if not gaps:
        st.success("No same-day gaps of 2 hours or longer were detected.")
    else:
        st.write(
            f"Detected **{len(gaps)} long gap"
            f"{'s' if len(gaps) != 1 else ''}**."
        )
        st.caption(
            "Answering Yes splits that day into two parking sessions."
        )

        for i, g in enumerate(gaps):
            st.markdown(
                f"**{g['day']} — "
                f"{time24_to_display(g['after_end_time'])} to "
                f"{time24_to_display(g['before_start_time'])} "
                f"({g['hours']:.1f} hours)**"
            )
            answer = st.radio(
                "Do you normally leave campus during this gap?",
                ["No", "Yes"],
                horizontal=True,
                key=f"gap_{g['day']}_{g['after_end_time']}_{g['before_start_time']}",
            )
            if answer == "Yes":
                leave_after.add((g["day"], g["after_end_time"]))

    st.header("3. Set your priorities")
    st.write("The values do not need to add up to 100.")

    p1, p2, p3, p4 = st.columns(4)
    with p1:
        walking = st.slider("Walking", 0, 100, DEFAULT_PREFERENCES["walking"])
    with p2:
        reliability = st.slider("Reliability", 0, 100, DEFAULT_PREFERENCES["reliability"])
    with p3:
        shade = st.slider("Shade", 0, 100, DEFAULT_PREFERENCES["shade"])
    with p4:
        price = st.slider("Price", 0, 100, DEFAULT_PREFERENCES["price"])

    preferences = {
        "walking": walking,
        "reliability": reliability,
        "shade": shade,
        "price": price,
    }

    semester_week = st.slider("Semester week", 1, 16, 5)

    st.header("4. Get your recommendation")
    if st.button("Recommend my permit", type="primary"):
        try:
            st.session_state.result = recommend_permit(
                st.session_state.classes,
                preferences=preferences,
                semester_week=semester_week,
                leave_after=leave_after,
                data_dir=DATA_DIR,
                confidence_simulations=300,
                include_tradeoffs=True,
            )
        except Exception as exc:
            st.error(str(exc))

result = st.session_state.result

if result:
    st.divider()
    confidence = result["confidence"]

    a, b, c = st.columns([2, 1, 1])
    with a:
        st.subheader("Recommended permit")
        st.markdown(f"## {result['permit_color']} — {result['recommended_permit']}")
        st.write(result["explanation"])
    with b:
        st.metric("Semester price", f"${result['price']:.0f}")
        st.metric("Model score", f"{result['score']:.1f}")
    with c:
        st.metric("Confidence", confidence["label"])
        st.caption(
            f"{confidence['winner_stability_percent']:.1f}% winner stability"
        )

    if result.get("low_frequency_guidance"):
        st.info(result["low_frequency_guidance"])

    st.subheader("Your weekly parking plan")
    plan = []
    for s in result["sessions"]:
        plan.append({
            "Day": s["day"],
            "Session": s["session_index"],
            "Preferred lot": s["lot"],
            "Arrive at lot by": time24_to_display(s["arrival_by_text"]),
            "First building": s["first_building"],
            "Walk to first class": f"{s['arrival_walk_seconds']/60:.1f} min",
            "Final building": s["last_building"],
            "Walk back to car": f"{s['final_walk_seconds']/60:.1f} min",
            "Search risk": f"{s['search_risk']:.0f}/100",
        })
    st.dataframe(pd.DataFrame(plan), hide_index=True, width="stretch")

    m = result["weekly_metrics"]
    x, y, z = st.columns(3)
    with x:
        st.metric("Weekly first/final walking", f"{m['weekly_walk_minutes']:.1f} min")
    with y:
        st.metric("Average search risk", f"{m['average_search_risk']:.0f}/100")
    with z:
        st.metric("Runner-up gap", f"{confidence['runner_up_gap']:.2f} pts")

    st.subheader("Permit comparison")
    comparison = []
    for p in result["ranked_permits"]:
        comparison.append({
            "Rank": p["rank"],
            "Permit": p["permit_name"],
            "Color": p["permit_color"],
            "Price": f"${p['price']:.0f}",
            "Score": round(p["score"], 2),
            "Weekly first/final walking":
                f"{p['weekly_metrics']['weekly_walk_minutes']:.1f} min",
            "Avg. search risk":
                round(p["weekly_metrics"]["average_search_risk"], 1),
        })
    st.dataframe(pd.DataFrame(comparison), hide_index=True, width="stretch")

    st.subheader("How changing your priorities affects the recommendation")
    st.write(
        "These are schedule-conditioned comparisons, not 100/0 extremes. "
        "Each one emphasizes a single preference while keeping the others relevant."
    )

    trade = [{
        "Scenario": "Your priorities",
        "Weights": f"{walking} W / {reliability} R / {shade} S / {price} P",
        "Recommendation": result["recommended_permit"],
    }]

    for t in result["priority_tradeoffs"]:
        p = t["preferences"]
        trade.append({
            "Scenario": t["label"],
            "Weights": (
                f"{p['walking']:.0f} W / "
                f"{p['reliability']:.0f} R / "
                f"{p['shade']:.0f} S / "
                f"{p['price']:.0f} P"
            ),
            "Recommendation": t["winner"],
        })

    st.dataframe(pd.DataFrame(trade), hide_index=True, width="stretch")

    changed = [
        t for t in result["priority_tradeoffs"]
        if t["winner"] != result["recommended_permit"]
    ]

    if changed:
        for t in changed:
            original = result["weekly_metrics"]
            alt = t["weekly_metrics"]

            walk_delta = alt["weekly_walk_minutes"] - original["weekly_walk_minutes"]
            risk_delta = alt["average_search_risk"] - original["average_search_risk"]
            price_delta = alt["price"] - original["price"]

            details = []
            if abs(walk_delta) >= 0.5:
                details.append(
                    f"{abs(walk_delta):.1f} min "
                    f"{'more' if walk_delta > 0 else 'less'} weekly walking"
                )
            if abs(risk_delta) >= 1:
                details.append(
                    f"{abs(risk_delta):.0f} points "
                    f"{'higher' if risk_delta > 0 else 'lower'} search risk"
                )
            if abs(price_delta) >= 1:
                details.append(
                    f"${abs(price_delta):.0f} "
                    f"{'more' if price_delta > 0 else 'less'}"
                )

            st.write(
                f"**If you prioritized {t['focus']} more:** "
                f"{t['winner']} would become the recommendation"
                + (f", with {'; '.join(details)}." if details else ".")
            )
    else:
        st.success(
            "The same permit stays first even after substantially emphasizing "
            "each individual priority."
        )

    with st.expander("Model limitations"):
        st.write(
            "- Search-risk values are relative heuristics, not probabilities.\n"
            "- Historical community reports are context, not live occupancy data.\n"
            "- Fall 2025 crisis conditions are not treated as the normal baseline.\n"
            "- Real-time closures, events, construction, and weather are not yet ingested."
        )
