# Third-party notices (native image, preview)

Java libraries on the build classpath of `libarcadedb.so` (native-spike build, engine 26.10.2). The licence column comes from each
project's own published licence and was written by hand for this preview; a release build must regenerate it from the build
(for example with `license-maven-plugin` over the resolved classpath) and compare. Full texts: `licenses/` and each project's repository.

| Library | Version | Licence |
|---|---|---|
| ArcadeDB engine, server, network, bolt, postgresw, redisw, graphql, mcp, integration, console, studio | 26.10.2 | Apache-2.0 |
| jvector (+ libjvector-x86_64.so) | 4.0.2 | Apache-2.0 |
| Apache Lucene (core, analysis-common, facet, queries, queryparser, sandbox, spatial3d, spatial-extras) | 10.5.2 | Apache-2.0 |
| JTS Core | 1.20.0 | EPL-2.0 OR EDL-1.0 (BSD-3-Clause) |
| s2-geometry-library-java, spatial4j | 1.0.0, 0.8 | Apache-2.0 |
| ANTLR 4 runtime | 4.13.2 | BSD-3-Clause |
| Undertow core, XNIO api/nio, jboss-threads, jboss-logging, wildfly-common, wildfly-client-config, smallrye-common-* | 2.4.4.Final, 3.8.16, 3.10.1, 3.6.2.Final, 1.5.4.Final, 1.0.1.Final, 2.20.0 | Apache-2.0 |
| Micrometer core, commons, observation | 1.17.1 | Apache-2.0 |
| Swagger core, models, annotations | 2.2.55 | Apache-2.0 |
| Gson, Agrona, LMAX Disruptor, lz4-java, commons-lang3, snakeyaml, univocity-parsers, jspecify, error_prone_annotations | 2.14.0, 1.20.0, 1.2.21, 1.12.0, 3.20.0, 2.4, 2.10.2, 1.0.1, 2.48.0 | Apache-2.0 |
| HdrHistogram | 2.2.2 | BSD-2-Clause OR CC0-1.0 |
| SLF4J api, slf4j-jdk14 | 2.0.20 | MIT |
| jakarta.activation-api, jakarta.xml.bind-api | 1.2.2, 2.3.3 | EDL-1.0 (BSD-3-Clause) |
| jakarta.validation-api | 2.0.2 | Apache-2.0 |
| GraalVM SDK (graal-sdk, polyglot, word, collections) | 25.0.2 / 25.4.4.1.1 | UPL-1.0 |
| GraalVM Substrate VM runtime and OpenJDK classes in the image | 25.4.4.1.1 (CE) | GPL-2.0 WITH Classpath-exception-2.0 |

Dynamic system libraries (not shipped): zlib (libz.so.1), glibc, libstdc++, libgcc_s.
