import json
import sys

nb_path = r"D:\HSE\Диплом\NL2BI-AI-assistant\notebooks\example.ipynb"
nb = json.load(open(nb_path, encoding="utf-8"))
print(f"Total cells: {len(nb['cells'])}")
for i, c in enumerate(nb["cells"]):
    src = "".join(c["source"])[:90].replace("\n", " ")
    cid = c.get("id", "?")
    ec = c.get("execution_count")
    outs = len(c.get("outputs", []))
    print(f"{i:>2} | {cid:>10} | {c['cell_type']:>8} | exec={ec} | outs={outs} | {src}")
