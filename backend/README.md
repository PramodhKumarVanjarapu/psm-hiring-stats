# Hiring funnel API

See the README in the main folder for setup. This folder is the FastAPI backend.


## What it stores

| Collection | One document per | Notes |
|---|---|---|
| `jobs` | Job ID | `_id` is the job ID in capitals ("j-12 " and "J-12" are one job) |
| `job_stats` | Each saved run | `_id` is the run ID, so a run can never be saved twice. `is_latest` marks the newest run of each job |
| `students` | Real person | Unique mobile, emails and user IDs. Name, product, bucket and TR status from the newest run |
| `applications` | Student + job | `_id` is `JOBID:student_id`. Stage values: `"Applied"` (TA), `"P1"`, `"Select"`, ... or `null` |
| `identity_conflicts` | Clash | Two different mobiles sharing an email / user ID. Shown once, counted each time |
| `student_merges` | Merged-away student | Full copy of a student that was merged into another |
| `locks` | — | One save at a time |

## How duplicates are handled

- **Same person, many rows in one sheet:** combined into one person; the best label per stage wins (P1 > P2 > P3, Select > Hold > Reject > NA).
- **Same person in many jobs:** one `students` document and one small `applications` document per job.
- **Student saved with only an email, later seen with a mobile:** the two students are merged into the older one; their applications move with them.
- **Two different mobiles with the same email or user ID:** never merged. The email / user ID stays with the first owner and the clash goes to `identity_conflicts`.
- **Same run sent twice** (double click, network retry): the second one is ignored.
- **Same job saved again:** a new stats snapshot is added to the history and the job's student list is replaced with the new one.
- **An older run saved after a newer one:** kept in the history only.
- **Two saves at the same moment:** the second waits and gets a "try again" answer (the Streamlit app retries by itself).

