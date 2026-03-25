# VLDB 2026 Literature Review

Date: 2026-02-25

Scope: papers relevant to ArcadeDB claims (multi-model, embedded deployment, multi-query interfaces, graph + vector workloads)

1. **Multi-model Databases: A New Journey to Handle the Variety of Data**
   ACM Computing Surveys (survey).
   Link: https://dl.acm.org/doi/10.1145/3323214
   Why: canonical survey to define multi-model DBMS scope and taxonomy.

BibTeX:
```bibtex
@article{Lu_2019,
  title={Multi-model Databases: A New Journey to Handle the Variety of Data},
  author={Lu, Jiaheng and Holubová, Irena},
  journal={ACM Computing Surveys},
  year={2019},
  volume={52},
  number={3},
  pages={1--38},
  doi={10.1145/3323214}
}
```

2. **UniBench: A Benchmark for Multi-model Database Management Systems**
  Link: https://link.springer.com/chapter/10.1007/978-3-030-11404-6_2
   Why: prior art for mixed-model benchmark design; useful contrast to your phased StackOverflow pipeline.

BibTeX:
```bibtex
@inbook{Zhang_2019_Unibench,
  title={UniBench: A Benchmark for Multi-model Database Management Systems},
  author={Zhang, Chao and Lu, Jiaheng and Xu, Pengfei and Chen, Yuxing},
  booktitle={Performance Evaluation and Benchmarking for the Era of Artificial Intelligence},
  year={2019},
  pages={7--23},
  doi={10.1007/978-3-030-11404-6_2}
}
```

3. **A Benchmark for Performance Evaluation of a Multi-Model Database vs. Polyglot Persistence**
   JDM (as surfaced by search).
   Link: https://dl.acm.org/doi/abs/10.4018/JDM.321756
   Why: direct comparator framing (single MMDB vs polyglot stack).

BibTeX:
```bibtex
@article{Ye_2023,
  title={A Benchmark for Performance Evaluation of a Multi-Model Database vs. Polyglot Persistence},
  author={Ye, Feng and Sheng, Xinjun and Nedjah, Nadia and Sun, Jun and Zhang, Peng},
  journal={Journal of Database Management},
  year={2023},
  volume={34},
  number={3},
  pages={1--20},
  doi={10.4018/JDM.321756}
}
```

4. **X-Stor: A Cloud-Native NoSQL Database Service with Multi-Model Support**
   PVLDB 17(12):4025–4037, 2024.
   Link: https://www.vldb.org/pvldb/vol17/p4025-lei.pdf
   Why: recent industrial/system paper on multi-model support (cloud-native angle).

BibTeX:
```bibtex
@article{Lei_2024,
  title={X-Stor: A Cloud-Native NoSQL Database Service with Multi-Model Support},
  author={Lei, Hongyu and Li, Chunhua and Zhou, Ke and Zhu, Jianping and Yan, Kezhou and Xiao, Fen and Xie, Ming and Wang, Jiang and Di, Shiyu},
  journal={Proceedings of the VLDB Endowment},
  year={2024},
  volume={17},
  number={12},
  pages={4025--4037},
  doi={10.14778/3685800.3685824}
}
```

5. **SQLite: past, present, and future**
   PVLDB 15(12), 2022.
   Link: https://www.vldb.org/pvldb/vol15/p3535-gaffney.pdf
   Why: modern in-process baseline context (transactional/analytical/blob flavors).

BibTeX:
```bibtex
@article{Gaffney_2022,
  title={SQLite: past, present, and future},
  author={Gaffney, Kevin P. and Prammer, Martin and Brasfield, Larry and Hipp, D. Richard and Kennedy, Dan and Patel, Jignesh M.},
  journal={Proceedings of the VLDB Endowment},
  year={2022},
  volume={15},
  number={12},
  pages={3535--3547},
  doi={10.14778/3554821.3554842}
}
```

6. **DuckDB: an Embeddable Analytical Database**
   SIGMOD demo paper (2019).
   Link: https://duckdb.org/pdf/SIGMOD2019-demo-duckdb.pdf
   Why: key embedded-OLAP baseline rationale.

BibTeX:
```bibtex
@inproceedings{Raasveldt_2019,
  title={DuckDB: an Embeddable Analytical Database},
  author={Raasveldt, Mark and M{"u}hleisen, Hannes},
  booktitle={Proceedings of the 2019 International Conference on Management of Data},
  year={2019},
  pages={1981--1984},
  doi={10.1145/3299869.3320212}
}
```

