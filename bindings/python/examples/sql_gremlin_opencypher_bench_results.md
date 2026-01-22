# Gremlin vs OpenCypher vs SQL Benchmark

## Dataset

This benchmark uses a synthetic graph seeded by the script:

- 10000 `Person` vertices with `name`, `age`, and `level`
- 500 `Company` vertices with `name` and `industry`
- 2000 `Project` vertices with `name` and `budget`
- 200 `Department` vertices with `name` and `cost_center`
- 200 `Skill` vertices with `name` and `level`
- 200 `Location` vertices with `name` and `country`
- 600 `Team` vertices with `name` and `focus`
- 8000 `Task` vertices with `title`, `priority`, and `estimate`
- 500 `Tag` vertices with `name` and `category`
- 300 `Event` vertices with `name` and `year`
- Edges:
  - `WORKS_FOR` (Person → Company) with `since`
  - `WORKS_ON` (Person → Project) with `role`
  - `KNOWS` (Person → Person) with `since`
  - `LIKES` (Person → Project) with `weight`
  - `MANAGES` (Person → Company) with `since`
  - `LOCATED_IN` (Company → Location) with `since`
  - `MEMBER_OF` (Person → Team) with `since`
  - `HAS_SKILL` (Person → Skill) with `years`
  - `PART_OF` (Company → Department) with `since`
  - `ASSIGNED_TO` (Person → Task) with `status`
  - `TAGGED_WITH` (Person → Tag) with `source`
  - `ATTENDED` (Person → Event) with `rating`
  - `COLLABORATES_WITH` (Person → Person) with `since`

- Iterations: 100
- Warmup: 2
- Parallel: True

## Results

| Query | Cypher vs SQL | Cypher vs Gremlin | OpenCypher mean (ms) | OpenCypher stdev (ms) | SQL mean (ms) | SQL stdev (ms) | Gremlin mean (ms) | Gremlin stdev (ms) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| people_over_20 | ✅ | ✅ | 25.938195 | 6.368695 | 23.993260 | 5.800837 | 27.153165 | 4.921867 |
| works_for_company | ✅ | ✅ | 46.423296 | 16.300428 | 40.055828 | 23.089628 | 72.043145 | 15.999090 |
| knows_since_2021 | ✅ | ✅ | 8.750049 | 7.746411 | 13.245796 | 13.998256 | 11.358863 | 8.752086 |
| knows_1_3_hops | ✅ | ✅ | 7.129558 | 9.804660 | 11.988790 | 6.266366 | 10.111611 | 10.740980 |
| optional_company | ✅ | ✅ | 85.433362 | 27.645340 | 65.793237 | 20.901965 | 120.310970 | 34.376449 |
| count_employees | ✅ | ✅ | 44.578314 | 15.109996 | 40.379600 | 15.108250 | 29.009667 | 11.735496 |
| senior_count_by_company | ✅ | ✅ | 28.645634 | 13.294578 | 28.090067 | 15.117315 | 22.364223 | 7.548751 |
| project_contributors | ✅ | ✅ | 70.854826 | 25.587902 | 63.107718 | 26.973216 | 39.333446 | 17.756942 |
| coworkers_of_person_1 | ✅ | ✅ | 9.795564 | 12.009517 | 94.602446 | 18.496517 | 12.432237 | 7.741996 |
| projects_for_company_1 | ✅ | ✅ | 2.598263 | 5.662460 | 4.255634 | 8.477657 | 2.699133 | 1.876815 |
| high_weight_likes | ✅ | ✅ | 44.219339 | 16.552219 | 41.077888 | 18.521235 | 45.327094 | 11.519360 |
| Average | - | - | 34.033309 | 14.189291 | 38.780933 | 15.704658 | 35.649414 | 12.088167 |
