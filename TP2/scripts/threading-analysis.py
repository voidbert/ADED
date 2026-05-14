#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Script for determining the performance impact of different threading and NUMA configurations.

# Usage:
#     $ module load Python/3.14.2-GCCcore-15.2.0
#     $ python -m venv .venv
#     $ . .venv/bin/activate
#     $ pip install duckdb
#     $ ./threading-analysis.py ../results/warmup ../results/threading
#
# LICENSE ------------------------------------------------------------------------------------------
#
# Copyright (C) 2026 Humberto Gomes, José Lopes, José Soares
#
# This file is part of FastInference.
#
# FastInference is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# FastInference is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without
# even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with FastInference. If
# not, see <https://www.gnu.org/licenses/>.
#
# CONFIGURATION ------------------------------------------------------------------------------------

# Compiler used
COMPILER = 'build-clang-blis'

# Quantization used
QUANTIZATION = 'Q4_K_M'

# Number of preceding runs to discard
WARMUP_RUNS = 1

# Number of measurements to collect
MEASUREMENT_RUNS = 5

# SCRIPT -------------------------------------------------------------------------------------------

import duckdb
import sys

# Parse command-line arguments
if len(sys.argv) != 3:
    print(f'Usage: {sys.argv[0]} <warmup-directory> <threading-directory>')
    sys.exit(1)

warmup_directory    = sys.argv[1]
threading_directory = sys.argv[2]

# Load no-NUMA measurement data and process basic statistics (mean and stddev)
duckdb.sql(f'''
    CREATE VIEW no_numa_measurements AS SELECT
        compiler, model, quantization, seeding, prompt,
        '48T NO-NUMA' AS threads,
        MEAN(ttft)    AS ttft_mean,
        STDDEV(ttft)  AS ttft_stdev,
        MEAN(tpot)    AS tpot_mean,
        STDDEV(tpot)  AS tpot_stdev,
        MEAN(mem)     AS mem_mean,
        STDDEV(mem)   AS mem_stdev
    FROM read_csv_auto('{warmup_directory}/*.csv', normalize_names=true)
    WHERE run > {WARMUP_RUNS} AND run <= {WARMUP_RUNS + MEASUREMENT_RUNS} AND
          compiler = '{COMPILER}' AND quantization = '{QUANTIZATION}' AND seeding = 'static'
    GROUP BY ALL
    ORDER BY ALL
''')

# Load threading measurement data and process basic statistics (mean and stddev)
duckdb.sql(f'''
    CREATE VIEW numa_measurements AS SELECT
        compiler, model, quantization, seeding, prompt,
        CONCAT(threads, 'T NUMA') AS threads,
        MEAN(ttft)                AS ttft_mean,
        STDDEV(ttft)              AS ttft_stdev,
        MEAN(tpot)                AS tpot_mean,
        STDDEV(tpot)              AS tpot_stdev,
        MEAN(mem)                 AS mem_mean,
        STDDEV(mem)               AS mem_stdev
    FROM read_csv_auto('{threading_directory}/*.csv', normalize_names=true)
    WHERE run > {WARMUP_RUNS} AND run <= {WARMUP_RUNS + MEASUREMENT_RUNS}
    GROUP BY ALL
    ORDER BY ALL
''')

# Combine NUMA-aware and non-NUMA-aware measurements
print('\033[1mTHREADING RAW DATA\033[0m')
duckdb.sql('''
    CREATE VIEW all_measurements AS
        SELECT * FROM no_numa_measurements
            UNION
        SELECT * FROM numa_measurements
''')

duckdb.sql('''
    SELECT * FROM all_measurements
    ORDER BY ALL
''').show(max_rows=1 << 32)

# Calculate geometric means to thread configurations
print('\033[1mTHREADING GEOMETRIC MEANS\033[0m')
duckdb.sql('''
    WITH normalized AS (
        SELECT
            model, prompt, threads,
            ttft_mean / MIN(ttft_mean) OVER (PARTITION BY model, prompt) AS ttft_ratio,
            tpot_mean / MIN(tpot_mean) OVER (PARTITION BY model, prompt) AS tpot_ratio
        FROM all_measurements
    )
    SELECT
        threads,
        GEOMEAN(ttft_ratio) AS ttft_geomean,
        GEOMEAN(tpot_ratio) AS tpot_geomean,
    FROM normalized
    GROUP BY threads
    ORDER BY tpot_geomean ASC
''').show(max_rows=1 << 32)