7. **DortDB: Bridging Query Languages for Multi-Model Data Ponds**
   PVLDB 18 (2025).
   Link: https://www.vldb.org/pvldb/vol18/p5335-koupil.pdf
   Why: directly relevant to your SQL + Cypher + vector language-bridge positioning.

BibTeX:
```bibtex
@article{Jezek_2025,
  title={DortDB: Bridging Query Languages for Multi-Model Data Ponds},
  author={Je{\v{z}}ek, Filip and Koupil, Pavel and Kopeck{\'y}, Michal and B{\'a}rt{\'\i}k, J{\'a}chym and Holubov{\'a}, Irena},
  journal={Proceedings of the VLDB Endowment},
  year={2025},
  volume={18},
  number={12},
  pages={5335--5338},
  doi={10.14778/3750601.3750665}
}
```

8. **The SQL++ Query Language: Configurable, Unifying and Semi-structured**
   arXiv + prior publication lineage.
   Link: https://arxiv.org/abs/1405.3631
   Why: unification language perspective for semi-structured querying.

BibTeX:
```bibtex
@misc{ong2014sqlpp,
  title={The SQL++ Query Language: Configurable, Unifying and Semi-structured},
  author={Ong, Kian Win and Papakonstantinou, Yannis and Vernoux, Romain},
  year={2014},
  eprint={1405.3631},
  archivePrefix={arXiv},
  primaryClass={cs.DB},
  doi={10.48550/arXiv.1405.3631}
}
```

9. **Formalising opencypher Graph Queries in Relational Algebra**
   ADBIS 2017 (arXiv version available).
   Link: https://arxiv.org/abs/1705.02844
   Why: formal bridge between graph query semantics and relational algebra.

BibTeX:
```bibtex
@misc{marton2017formalising,
  title={Formalising opencypher Graph Queries in Relational Algebra},
  author={Marton, J{'o}zsef and Sz{'a}rnyas, G{'a}bor and Varr{'o}, D{'a}niel},
  year={2017},
  eprint={1705.02844},
  archivePrefix={arXiv},
  primaryClass={cs.DB},
  doi={10.48550/arXiv.1705.02844}
}
```

10. **openCypher 9 Specification and Resources**
    Link: https://opencypher.org/
    Why: standards context for graph query language interoperability (non-paper, cite carefully).

BibTeX:
```bibtex
@misc{opencypher_spec,
  title={openCypher 9 Specification and Resources},
  author={{openCypher Implementers Group}},
  year={2025},
  url={https://opencypher.org/},
  note={Accessed: 2026-02-25}
}
```

11. **The LDBC Social Network Benchmark: Interactive Workload**
    ACM SIGMOD 2015.
    Link: https://dl.acm.org/doi/10.1145/2723372.2742786
    Why: standard transactional graph benchmark reference.

BibTeX:
```bibtex
@inproceedings{Erling_2015,
  title={The LDBC Social Network Benchmark: Interactive Workload},
  author={Erling, Orri and Averbuch, Alex and Larriba-Pey, Josep and Chafi, Hassan and Gubichev, Andrey and Prat, Arnau and Pham, Minh-Duc and Boncz, Peter},
  booktitle={Proceedings of the 2015 ACM SIGMOD International Conference on Management of Data},
  year={2015},
  pages={619--630},
  doi={10.1145/2723372.2742786}
}
```

12. **The LDBC Social Network Benchmark Interactive Workload v2: A Transactional Graph Query Benchmark with Deep Delete Operations**
    Link: https://ir.cwi.nl/pub/33319/33319.pdf
    Why: modern benchmark engineering ideas for stable path-query runtimes under updates.

BibTeX:
```bibtex
@inbook{Puroja_2024,
  title={The LDBC Social Network Benchmark Interactive Workload v2: A Transactional Graph Query Benchmark with Deep Delete Operations},
  author={P{"u}roja, David and Waudby, Jack and Boncz, Peter and Sz{'a}rnyas, G{'a}bor},
  booktitle={Performance Evaluation and Benchmarking},
  year={2024},
  pages={107--123},
  doi={10.1007/978-3-031-68031-1_8}
}
```

13. **The LDBC Financial Benchmark: Transaction Workload**
    PVLDB 18 (as surfaced in search).
    Link: https://www.vldb.org/pvldb/vol18/p3007-qi.pdf
    Why: recent graph benchmark design patterns and choke-point analysis.

