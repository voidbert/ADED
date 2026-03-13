#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Script for validating query output, comparing it to that of the original query.
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

import calendar
import datetime
from pyspark.sql import SparkSession
import subprocess
import sys
import tempfile

import original
import util

# Hardcoded year for report results. It only influences output parameters related to time ranges,
# so it need not be changed for using other years' datasets.
YEAR = 2025

if __name__ == '__main__':
    # Parse command line arguments
    queries = util.get_avaialable_queries()
    if len(sys.argv) == 3 and sys.argv[1] in queries:
        query_class  = queries[sys.argv[1]]
        dataset_path = sys.argv[2]
    else:
        print(f'Usage:             {sys.argv[0]} <query class> <dataset path>', file=sys.stderr)
        print('Available queries:', ', '.join(queries), file=sys.stderr)
        sys.exit(1)

    # Initialize contexts
    spark_processes = util.get_spark_num_processes()
    with original.Original.create_context(spark_processes) as original_context:
        with query_class.create_context(spark_processes) as query_context:

            # Create temporary files for the outputs of the original query and the query being
            # tested
            with tempfile.NamedTemporaryFile() as original_output:
                with tempfile.NamedTemporaryFile() as query_output:
                    year_start_date = datetime.date(YEAR, 1, 1)

                    # Test results for each month
                    for month in range(1, 13):
                        month_name = list(calendar.month_name)[month]
                        print(f'Testing {month_name}')

                        original_query = original.Original(month, YEAR, year_start_date)
                        original_query.run(original_context, dataset_path, original_output.name)

                        query = query_class(month, YEAR, year_start_date)
                        query.run(query_context, dataset_path, query_output.name)

                        # Compare query outputs
                        diff_result = subprocess.run(
                            [
                                'diff', '--color=always', '-u',
                                original_output.name, query_output.name
                            ],
                            capture_output=True
                        ).stdout.decode('utf-8')

                        # Fail if outputs differ
                        if diff_result:
                            print(f'Queries do not match for month {month_name}', file=sys.stderr)
                            print(diff_result, file=sys.stderr)
                            sys.exit(1)
