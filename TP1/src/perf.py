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
import datetime
import json
import socket
import tempfile
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

    parser.add_argument('-e', '--events',   nargs='?')
    parser.add_argument('-o', '--outfile',  nargs='?')
    parser.add_argument('-w', '--warmup',   nargs='?', type=int)
    parser.add_argument('-r', '--runs',     nargs='?', type=int)
    parser.add_argument('-n', '--nthreads', nargs='?', type=__parse_thread_list)

    args = parser.parse_args()

    # Use default arguments if arguments are not set
    query_class = queries[args.query]
    output_file = args.outfile  or 'perf.json'
    warmup_runs = args.warmup   or 0
    runs        = args.runs     or 3
    nthreads    = args.nthreads or [util.get_context_threads()]

    # Run scalability analysis
    output_data = {
        'query':       args.query,
        'hostname':    socket.gethostname(),
        'scalability': {}
    }

    for nthread in nthreads:
        # Create (and time) context creation
        context_init_start = time.monotonic()
        with query_class.create_context(nthread, events=args.events) as context:
            context_init_end  = time.monotonic()
            scalability_entry = {
                'threads':         nthread,
                'contextInitTime': context_init_end - context_init_start,
                'runs':            []
            }

            # Run all runs for the current number of threads
            for run in range(warmup_runs + runs):
                # User feedback
                if run >= warmup_runs:
                    print(f'Running: {nthread} threads -- run {run + 1 - warmup_runs}')
                else:
                    print(f'Running: {nthread} threads -- warmup run {run + 1}')

                # Measure dataset loading and query execution times
                t0 = time.monotonic()

                query = query_class(MONTH, YEAR, datetime.date(YEAR, 1, 1))
                query.load_dataset(context, args.dataset)

                t1 = time.monotonic()

                query.process_dataset(context)

                with tempfile.NamedTemporaryFile() as query_output_file:
                    query.output_result(query_output_file.name)

                t2 = time.monotonic()

                # Add non-warmup runs to output file
                if run >= warmup_runs:
                    scalability_entry['runs'].append({
                        'datasetLoadTime':    t1 - t0,
                        'datasetProcessTime': t2 - t1,
                        'totalTime':          t2 - t0
                    })

                # Cleanup context before next run 
                context.between_runs_cleanup()


        # Insert thread data into final file
        output_data['scalability'][str(nthread)] = scalability_entry

    # Output file data
    with open(output_file, 'w') as json_file:
        json.dump(output_data, json_file, indent=4)
        json_file.write('\n')