BibTeX:
```bibtex
@article{Qi_2025,
  title={The LDBC Financial Benchmark: Transaction Workload},
  author={Qi, Shipeng and Tong, Bing and Hu, Jiatao and Lin, Heng and Pang, Yue and Yuan, Wei and Lyu, Songlin and Guo, Zhihui and Huang, Ke and Ba, Xujin and Yin, Qiang and Shen, Youren and Zhou, Yan and Lv, Tao and Li, Jia and Zou, Lei and Wu, Yongwei and Sz{'a}rnyas, G{'a}bor and Zhu, Xiaowei and Chen, Wenguang and Hong, Chuntao},
  journal={Proceedings of the VLDB Endowment},
  year={2025},
  volume={18},
  number={9},
  pages={3007--3020},
  doi={10.14778/3746405.3746424}
}
```

14. **Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs**
    IEEE TPAMI 2018. DOI: 10.1109/TPAMI.2018.2889473
    Link: https://arxiv.org/abs/1603.09320
    Why: foundational ANN method used widely in DB vector indexes.

BibTeX:
```bibtex
@misc{malkov2016efficient,
  title={Efficient and robust approximate nearest neighbor search using Hierarchical Navigable Small World graphs},
  author={Malkov, Yu. A. and Yashunin, D. A.},
  year={2016},
  eprint={1603.09320},
  archivePrefix={arXiv},
  primaryClass={cs.DS},
  doi={10.48550/arXiv.1603.09320}
}
```

15. **DiskANN: Fast Accurate Billion-point Nearest Neighbor Search on a Single Node**
    NeurIPS 2019.
    Link (MSR page): https://www.microsoft.com/en-us/research/publication/diskann-fast-accurate-billion-point-nearest-neighbor-search-on-a-single-node/
    Why: disk-backed ANN baseline and design motivation.

BibTeX:
```bibtex
@inbook{10.5555/3454287.3455520,
author = {Subramanya, Suhas Jayaram and Devvrit and Kadekodi, Rohan and Krishaswamy, Ravishankar and Simhadri, Harsha Vardhan},
title = {DiskANN: fast accurate billion-point nearest neighbor search on a single node},
year = {2019},
publisher = {Curran Associates Inc.},
address = {Red Hook, NY, USA},
booktitle = {Proceedings of the 33rd International Conference on Neural Information Processing Systems},
articleno = {1233},
numpages = {11}
}
```

16. **SPANN: Highly-efficient Billion-scale Approximate Nearest Neighbor Search**
    Link: https://www.microsoft.com/en-us/research/publication/spann-highly-efficient-billion-scale-approximate-nearest-neighbor-search/
    Why: memory-disk hybrid ANN reference.

BibTeX:
```bibtex
@misc{chen2021spann,
  title={SPANN: Highly-efficient Billion-scale Approximate Nearest Neighbor Search},
  author={Chen, Qi and Zhao, Bing and Wang, Haidong and Li, Mingqin and Liu, Chuanjie and Li, Zengzhong and Yang, Mao and Wang, Jingdong},
  year={2021},
  eprint={2111.08566},
  archivePrefix={arXiv},
  primaryClass={cs.DB},
  doi={10.48550/arXiv.2111.08566}
}
```

17. **FreshDiskANN: A Fast and Accurate Graph-Based ANN Index for Streaming Similarity Search**
    Link (project page): https://www.microsoft.com/en-us/research/project/project-akupara-approximate-nearest-neighbor-search-for-large-scale-semantic-search/
    Why: update-aware ANN context for ingestion-vs-query tradeoffs.

BibTeX:
```bibtex
@misc{singh2021freshdiskann,
  title={FreshDiskANN: A Fast and Accurate Graph-Based ANN Index for Streaming Similarity Search},
  author={Singh, Aditi and Subramanya, Suhas Jayaram and Krishnaswamy, Ravishankar and Simhadri, Harsha Vardhan},
  year={2021},
  eprint={2105.09613},
  archivePrefix={arXiv},
  primaryClass={cs.IR},
  doi={10.48550/arXiv.2105.09613}
}
```

18. **Cost-Effective, Low Latency Vector Search with Azure Cosmos DB**
    (You already summarized this in your 2025 folder.)
    Why: concrete industrial system showing deep vector integration in an operational DB.

