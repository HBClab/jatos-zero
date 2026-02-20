# Main goal of this project
---
This repo contains a QA/QC pipeline that was built for a single study and is currently hard-coded. The main goal is to refactor the pipeline so it is configurable, while preserving existing behavior for the current study.

## Scope and intent
---
- Primary users include analysts, researchers, and data engineers.
- Some users want the `meta/` outputs, others only want saved/cleaned data; both must remain supported.
- The current pipeline is the baseline “full QC” behavior and should remain intact for the known tasks.

## Task definition (authoritative list)
---
A “task” is a JATOS task/task ID in `code/main_handler.py`. The authoritative list is:

```
self.IDs = {
    "AF": [945, 960, 990, 898, 919, 932],
    "ATS": [947, 961, 984, 918, 920, 933],
    "DSST": [949, 975, 986, 901, 959, 935],
    "DWL": [948, 974, 985, 900, 921, 934],
    "FN": [950, 964, 987, 902, 923, 936],
    "LC": [951, 976, 988, 903, 924, 937],
    "NF": [980, 981, 982, 978, 979, 977],
    "NNB": [946, 967, 989, 905, 929, 939],
    "NTS": [953, 968, 991, 906, 930, 940],
    "PC": [954, 969, 992, 912, 925, 941],
    "SM": [955, 970, 993, 916, 926, 996],
    "VNB": [957, 971, 994, 915, 928, 943],
    "WL": [958, 972, 995, 910, 927, 944]
}
```


## Domains
---
Current domains are CC, MEM, PS, and WL. If a task name does not exist in its domain, do not run full QC and do not expand the pipeline to support it (new tasks are a non-goal for now).

## Requirements
---
- Configurability is the main objective; the exact config surface (file type, schema, defaults) will be decided in a first feature.
- Full QC should run only for tasks in the authoritative list above.
- For now, ignore new/unknown tasks entirely (no QC, no plots, no meta, no saving).
- Meta outputs must continue to be produced in the same way for known tasks.
- `meta/` outputs are always generated, even if a user only cares about raw data.
- Plots are not in scope for this goal.

## User stories
---
**User Story 1**: I have just obtained tasks from JATOS and want the existing full QC pipeline to save and transform my data into usable outputs (including `meta/`).

**User Story 2**: I use this instead of downloading from JATOS directly. I may ignore `meta/`, but it still gets generated.
