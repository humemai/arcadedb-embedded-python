# Operations Guide

Understanding ArcadeDB operations, file structure, logging, and maintenance for the
Python bindings.

## Overview

ArcadeDB creates various files and directories during operation for different purposes:

- **Database files**: Core data storage (embedded mode)
- **Server files**: Multi-user configuration (server mode)
- **Log files**: Three types of logs in different locations
- **Transaction logs**: Write-ahead logging for durability
- **Backup files**: Database snapshots

Understanding this structure helps with monitoring, debugging, and maintenance.

## File Structure

### Typical Directory Layout

When running ArcadeDB applications, you'll see this structure:

```
your_project/
├── your_app.py
├── log/                         # JVM and ArcadeDB logs
│   ├── arcadedb.log.0           # Current ArcadeDB log
│   ├── arcadedb.log.1           # Rotated log file
│   ├── arcadedb.log.2           # Older rotated file
│   ├── arcadedb.log.0.lck       # Log lock file
│   ├── hs_err_pid12345.log      # JVM crash dump
│   └── hs_err_pid67890.log      # Another crash dump
├── my_databases/                # Your databases root
│   ├── production_db/           # Embedded database
│   │   ├── configuration.json   # Database config
│   │   ├── schema.json          # Schema definition
│   │   ├── statistics.json      # Performance stats
│   │   ├── dictionary.*.dict    # String compression
│   │   ├── MyType_*.bucket      # Data files
│   │   ├── txlog_*.wal          # Transaction logs
│   │   └── database.lck         # Database lock
│   ├── backups/                 # Backup directory
│   ├── config/                  # Server configuration
│   │   ├── server-users.jsonl   # User accounts
│   │   └── server-groups.json   # Permissions
│   └── log/                     # Server event logs
│       ├── server-event-log-*.jsonl
│       └── server-event-log-*.jsonl
```

## Logging System

ArcadeDB has **three distinct types of logs** stored in **two different locations**:

### 1. JVM and ArcadeDB Application Logs

**Location**: `./log/` (relative to your Python script)

**Files**:

- `arcadedb.log.0` - Current application log
- `arcadedb.log.1`, `arcadedb.log.2`, etc. - Rotated logs
- `arcadedb.log.0.lck` - Log rotation lock file

**Content**: Application-level events, database operations, performance info
```
2025-10-22 10:23:21.560 INFO  [ArcadeDBServer] ArcadeDB Server v25.10.1 starting up...
2025-10-22 10:23:21.563 INFO  [ArcadeDBServer] Running on Linux - OpenJDK 64-Bit Server VM 21.0.4
2025-10-22 10:23:21.628 INFO  [ArcadeDBServer] Server root path: /path/to/databases
2025-10-22 10:23:21.928 INFO  [HttpServer] HTTP Server started (port=2480)
```

### 2. JVM Crash Dumps

**Location**: `./log/` (same directory as application logs)

**Files**: `hs_err_pid<process_id>.log`

**Content**: JVM fatal error information (crashes, segfaults)
```
# A fatal error has been detected by the Java Runtime Environment:
# SIGSEGV (0xb) at pc=0x000000000056950b, pid=1194752
# JRE version: OpenJDK Runtime Environment Corretto-25
# Problematic frame: C  [python+0x16950b]  PyObject_RichCompareBool+0x3b
```

### 3. Server Event Logs (Server Mode Only)

**Location**: `<server_root>/log/` (inside server root directory)

**Files**: `server-event-log-<timestamp>.<sequence>.jsonl`

**Content**: Structured server lifecycle events in JSON Lines format
```json
{"time":"2025-10-22 10:22:47.888","type":"INFO","component":"Server","db":null,"message":"ArcadeDB Server started in 'development' mode"}
{"time":"2025-10-22 10:22:49.059","type":"INFO","component":"Server","db":null,"message":"Server shutdown correctly"}
```

### Log Configuration

**Rotation**: Application logs rotate automatically:

- Current: `arcadedb.log.0`
- Previous: `arcadedb.log.1`, `arcadedb.log.2`, etc.
- Default: 5 files, 10MB each

**Verbosity**: Controlled by Java system properties:

```python
import jpype

# Set before importing arcadedb_embedded
jpype.startJVM(
    "-Djava.util.logging.level=DEBUG",
    "-Darcadedb.log.level=FINE"
)

import arcadedb_embedded as arcadedb
```

## Database Files (Embedded Mode)

### Core Database Files

**configuration.json** - Database settings

```json
{
  "configuration": {
    "timezone": "UTC",
    "dateFormat": "yyyy-MM-dd"
  }
}
```

**schema.json** - Schema definition with types, properties, indexes

```json
{
  "schemaVersion": 19,
  "dbmsVersion": "25.10.1-SNAPSHOT",
  "types": {
    "User": {
      "type": "d",
      "parents": [],
      "buckets": ["User_0"],
      "properties": {
        "email": {"type": "STRING", "mandatory": true}
      },
      "indexes": {
        "User.email": {"type": "LSM_TREE", "unique": true}
      }
    }
  }
}
```

**statistics.json** - Performance and storage statistics

```json
{
  "User_0": {
    "pages": [
      {"id": 0, "free": 57314},
      {"id": 1, "free": 45123}
    ]
  }
}
```

### Data Storage Files

**Type_N.M.P.vQ.bucket** - Actual data storage

- `Type`: Document/Vertex/Edge type name
- `N`: Bucket number
- `M`: Sub-bucket
- `P`: Page size
- `Q`: Version

Example: `User_0.1.65536.v0.bucket`

**dictionary.X.Y.vZ.dict** - String compression dictionary

- Frequently used strings stored once
- Referenced by ID in data files
- Reduces storage space significantly

### Transaction Files

**txlog_N.wal** - Write-Ahead Log files

- Ensures ACID properties
- Transaction durability
- Crash recovery
- Auto-rotation when full

**database.lck** - Database lock file

- Prevents concurrent access
- Contains process information
- Removed on clean shutdown

## Server Files (Server Mode Only)

### Configuration Files

**server-users.jsonl** - User accounts (JSON Lines format)
```jsonl
{"name":"root","databases":{"*":["admin"]},"password":"PBKDF2WithHmacSHA256$..."}
{"name":"user1","databases":{"mydb":["read"]},"password":"PBKDF2WithHmacSHA256$..."}
```

**server-groups.json** - Permission groups
```json
{
  "databases": {
    "*": {
      "groups": {
        "admin": {
          "resultSetLimit": -1,
          "access": ["updateSecurity", "updateSchema"],
          "types": {
            "*": {
              "access": ["createRecord", "readRecord", "updateRecord", "deleteRecord"]
            }
          }
        }
      }
    }
  }
}
```

### Directory Structure

**backups/** - Database backup storage

- Created by backup operations
- Timestamped directories
- Full database copies

**databases/** - Individual database directories

- Each database in separate subdirectory
- Same structure as embedded databases

## See Also

- [Database Management](core/database.md) - Database lifecycle and configuration
- [Server Mode](server.md) - Multi-user server setup
- [Troubleshooting](../development/troubleshooting.md) - Common issues and solutions
- [Architecture](../development/architecture.md) - System design overview