BibTeX:
```bibtex
@article{Upreti_2025,
  title={Cost-Effective, Low Latency Vector Search with Azure Cosmos DB},
  author={Upreti, Nitish and Simhadri, Harsha Vardhan and Sundar, Hari Sudan and Sundaram, Krishnan and Boshra, Samer and Perumalswamy, Balachandar and Atri, Shivam and Chisholm, Martin and Singh, Revti Raman and Yang, Greg and Hass, Tamara and Dudhey, Nitesh and Pattipaka, Subramanyam and Hildebrand, Mark and Manohar, Magdalen and Moffitt, Jack and Xu, Haiyang and Datha, Naren and Gupta, Suryansh and Krishnaswamy, Ravishankar and Gupta, Prashant and Sahu, Abhishek and Varada, Hemeswari and Barthwal, Sudhanshu and Mor, Ritika and Codella, James and Cooper, Shaun and Pilch, Kevin and Moreno, Simon and Kataria, Aayush and Kulkarni, Santosh and Deshpande, Neil and Sagare, Amar and Billa, Dinesh and Fu, Zishan and Vishal, Vipul},
  journal={Proceedings of the VLDB Endowment},
  year={2025},
  volume={18},
  number={12},
  pages={5166--5183},
  doi={10.14778/3750601.3750635}
}
```

19. **GaussDB-Vector: A Large-Scale Persistent Real-Time Vector Database for LLM Applications**
    (You already summarized this in your 2025 folder.)
    Why: industrial large-scale vector system baseline and design alternatives.

BibTeX:
```bibtex
@article{Sun_2025,
  title={GaussDB-Vector: A Large-Scale Persistent Real-Time Vector Database for LLM Applications},
  author={Sun, Ji and Li, Guoliang and Pan, James and Wang, Jiang and Xie, Yongqing and Liu, Ruicheng and Nie, Wen},
  journal={Proceedings of the VLDB Endowment},
  year={2025},
  volume={18},
  number={12},
  pages={4951--4963},
  doi={10.14778/3750601.3750619}
}
```

20. **M2Bench: A Database Benchmark for Multi-Model Analytic Workloads**
    PVLDB 16(4):747–759, 2022. DOI: 10.14778/3574245.3574259
    Link: https://www.vldb.org/pvldb/vol16/p747-moon.pdf
    Why: fills the exact benchmark gap between UniBench-style mixed modeling and your phased end-to-end multi-model workload design.

BibTeX:
```bibtex
@article{Kim_2022,
  title={M2Bench: A Database Benchmark for Multi-Model Analytic Workloads},
  author={Kim, Bogyeong and Koo, Kyoseung and Enkhbat, Undraa and Kim, Sohyun and Kim, Juhun and Moon, Bongki},
  journal={Proceedings of the VLDB Endowment},
  year={2022},
  volume={16},
  number={4},
  pages={747--759},
  doi={10.14778/3574245.3574259}
}
```

21. **Multi-model query languages: taming the variety of big data**
    Distributed and Parallel Databases (Springer), 2023. DOI: 10.1007/s10619-023-07433-1
    Link: https://link.springer.com/article/10.1007/s10619-023-07433-1
    Why: strong citation to justify “multiple query interfaces” as a first-class research topic.

BibTeX:
```bibtex
@article{Guo_2023,
  title={Multi-model query languages: taming the variety of big data},
  author={Guo, Qingsong and Zhang, Chao and Zhang, Shuxun and Lu, Jiaheng},
  journal={Distributed and Parallel Databases},
  year={2023},
  volume={42},
  number={1},
  pages={31--71},
  doi={10.1007/s10619-023-07433-1}
}
```

22. **Filtered Vector Search: State-of-the-Art and Research Opportunities**
    PVLDB 18 tutorial track context (2025).
    Link: https://www.vldb.org/pvldb/vol18/p5488-caminal.pdf
    Why: gives vocabulary and taxonomy for filtered ANN (pre-filter/post-filter/inline-filter) and DB-style declarative behavior.

BibTeX:
```bibtex
@article{Chronis_2025,
  title={Filtered Vector Search: State-of-the-Art and Research Opportunities},
  author={Chronis, Yannis and Caminal, Helena and Papakonstantinou, Yannis and {"O}zcan, Fatma and Ailamaki, Anastasia},
  journal={Proceedings of the VLDB Endowment},
  year={2025},
  volume={18},
  number={12},
  pages={5488--5492},
  doi={10.14778/3750601.3750700}
}
```

