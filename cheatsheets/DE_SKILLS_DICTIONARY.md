# DE Skills Dictionary — SQL + Python + Stack → STTM (Practical + Plain English)

> Format setiap item: **WHAT → CODE → PLAIN ENGLISH → ANALOGY → WHEN USE**.
> Bukan teori. Ni "coding dictionary" — baca, faham, terus guna interview/kerja.
> Work distribution sebenar JD: **70% SQL+Python · 20% modeling · 10% tools.**

---

## 🔗 1. INNER JOIN
**WHAT** — Ambil data yang match sahaja antara 2 table.
```sql
SELECT *
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id;
```
**PLAIN ENGLISH** — "Ambil order yang ada customer valid sahaja."
**ANALOGY** — invois hanya kalau IC customer wujud.
**WHEN** — nak dataset bersih, tak nak baris yang tak match.

## 🔀 2. LEFT JOIN
**WHAT** — Semua baris dari table KIRI + yang match dari kanan.
```sql
SELECT *
FROM customers c
LEFT JOIN orders o ON c.customer_id = o.customer_id;
```
**PLAIN ENGLISH** — "Ambil SEMUA customer, walaupun dia tak pernah order."
**ANALOGY** — phonebook semua orang, walaupun tak pernah call.
**WHEN** — detect missing data, churn / inactive analysis.

## 🔀 3. RIGHT JOIN
**WHAT** — Semua baris dari table KANAN + yang match dari kiri.
```sql
SELECT *
FROM orders o
RIGHT JOIN customers c ON o.customer_id = c.customer_id;
```
**PLAIN ENGLISH** — "Ambil semua customer walaupun tak ada order."
**ANALOGY** — list semua customer walaupun belum beli apa-apa.
**WHEN** — jarang; biasa orang tukar jadi LEFT JOIN. Guna untuk completeness check.

## 🔁 4. FULL OUTER JOIN
**WHAT** — Semua baris dari KEDUA-DUA table, match atau tidak.
```sql
SELECT *
FROM customers c
FULL OUTER JOIN orders o ON c.customer_id = o.customer_id;
```
**PLAIN ENGLISH** — "Gabung semua data, tak buang sesiapa."
**ANALOGY** — cantum 2 senarai contact tanpa buang sesiapa.
**WHEN** — reconciliation, cari mismatch antara 2 sumber.

## 🧮 5. GROUP BY
**WHAT** — Kumpulkan baris ikut kategori, kira aggregate.
```sql
SELECT customer_id, COUNT(*) AS total_orders
FROM orders
GROUP BY customer_id;
```
**PLAIN ENGLISH** — "Kira berapa order setiap customer."
**ANALOGY** — group pelajar ikut kelas, kira bilangan tiap kelas.
**WHEN** — summary, KPI, metric per kategori.

## 📊 6. WINDOW FUNCTION (PENTING)
**WHAT** — Kira merentas baris TANPA collapse baris (row kekal).
```sql
SELECT *,
       ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY order_date DESC) AS rn
FROM orders;
```
**PLAIN ENGLISH** — "Nomborkan order tiap customer, latest dulu."
**ANALOGY** — tiap customer ada ranking sendiri.
**WHEN** — latest record per group, running total, LAG/LEAD compare.

## 🧱 7. CTE (WITH clause)
**WHAT** — Pecahkan query jadi step-by-step yang reusable.
```sql
WITH recent_orders AS (
    SELECT * FROM orders WHERE order_date > '2025-01-01'
)
SELECT * FROM recent_orders;
```
**PLAIN ENGLISH** — "Buat hasil sementara dulu, lepas tu guna balik."
**ANALOGY** — siapkan kerja step demi step sebelum output akhir.
**WHEN** — query kompleks; lagi senang baca dari subquery bersarang.

## 🧹 8. WHERE (filter)
**WHAT** — Buang baris tak perlu seawal mungkin.
```sql
SELECT * FROM orders WHERE amount > 100;
```
**PLAIN ENGLISH** — "Ambil order lebih RM100 sahaja."
**ANALOGY** — tapis awal sebelum proses (jimat kerja).
**WHEN** — sentiasa; filter awal = pipeline laju (predicate pushdown).

## 🐍 9. PYTHON — FOR LOOP
**WHAT** — Ulang aksi untuk setiap item dalam senarai.
```python
for item in items:
    print(item)
```
**PLAIN ENGLISH** — "Ambil satu-satu item dalam list, proses."
**ANALOGY** — check tiap barang dalam bakul satu per satu.
**WHEN** — proses fail/list/partition satu per satu.

## 🐍 10. PYTHON — DICTIONARY (key-value)
**WHAT** — Simpan data sebagai mapping key → value.
```python
cache = {"user1": 100, "user2": 200}
print(cache["user1"])   # 100
```
**PLAIN ENGLISH** — "Ambil value ikut nama key."
**ANALOGY** — IC → lookup info seseorang.
**WHEN** — lookup pantas, config, mapping source→target.

## 🐍 11. PYTHON — FUNCTION (modular)
**WHAT** — Bungkus logik jadi blok boleh guna semula.
```python
def clean_amount(x):
    return max(x, 0)        # business rule: no negative
```
**PLAIN ENGLISH** — "Satu kerja = satu function, boleh panggil banyak kali."
**ANALOGY** — resepi yang kau boleh ulang guna.
**WHEN** — extract/transform/load logic; pipeline reusable.

