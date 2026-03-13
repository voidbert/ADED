#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Script for benchmarking query implementations.
#
# LICENSE ------------------------------------------------------------------------------------------
#
# Copyright (C) 2026 Humberto Gomes, José Lopes, José Soares
#
# This file is part of Deucalion Job Query.
#
# Deucalion Job Query is free software: you can redistribute it and/or modify it under the terms of
# the GNU General Public License as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# Deucalion Job Query is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with Deucalion Job Query.
# If not, see <https://www.gnu.org/licenses/>.
#
# SOURCE FILE --------------------------------------------------------------------------------------

import argparse
import csv
import datetime
import socket
import time

import util

# Hardcoded year and month for report results.
YEAR  = 2025
MONTH = 1

# Parses a list of threads for a scalability analysis
def __parse_thread_list(thread_list: str) -> list[int]:
    return [int(threads) for threads in thread_list.split(',')]

if __name__ == '__main__':
    # Parse command-line arguments
    queries = util.get_avaialable_queries()
    parser  = argparse.ArgumentParser()

    parser.add_argument('query', choices=queries)
    parser.add_argument('dataset')

    parser.add_argument('-o', '--outfile', nargs='?')
    parser.add_argument('-w', '--warmup',  nargs='?', type=int)
    parser.add_argument('-r', '--runs',    nargs='?', type=int)
    parser.add_argument('-n', '--nprocs',  nargs='?', type=__parse_thread_list)

    args = parser.parse_args()

    # Use default arguments if arguments are not set
    query_class = queries[args.query]
    output_file = args.outfile or 'perf.csv'
    warmup_runs = args.warmup  or 0
    runs        = args.runs    or 3
    nprocs      = args.nprocs  or [util.get_spark_num_processes()]

    # Run performance analysis
    hostname = socket.gethostname()

    with open(output_file, 'w') as csv_file:
        csv_writer = csv.writer(csv_file, lineterminator='\n')
        csv_writer.writerow([
            'HOSTNAME',
            'NPROC',
            'RUN',
            'SPARK_INIT_TIME',
            'DATASET_LOAD_TIME',
            'DATASET_PROCESS_TIME'
        ])
        csv_file.flush()

        for nproc in nprocs:
            # Create (and time) context creation
            context_init_start = time.monotonic()
            with query_class.create_context(nproc) as context:
                context_init_end = time.monotonic()

                for run in range(warmup_runs + runs):
                    # User feedback
                    if run >= warmup_runs:
                        print(f'Running: {nproc} processes -- run {run + 1 - warmup_runs}')
                    else:
                        print(f'Running: {nproc} processes -- warmup run {run + 1}')

                    # Measure dataset loading and query execution times
                    t0 = time.monotonic()

                    query = query_class(MONTH, YEAR, datetime.date(YEAR, 1, 1))
                    query.load_dataset(context, args.dataset)

                    t1 = time.monotonic()

                    query.process_dataset(context)

                    t2 = time.monotonic()

                    # Write non-warmup run performance data to the CSV file
                    if run >= warmup_runs:
                        csv_writer.writerow([
                            hostname,
                            nproc,
                            run,
                            context_init_end - context_init_start,
                            t1 - t0,
                            t2 - t1
                        ])

                        csv_file.flush()