23. **Vector Database Management Techniques and Systems**
    ACM SIGMOD Companion 2024. DOI: 10.1145/3626246.3654691
    Link: https://dl.acm.org/doi/10.1145/3626246.3654691
    Why: concise systems-oriented overview to anchor architecture and workload terminology.

BibTeX:
```bibtex
@inproceedings{Pan_2024,
  title={Vector Database Management Techniques and Systems},
  author={Pan, James Jie and Wang, Jianguo and Li, Guoliang},
  booktitle={Companion of the 2024 International Conference on Management of Data},
  year={2024},
  pages={597--604},
  doi={10.1145/3626246.3654691}
}
```

24. **Survey of vector database management systems**
    The VLDB Journal 33(4):1591–1615, 2024. DOI: 10.1007/s00778-024-00864-x
    Link: https://link.springer.com/article/10.1007/s00778-024-00864-x
    Why: broad, peer-reviewed survey anchor that avoids over-reliance on vendor docs/blogs.

BibTeX:
```bibtex
@article{Pan_2024_vldbj,
  title={Survey of vector database management systems},
  author={Pan, James Jie and Wang, Jianguo and Li, Guoliang},
  journal={The VLDB Journal},
  year={2024},
  volume={33},
  number={5},
  pages={1591--1615},
  doi={10.1007/s00778-024-00864-x}
}
```

25. **ISO/IEC 9075-16:2023 Information technology --- Database languages SQL --- Part 16: Property Graph Queries (SQL/PGQ)**
    Link: https://www.iso.org/standard/79473.html
    Why: standards trajectory for SQL-native property graph querying; pairs well with openCypher/GQL interoperability discussion.

BibTeX:
```bibtex
@standard{ISO9075_16_2023,
  title={ISO/IEC 9075-16:2023 Information technology --- Database languages SQL --- Part 16: Property Graph Queries (SQL/PGQ)},
  organization={International Organization for Standardization},
  year={2023},
  url={https://www.iso.org/standard/79473.html},
  note={First edition, accessed 2026-02-25}
}
```

26. **HAKES: Scalable Vector Database for Embedding Search Service**
    PVLDB 18, 2025. DOI: 10.14778/3746405.3746427
    Link: https://dl.acm.org/doi/10.14778/3746405.3746427
    Why: strong support if you discuss read/write concurrency and ingestion-vs-query tradeoffs in vector systems.

BibTeX:
```bibtex
@article{Hu_2025,
  title={HAKES: Scalable Vector Database for Embedding Search Service},
  author={Hu, Guoyu and Cai, Shaofeng and Dinh, Tien Tuan Anh and Xie, Zhongle and Yue, Cong and Chen, Gang and Ooi, Beng Chin},
  journal={Proceedings of the VLDB Endowment},
  year={2025},
  volume={18},
  number={9},
  pages={3049--3062},
  doi={10.14778/3746405.3746427}
}
```

27. **Fast Vector Search in PostgreSQL: A Decoupled Approach**
    CIDR 2026.
    Link: https://www.vldb.org/cidrdb/2026/fast-vector-search-in-postgresql-a-decoupled-approach.html
    Why: high-quality research baseline for “vector inside PostgreSQL” beyond extension docs.

BibTeX:
```bibtex
@inproceedings{Liu_2026,
  title={Fast Vector Search in PostgreSQL: A Decoupled Approach},
  author={Liu, Jiayi and Zhang, Yunan and Jin, Chenzhe and Gupta, Aditya and Liu, Shige and Wang, Jianguo},
  booktitle={CIDR 2026},
  year={2026},
  url={https://www.vldb.org/cidrdb/2026/fast-vector-search-in-postgresql-a-decoupled-approach.html}
}
```

28. **Holistic evaluation in multi-model databases benchmarking**
    Distributed and Parallel Databases, 2019. DOI: 10.1007/s10619-019-07279-6
    Link: https://link.springer.com/article/10.1007/s10619-019-07279-6
    Why: extended UniBench analysis with parameter curation and broader MMDB benchmarking insights.

BibTeX:
```bibtex
@article{Zhang_2019_Holistic,
  title={Holistic evaluation in multi-model databases benchmarking},
  author={Zhang, Chao and Lu, Jiaheng},
  journal={Distributed and Parallel Databases},
  year={2019},
  volume={39},
  number={1},
  pages={1--33},
  doi={10.1007/s10619-019-07279-6}
}
```