## 🐍 12. PYTHON — try/except (production thinking)
**WHAT** — Tangkap error supaya pipeline tak mati terus.
```python
try:
    load(df)
except Exception as e:
    log.error(f"load failed: {e}")
    raise
```
**PLAIN ENGLISH** — "Cuba; kalau gagal, log dan handle elok-elok."
**ANALOGY** — ada plan B bila benda tak jalan.
**WHEN** — semua script production; retry-safe, idempotent.

## ⚙️ 13. PYSPARK (big-data thinking)
**WHAT** — Proses data besar secara distributed (tak muat RAM).
```python
df = df.filter(df.amount > 100)
df = df.groupBy("customer_id").count()
```
**PLAIN ENGLISH** — "SQL tapi untuk data besar, dipecah ke banyak mesin."
**ANALOGY** — ramai pekerja angkat kotak serentak, bukan sorang.
**KEY** — DataFrame = table · transformation = lazy · partition = pecah untuk laju · skew = pecah tak sama rata (bahaya).

## 🧱 14. dbt (transformation layer)
**WHAT** — Framework SQL untuk transform + test + document.
```sql
-- models/marts/customer_spend.sql
SELECT customer_id, SUM(amount) AS total_spent
FROM {{ ref('stg_orders') }}
GROUP BY customer_id
```
**PLAIN ENGLISH** — "SQL yang berstruktur, reusable, ada test."
**ANALOGY** — SQL + governance + susunan kemas.
**KEY** — tests: `unique`, `not_null`, `relationships` · `ref()` bina lineage · docs auto-generate.

## ☁️ 15. AIRFLOW (orchestration)
**WHAT** — Kawal aliran pipeline (urutan + jadual).
```python
ingest >> enrich >> build_mart >> publish
```
**PLAIN ENGLISH** — "ingest jalan dulu, lepas tu enrich, mart, publish."
**ANALOGY** — pengawal trafik untuk data.
**KEY** — DAG = graf dependency · critical path = rantai paling panjang (tentukan SLA) · parallel kalau takde dependency · `catchup`/`retries`/`pool` mempengaruhi SLA.

## 🧱 16. SNOWFLAKE (warehouse)
**WHAT** — Enjin SQL + storage untuk analytics.
**PLAIN ENGLISH** — "Tempat semua data analytics duduk + diquery laju."
**ANALOGY** — otak analitik + gudang data.
**KEY** — pisah compute/storage · clustering key · query optimization · BI-ready.

## 🔥 17. DATA LAYERS (architecture)
**WHAT** — Aliran data: `Raw → Cleaned → Business-ready`.
```
Bronze (raw) → Enrich/Silver (clean+conform) → Data Mart/Gold → Serving/RRD
```
**PLAIN ENGLISH** — "Data mentah → bersih → siap KPI → siap report."
**ANALOGY** — bahan mentah → masak → hidang.
**KEY** — logik duduk di layer yang betul; jangan campak business logic dalam Bronze.

## 🧱 18. STAR SCHEMA (Kimball)
**WHAT** — Fact (event) + Dimension (context).
```
fact_sales(date_sk, product_sk, units_sold)   ← measures
dim_date / dim_product / dim_channel          ← context
```
**PLAIN ENGLISH** — "Fact = apa yang berlaku; dimension = konteks."
**ANALOGY** — fact = resit; dimension = siapa/apa/bila.
**KEY** — **GRAIN = unit analisis (PALING PENTING)** · SCD Type 2 = simpan history · SCD Type 1 = overwrite.

## 🔗 19. STTM (Source-to-Target Mapping) ⭐ SKILL JARANG
**WHAT** — Mapping setiap column: source → transform → target.
| Source Column | Target Column | Transformation |
|---------------|---------------|----------------|
| `cust_id` | `customer_id` | direct mapping |
| `amt` | `total_amount` | `SUM(transaction_amt)` |
| `date` | `order_date` | `CAST` to date |

**PLAIN ENGLISH** — "Column ni datang dari mana + berubah macam mana + berakhir di mana."
**ANALOGY** — buku resepi: ingredient (source) → cara masak (transform) → hidangan (target).
**WHY PENTING** — debugging, audit/compliance, cross-team alignment, single source of truth.

---

## ⚡ 80/20 — Ingat ni sahaja
**SQL core:** JOIN = gabung · LEFT JOIN = simpan semua kiri · GROUP BY = ringkas · WINDOW = ranking/analytics · CTE = step breakdown · WHERE = tapis awal.
**Python core:** LOOP = proses item · DICT = lookup · FUNCTION = modular · try/except = production-safe.
**Pipeline:** Airflow = orchestrate · dbt = transform+test · Spark = big data · Snowflake = warehouse.
**Truth:** STAR SCHEMA + GRAIN = struktur analytics · STTM = peta kebenaran data.

## 💣 Interview reality
Mereka BUKAN test coding competition (bukan LeetCode). Mereka test:
✔ boleh alirkan data dengan betul · ✔ boleh explain data journey · ✔ boleh jaga SLA + consistency · ✔ boleh maintain data truth merentas team.
