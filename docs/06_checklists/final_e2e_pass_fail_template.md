# Final E2E pass/fail template

| № | Scenario | Mode | Request file/query | Expected | Actual status | Artifact | Pass/Fail | Notes |
|---:|---|---|---|---|---|---|---|---|
| 1 | Time series | mock |  | line chart |  |  |  |  |
| 2 | Category comparison | mock |  | bar chart |  |  |  |  |
| 3 | Top-N | mock |  | table or bar |  |  |  |  |
| 4 | Empty result | mock |  | safe empty result |  |  |  |  |
| 5 | Time series | colab |  | line/table after real extraction |  |  |  |  |
| 6 | Category comparison | colab |  | bar/table after real extraction |  |  |  |  |
| 7 | Colab unavailable | colab/broken URL |  | safe error |  |  |  |  |
| 8 | Metadata incomplete | mock or colab |  | fallback + warning |  |  |  |  |
