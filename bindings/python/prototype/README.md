# JRE Bundling Prototype

This directory contains the Docker-based prototype for JRE bundling validation.

## Purpose

Validate the JRE bundling approach locally before implementing full CI/CD:

- Analyze JAR dependencies with `jdeps`
- Build minimal JRE with `jlink`
- Test JRE functionality
- Measure size impact

## Quick Start

```bash
# Build the JRE prototype
./build-jre-prototype.sh

# Output will be in ./output/
# - analysis/required-modules.txt - Java modules needed
# - minimal-jre/                  - Minimal JRE build
# - jars/                         - ArcadeDB JAR files
```

## Files

- `Dockerfile.jre-prototype` - Multi-stage Docker build for JRE analysis and creation
- `build-jre-prototype.sh` - Build script that orchestrates Docker build and extraction
- `output/` - Generated output directory (git-ignored)

## Expected Results

- **JRE Size:** ~40-70 MB (compressed)
- **Required Modules:** Core Java modules for ArcadeDB operation
- **Functionality:** JRE can run `java -version` and basic JVM operations

## Next Steps

After successful prototype:

1. Test JRE with Python/JPype
2. Create prototype packages (base + JRE variants)
3. Validate with actual ArcadeDB operations
4. Document findings
5. Update build system based on learnings
