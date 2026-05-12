#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Script for determining how many warmup runs are necessary.

# Usage:
#     $ module load Python/3.14.2-GCCcore-15.2.0
#     $ python -m venv .venv
#     $ . .venv/bin/activate
#     $ pip install duckdb
#     $ ./warmup-analysis.py ../results/warmup
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
# SCRIPT -------------------------------------------------------------------------------------------

import duckdb
import sys

# Parse command-line arguments
if len(sys.argv) != 2:
    print(f'Usage: {sys.argv[0]} <directory>')
    sys.exit(1)

csv_directory = sys.argv[1]

# Load measurement data
duckdb.sql(rf'''
    CREATE VIEW all_measurements AS SELECT *
    FROM read_csv_auto('{csv_directory}/*.csv', normalize_names=true)
''')

# Verify that, for all non-first runs, the number of prompt processed tokens is one due to KV-cache
# usage. This query shows this phenomena happens for all models except for Gemma.
print("\033[1mKV-CACHE USAGE\033[0m")
duckdb.sql('''
    SELECT
        model,
        COUNT(*) as measurment_count,
        COUNTIF((run = 1 AND prompt_n > 1) OR (run > 1 AND prompt_n == 1)) AS property_applies
    FROM all_measurements
    GROUP BY ALL
    ORDER BY model ASC
''').show(max_rows=1 << 32)

# Apply MSER method: calculate mean-square-error after excluding the first `warmup_run` measurements
duckdb.sql('''
    CREATE VIEW mses AS SELECT
        compiler, model, quantization, seeding, prompt,
        run - 1 AS warmup_runs,
        VARIANCE(ttft) OVER wind / COUNT(*) OVER wind AS mse,
    FROM all_measurements
    WINDOW wind AS (
        PARTITION BY compiler, model, quantization, seeding, prompt
        ORDER BY run
        ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING
    )
    QUALIFY mse IS NOT NULL
''')

# Print MSEs for debugging
"""
print("\033[1mMSER METHOD\033[0m")
duckdb.sql('''
    SELECT
        model, compiler, quantization, seeding, prompt, warmup_runs, mse
    FROM mses
    WHERE warmup_runs <= 3
    ORDER BY ALL ASC
''').show(max_rows=1 << 32)
"""

# Verify that MSER is orders of magnitude higher when there are no warmup runs: calculate geometric
# mean of quotients between successive MSEs
print("\033[1mMSER QUOTIENT GEOMETRIC MEANS\033[0m")
duckdb.sql(f'''
    WITH mses_quotients AS (
        SELECT
            compiler, model, quantization, seeding, prompt, warmup_runs,
            LAG(mse) OVER (
                PARTITION BY compiler, model, quantization, seeding, prompt
                ORDER BY warmup_runs
            ) / mse AS mse_quotient
        FROM mses
        QUALIFY mse_quotient IS NOT NULL
        ORDER BY compiler, model, quantization, seeding, prompt, warmup_runs
    )
    SELECT
        warmup_runs,
        geomean(mse_quotient) AS mse_quotient_geomean
    FROM mses_quotients
    GROUP BY warmup_runs
    ORDER BY warmup_runs
''').show(max_rows=1 << 32)
