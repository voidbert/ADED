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
import re
import subprocess
import sys
import tempfile

from aded import config, util
from aded.queries import Original

# Runs the diff command on two files
def diff_files(original_path: str, modified_path: str) -> str:
    return subprocess.run(
        ['diff', '--color=always', '-u', original_path, modified_path],
        capture_output=True
    ).stdout.decode('utf-8')

# Checks if query differences are attributable to differences in floating-point arithmetic
def check_diff_for_fp_errors(diff_result: str) -> bool:
    # Parse differences between lines
    original_differences = dict(re.findall(r'\n[^\-]*-\\def\\(\w*){([^}]*)}', diff_result))
    query_differences    = dict(re.findall(r'\n[^+]*\+\\def\\(\w*){([^}]*)}', diff_result))

    # Check for additional or missing parameters
    if list(original_differences) != list(query_differences):
        return False

    # Check for floating-point differences
    for parameters, original_value in original_differences.items():
        # Check floating point values
        try:
            original_value_fp = float(original_value)
            query_value_fp    = float(query_differences[parameters])
            error             = abs(original_value_fp - query_value_fp) / original_value_fp

            if error > config.MAX_RELATIVE_ERROR:
                return False

        except ValueError, ZeroDivisionError:
            # Casting errors -> not floats -> string differences -> fail
            # Division error -> original is 0 and the other value is not -> fail
            return False

    return True

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
    context_threads = util.get_context_threads()
    with Original.create_context(context_threads) as original_context:
        with query_class.create_context(context_threads) as query_context:

            # Create temporary files for the outputs of the original query and the query being
            # tested
            with tempfile.NamedTemporaryFile() as original_output:
                with tempfile.NamedTemporaryFile() as query_output:
                    year_start_date = datetime.date(config.YEAR, 1, 1)

                    # Test results for each month
                    for month in range(1, 13):
                        month_name = list(calendar.month_name)[month]
                        print(f'Testing {month_name}')

                        # Run queries
                        original_query = Original(month, config.YEAR, year_start_date)
                        original_query.run(original_context, dataset_path, original_output.name)

                        query = query_class(month, config.YEAR, year_start_date)
                        query.run(query_context, dataset_path, query_output.name)

                        # Compare query outputs
                        diff_result = diff_files(original_output.name, query_output.name)
                        fp_errors   = check_diff_for_fp_errors(diff_result)

                        # Fail if outputs differ
                        if diff_result:
                            if fp_errors:
                                print(
                                    f'\033[35mAcceptable differences for {month_name}:\033[0m',
                                    file=sys.stderr
                                )
                                print(diff_result, file=sys.stderr)
                            else:
                                print(
                                    f'\033[31mUnacceptable differences for {month_name}:\033[0m',
                                    file=sys.stderr
                                )

                                print(diff_result, file=sys.stderr)
                                sys.exit(1)

                        # Truncate temporary files
                        original_output.truncate(0)
                        original_output.seek(0)
                        query_output.truncate(0)
                        query_output.seek(0)

                        # Reset contexts
                        original_context.between_runs_cleanup()
                        query_context.between_runs_cleanup()
