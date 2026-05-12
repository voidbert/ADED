#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Script for determining the performance impact of mmap.

# Usage:
#     $ module load Python/3.14.2-GCCcore-15.2.0
#     $ python -m venv .venv
#     $ . .venv/bin/activate
#     $ pip install duckdb
#     $ pip install scipy
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
# CONFIGURATION ------------------------------------------------------------------------------------

# Number of preceding runs to discard
WARMUP_RUNS = 1

# Number of measurements to collect
MEASUREMENT_RUNS = 5

# SCRIPT -------------------------------------------------------------------------------------------

import duckdb
from scipy.stats import ttest_ind
import sys

# Parse command-line arguments
if len(sys.argv) != 3:
    print(f'Usage: {sys.argv[0]} <warmup-directory> <mmap-directory>')
    sys.exit(1)

warmup_directory = sys.argv[1]
mmap_directory   = sys.argv[2]

# Load --no-mmap measurement data and process basic statistics (mean and stddev)
duckdb.sql(f'''
    CREATE VIEW no_mmap_measurements AS SELECT
        compiler, model, quantization, seeding, prompt,
        MEAN(ttft)   AS no_mmap_ttft_mean,
        STDDEV(ttft) AS no_mmap_ttft_stdev,
        MEAN(tpot)   AS no_mmap_tpot_mean,
        STDDEV(tpot) AS no_mmap_tpot_stdev,
        MEAN(mem)    AS no_mmap_mem_mean,
        STDDEV(mem)  AS no_mmap_mem_stdev
    FROM read_csv_auto('{warmup_directory}/*.csv', normalize_names=true)
    WHERE run > {WARMUP_RUNS} AND run <= {WARMUP_RUNS + MEASUREMENT_RUNS}
    GROUP BY ALL
    ORDER BY ALL
''')

# Load --mmap measurement data and process basic statistics (mean and stddev)
duckdb.sql(f'''
    CREATE VIEW mmap_measurements AS SELECT
        compiler, model, quantization, seeding, prompt,
        MEAN(ttft)   AS mmap_ttft_mean,
        STDDEV(ttft) AS mmap_ttft_stdev,
        MEAN(tpot)   AS mmap_tpot_mean,
        STDDEV(tpot) AS mmap_tpot_stdev,
        MEAN(mem)    AS mmap_mem_mean,
        STDDEV(mem)  AS mmap_mem_stdev
    FROM read_csv_auto('{mmap_directory}/*.csv', normalize_names=true)
    WHERE run > {WARMUP_RUNS} AND run <= {WARMUP_RUNS + MEASUREMENT_RUNS}
    GROUP BY ALL
    ORDER BY ALL
''')

# Combine --no-mmap and --mmap measurements
duckdb.sql('''
    CREATE VIEW measurements AS SELECT   
            mmap_measurements.compiler,
            mmap_measurements.model,
            mmap_measurements.quantization,
            mmap_measurements.seeding,
            mmap_measurements.prompt,
            no_mmap_ttft_mean,  mmap_ttft_mean,
            no_mmap_ttft_stdev, mmap_ttft_stdev,
            no_mmap_tpot_mean,  mmap_tpot_mean,
            no_mmap_tpot_stdev, mmap_tpot_stdev,
            no_mmap_mem_mean,   mmap_mem_mean,
            no_mmap_mem_stdev,  mmap_mem_stdev
        FROM mmap_measurements INNER JOIN no_mmap_measurements ON
            mmap_measurements.compiler     = no_mmap_measurements.compiler     AND
            mmap_measurements.model        = no_mmap_measurements.model        AND
            mmap_measurements.quantization = no_mmap_measurements.quantization AND
            mmap_measurements.seeding      = no_mmap_measurements.seeding      AND
            mmap_measurements.prompt       = no_mmap_measurements.prompt
''')

# Show combined measurements
print('\033[1mMMAP AND NO-MMAP RESULTS\033[0m')
duckdb.sql('SELECT * FROM measurements').show(max_rows=1 << 32)

# Show, using double sided t-tests, that there is no difference in performance between --mmap and
# --no-mmap in TTFT
no_mmap_ttft = [
    row[0] for row in duckdb.sql('SELECT no_mmap_ttft_mean FROM measurements').fetchall()
]

mmap_ttft = [
    row[0] for row in duckdb.sql('SELECT mmap_ttft_mean FROM measurements').fetchall()
]

_, p_value = ttest_ind(mmap_ttft, no_mmap_ttft, alternative='two-sided')
print('\033[1mTTFT T-TEST\033[0m')
print('p =', p_value, end='\n\n')


# Show, using double sided t-tests, that there is no difference in performance between --mmap and
# --no-mmap in TPOT
no_mmap_tpot = [
    row[0] for row in duckdb.sql('SELECT no_mmap_tpot_mean FROM measurements').fetchall()
]

mmap_tpot = [
    row[0] for row in duckdb.sql('SELECT mmap_tpot_mean FROM measurements').fetchall()
]

_, p_value = ttest_ind(mmap_tpot, no_mmap_tpot, alternative='two-sided')
print('\033[1mTPOT T-TEST\033[0m')
print('p =', p_value)
