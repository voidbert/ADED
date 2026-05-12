#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Script for comparing performance of difference quantization schemes.
#
# Usage:
#     $ module load Python/3.14.2-GCCcore-15.2.0
#     $ python -m venv .venv
#     $ . .venv/bin/activate
#     $ pip install duckdb
#     $ ./quantization-analysis.py ../results/warmup
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

# Chosen reference compiler
COMPILER = 'build-clang-blis'

# Number of preceding runs to discard
WARMUP_RUNS = 1

# Number of measurements to collect
MEASUREMENT_RUNS = 5

# SCRIPT -------------------------------------------------------------------------------------------

import duckdb
import sys

# Parse command-line arguments
if len(sys.argv) != 2:
    print(f'Usage: {sys.argv[0]} <directory>')
    sys.exit(1)

csv_directory = sys.argv[1]

# Load measurement data and filter which measurements to include
duckdb.sql(rf'''
    CREATE VIEW measurements AS SELECT *
    FROM read_csv_auto('{csv_directory}/*.csv', normalize_names=true)
    WHERE run > {WARMUP_RUNS} AND run <= {WARMUP_RUNS + MEASUREMENT_RUNS} AND
          seeding = 'static' AND compiler = '{COMPILER}'
''')

# Compare raw quantization performance
print("\033[1mRAW QUANTIZATION PERFORMANCE\033[0m")
duckdb.sql('''
    SELECT
        model, prompt, quantization,
        MEAN(ttft), STDDEV(ttft),
        MEAN(tpot), STDDEV(tpot),
        MEAN(mem),  STDDEV(mem)
    FROM measurements
    GROUP BY ALL
    ORDER BY model, prompt, quantization ASC
''').show(max_rows=1 << 32)

# Calculate geometric means to compare quantizations
print("\033[1mQUANTIZATION GEOMETRIC MEANS\033[0m")
duckdb.sql('''
    WITH per_config_means AS (
        SELECT
            model, quantization, prompt,
            MEAN(ttft) AS ttft_mean,
            MEAN(tpot) AS tpot_mean,
            MEAN(mem)  AS mem_mean
        FROM measurements
        GROUP BY ALL
    ),
    normalized AS (
        SELECT
            model, quantization, prompt,
            ttft_mean / MIN(ttft_mean) OVER (PARTITION BY model, prompt) AS ttft_ratio,
            tpot_mean / MIN(tpot_mean) OVER (PARTITION BY model, prompt) AS tpot_ratio,
            mem_mean  / MIN(mem_mean)  OVER (PARTITION BY model, prompt) AS mem_ratio
        FROM per_config_means
    )
    SELECT
        quantization,
        GEOMEAN(ttft_ratio) AS ttft_geomean,
        GEOMEAN(tpot_ratio) AS tpot_geomean,
        GEOMEAN(tpot_ratio) AS mem_geomean
    FROM normalized
    GROUP BY quantization
''').show(max_rows=1 << 32)
