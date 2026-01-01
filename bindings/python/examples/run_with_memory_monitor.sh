#!/bin/bash
#
# Run a Python script with memory monitoring
#
# Usage:
#   ./run_with_memory_monitor.sh <log_prefix> <python_command>
#
# Example:
#   ./run_with_memory_monitor.sh vector_large "ARCADEDB_JVM_ARGS='-Xmx8g -Xms8g' python 06_vector_search_recommendations.py --source-db my_test_databases/movielens_graph_large_db --db-path my_test_databases/movielens_graph_large_db_vectors"
#

if [ $# -lt 2 ]; then
    echo "Usage: $0 <log_prefix> <python_command>"
    echo ""
    echo "Example:"
    echo "  $0 vector_large \"python 06_vector_search_recommendations.py --source-db my_test_databases/movielens_graph_large_db --db-path my_test_databases/movielens_graph_large_db_vectors\""
    exit 1
fi

LOG_PREFIX=$1
shift
# Store command exactly as passed (will be used with exec, no quotes)
CMD="$@"

# Create log directory
LOG_DIR="./benchmark_logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/${LOG_PREFIX}_${TIMESTAMP}.log"
MEM_LOG="$LOG_DIR/${LOG_PREFIX}_${TIMESTAMP}_memory.log"

echo "========================================================================"
echo "Running with memory monitoring"
echo "========================================================================"
echo "Command: $CMD"
echo "Output log: $LOG_FILE"
echo "Memory log: $MEM_LOG"
echo ""

# Function to monitor memory usage of a process (Python + embedded Java JVM)
# Note: Java JVM is embedded within Python process (GraalVM), not a separate process
monitor_memory() {
    local PID=$1
    local MEM_LOG=$2

    echo "Time,RSS_MB,VSZ_MB,CPU%" > "$MEM_LOG"

    while kill -0 $PID 2> /dev/null; do
        # Get Python process stats (includes embedded Java JVM)
        # RSS = Resident Set Size (actual physical memory used)
        # VSZ = Virtual Size (total virtual memory allocated)
        STATS=$(ps -o rss=,vsz=,%cpu= -p $PID 2> /dev/null || echo "0 0 0")
        RSS_KB=$(echo $STATS | awk '{print $1}')
        VSZ_KB=$(echo $STATS | awk '{print $2}')
        CPU=$(echo $STATS | awk '{print $3}')

        # Convert to MB
        RSS_MB=$(echo "scale=2; $RSS_KB/1024" | bc)
        VSZ_MB=$(echo "scale=2; $VSZ_KB/1024" | bc)

        TIMESTAMP=$(date +%s)
        echo "$TIMESTAMP,$RSS_MB,$VSZ_MB,$CPU" >> "$MEM_LOG"

        sleep 2
    done
}

# Run the command in background
# Run normally first, then find the actual Python child process
eval "$CMD" > "$LOG_FILE" 2>&1 &
SHELL_PID=$!

# Wait a moment for Python to start, then find the actual Python process
sleep 1

# Find the Python child process (not the shell wrapper)
# Match any python* process (python, python3, python3.12, etc.)
PYTHON_PID=$(pgrep -P $SHELL_PID -f python 2> /dev/null | head -1)

# If we didn't find a Python child, try looking for any child process
if [ -z "$PYTHON_PID" ]; then
    PYTHON_PID=$(pgrep -P $SHELL_PID 2> /dev/null | head -1)
fi

# Use the Python PID if found, otherwise fall back to the shell PID
if [ -n "$PYTHON_PID" ] && [ "$PYTHON_PID" != "$SHELL_PID" ]; then
    PID=$PYTHON_PID
else
    PID=$SHELL_PID
fi

echo "Started process (PID: $PID)"
echo "Monitoring memory usage..."
echo ""

# Start memory monitoring
monitor_memory $PID "$MEM_LOG"

# Wait for process to complete
wait $PID
EXIT_CODE=$?

echo ""
echo "========================================================================"
echo "Process completed (exit code: $EXIT_CODE)"
echo "========================================================================"
echo ""

# Display memory summary
if [ -f "$MEM_LOG" ]; then
    echo "MEMORY USAGE SUMMARY:"
    echo "------------------------------------------------------------------------"

    # Extract peak values (skip header)
    PEAK_RSS=$(tail -n +2 "$MEM_LOG" | cut -d',' -f2 | sort -n | tail -1)
    PEAK_VSZ=$(tail -n +2 "$MEM_LOG" | cut -d',' -f3 | sort -n | tail -1)
    PEAK_CPU=$(tail -n +2 "$MEM_LOG" | cut -d',' -f4 | sort -n | tail -1)

    # Calculate averages
    AVG_RSS=$(tail -n +2 "$MEM_LOG" | cut -d',' -f2 | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')
    AVG_VSZ=$(tail -n +2 "$MEM_LOG" | cut -d',' -f3 | awk '{sum+=$1; count++} END {if(count>0) print sum/count; else print 0}')

    if [ ! -z "$PEAK_RSS" ] && [ "$PEAK_RSS" != "" ]; then
        printf "  Peak RSS: %8.2f MB (actual memory) | Peak VSZ: %8.2f MB (virtual) | Peak CPU: %6.1f%%\n" \
            $PEAK_RSS $PEAK_VSZ $PEAK_CPU
        printf "  Avg  RSS: %8.2f MB                | Avg  VSZ: %8.2f MB\n" \
            $AVG_RSS $AVG_VSZ
    fi
    echo "------------------------------------------------------------------------"
    echo ""
fi

echo "Logs saved:"
echo "  Output: $LOG_FILE"
echo "  Memory: $MEM_LOG"
echo ""

exit $EXIT_CODE
