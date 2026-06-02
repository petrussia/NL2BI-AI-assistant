"""Expanded crash-test 5 sources × 10 query types via direct /extract.

Categories:
  L1 simple    : count, top-n, group-by, filter
  L2 medium    : 2-table join, time series, having
  L3 hard      : multi-hop join, subquery/CTE, multi-aggregate

Goal: stress test SQL quality across realistic difficulty.
"""
import json, urllib.request, urllib.error, time, sys

URL = sys.argv[1] if len(sys.argv) > 1 else "https://8e4d-34-12-16-70.ngrok-free.app"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else ""

TESTS = [
    ("demo_concert_singer", [
        ("L1 count",      "Сколько всего певцов в базе"),
        ("L1 top-n",      "Топ-5 стадионов по вместимости"),
        ("L1 filter",     "Сколько певцов из Франции"),
        ("L1 group-by",   "Сравни количество певцов по странам"),
        ("L2 ts",         "Количество концертов по годам"),
        ("L2 join",       "Какие певцы участвовали в концерте Auditions"),
        ("L2 having",     "Страны где больше 1 певца"),
        ("L3 mhop join",  "Топ-3 стадиона по количеству концертов"),
        ("L3 subquery",   "Певцы старше среднего возраста"),
        ("L3 mulagg",     "Среднее, минимум и максимум возраста певцов по странам"),
    ]),
    ("bird_student_club", [
        ("L1 count",      "How many members are in the club"),
        ("L1 top-n",      "Top 5 members by attendance count"),
        ("L1 filter",     "How many events are completed"),
        ("L1 group-by",   "Count of members per major"),
        ("L2 ts",         "Number of events per month"),
        ("L2 join",       "List members who attended Yearly Kickoff event"),
        ("L2 having",     "Majors with at least 2 members"),
        ("L3 mhop join",  "Total expense amount per event"),
        ("L3 subquery",   "Members who attended more than average events"),
        ("L3 mulagg",     "Average expense per category with min and max"),
    ]),
    ("spider2_retail_dbt", [
        ("L1 count",      "How many completed orders are in the retail dataset"),
        ("L1 top-n",      "Top 5 product categories by revenue"),
        ("L1 filter",     "How many online orders were completed"),
        ("L1 group-by",   "Revenue by sales channel"),
        ("L2 ts",         "Monthly revenue trend in 2024"),
        ("L2 join",       "List top products with their category and total revenue"),
        ("L2 having",     "Stores with revenue above 100000"),
        ("L3 mhop join",  "Revenue by customer segment and region"),
        ("L3 subquery",   "Product categories with revenue above the average category revenue"),
        ("L3 mulagg",     "Min, avg, max order revenue by customer segment"),
    ]),
    ("moscow_open", [
        ("L1 count",      "Сколько всего станций метро"),
        ("L1 top-n",      "Топ-5 районов по населению"),
        ("L1 filter",     "Сколько станций открыто после 2010 года"),
        ("L1 group-by",   "Сколько станций на каждой линии"),
        ("L2 ts",         "Сколько станций открыто по десятилетиям"),
        ("L2 join",       "Сколько станций в каждом округе"),
        ("L2 having",     "Линии с более чем 15 станциями"),
        ("L3 mhop join",  "Самые загруженные станции в Центральном округе"),
        ("L3 subquery",   "Округа с населением выше среднего"),
        ("L3 mulagg",     "Минимум, среднее и максимум населения районов по округам"),
    ]),
    ("northwind_ru", [
        ("L1 count",      "Сколько всего заказов"),
        ("L1 top-n",      "Топ-5 товаров по выручке"),
        ("L1 filter",     "Сколько клиентов из сегмента HoReCa"),
        ("L1 group-by",   "Сколько продано в каждой категории"),
        ("L2 ts",         "Динамика заказов по месяцам 2024"),
        ("L2 join",       "Топ-5 клиентов по сумме заказов"),
        ("L2 having",     "Категории с выручкой больше миллиона"),
        ("L3 mhop join",  "Выручка по федеральным округам России"),
        ("L3 subquery",   "Клиенты с заказами выше среднего чека"),
        ("L3 mulagg",     "Минимум, среднее и максимум стоимости заказа по сегментам"),
    ]),
]

def ask(ds_id, query):
    body = json.dumps({
        "request_id": f"x-{ds_id}-{int(time.time()*1000)}",
        "user_query": query,
        "data_source": {"id": ds_id},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{URL}/extract", data=body, method="POST",
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8")), time.time()-t0
    except urllib.error.HTTPError as e:
        return {"status": "http_error", "code": e.code, "body": e.read().decode("utf-8")[:200]}, time.time()-t0
    except Exception as e:
        return {"status": "exception", "error": str(e)}, time.time()-t0

print(f"{'source':<24} {'lvl':<14} {'status':<14} {'rows':>5}  {'sec':>5}  err")
print("-" * 110)
hard_fails = 0
partial = 0
success = 0
total = 0
by_source = {}

for ds_id, queries in TESTS:
    by_source.setdefault(ds_id, [0,0,0,0])  # success, partial, fail, count
    for qtype, q in queries:
        d, dt = ask(ds_id, q)
        status = d.get("status","?")
        rt = d.get("result_table",{}) or {}
        rows = rt.get("row_count", 0)
        errs = [e.get("code") for e in (d.get("errors") or [])]
        total += 1
        by_source[ds_id][3] += 1
        if status == "success":
            success += 1; by_source[ds_id][0] += 1
        elif status == "partial_success":
            partial += 1; by_source[ds_id][1] += 1
        else:
            hard_fails += 1; by_source[ds_id][2] += 1
        print(f"{ds_id:<24} {qtype:<14} {status:<14} {rows:>5}  {dt:5.1f}  {','.join(errs) if errs else ''}")

print()
print(f"=== summary ===")
print(f"Hard fails    : {hard_fails}/{total}")
print(f"Partial (0-rows): {partial}/{total}")
print(f"Full success   : {success}/{total}")
print(f"Valid SQL ratio: {(success+partial)/total*100:.0f}%")
print()
for src, (s,p,f,t) in by_source.items():
    print(f"  {src:<24}  success {s} | partial {p} | fail {f} | total {t}")
