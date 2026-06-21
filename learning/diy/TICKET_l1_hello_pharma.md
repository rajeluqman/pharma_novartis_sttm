# TICKET — L1: `hello_pharma` (DIY Build Mode)

> @cikgu writes the WHAT, not the HOW. You build `learning/diy/hello_pharma_diy.py` yourself,
> cheatsheet at your elbow. When you say "done", we diff vs the answer key and quiz WHY on every
> difference. No peeking at `airflow/dags/gym_*` — those are later levels.

## Goal
A single-task Airflow DAG that prints the row count of one landed raw file. This is the "hello world"
of the gym — you're proving you can define a DAG, a task, and a schedule, and run it once.

## Inputs
- One landed CSV (e.g. the alpha sales file under `data/landing/alpha/<date>/`), OR — if you want to
  practice the S3-canonical reality — read it from `s3://novartis-pharma-sttm-lake/landing/alpha/<date>/`.
- Local Airflow is in `.venv` (3.x). The real pipeline is `airflow/dags/pharma_sttm_pipeline.py` — read
  it for *style* reference only; do NOT copy it.

## Acceptance criteria (Definition of Done)
1. File `learning/diy/hello_pharma_diy.py` defines exactly **one** DAG with **one** task.
2. The task reads the raw file and prints its row count to the task log.
3. DAG attributes set deliberately: `dag_id`, `schedule` (pick one and be ready to justify it),
   `start_date`, `catchup=False` — and you can explain *why* each, especially `catchup`.
4. It **parses clean**: `DagBag` import with zero import errors (you can reuse the check pattern from
   `scripts/parse_test_mwaa.sh` or a one-line `DagBag(...)` import).
5. You can draw/say its "critical path" (trivial here — one task — but say why).

## Out of scope (do NOT do yet)
- No Bronze write, no dbt, no S3 write-back, no parallelism, no sensors. Those are L2+.
- No sabotage yet — L1 is the free level to learn the basics.

## Concepts @cikgu will quiz you on (WHY before HOW)
- Why does `catchup=False` matter for a daily pipeline you just turned on in June?
- What's the difference between `start_date` and the first actual run?
- DAG = graph; task = node — what makes two tasks "dependent"?

## When you're stuck
Don't ask for code. Ask: "where's the official doc for X?" Cikgu's first answer is always a doc
pointer (`site:airflow.apache.org dag schedule`), not a snippet. Each hint = −5 score.
