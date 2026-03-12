#!/usr/bin/env python3

# ABOUT --------------------------------------------------------------------------------------------
#
# Script for running the query implementations.
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
import calendar
import datetime
from pyspark.sql import SparkSession

import util

# Parses a YY-MM-DD date from the command-line arguments
def __parse_cmd_date(date_str: str) -> datetime.date:
    return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

if __name__ == '__main__':
    # Get calendar month name abbreviations (and remove 0-th month) and available query classes
    month_abbreviations = list(calendar.month_abbr)[1:]
    queries = util.get_avaialable_queries()

    # Parse command-line arguments
    parser = argparse.ArgumentParser()

    parser.add_argument('query', choices=queries)
    parser.add_argument('dataset')

    parser.add_argument('-o', '--outfile', nargs='?')
    parser.add_argument('-m', '--month',   nargs='?', choices=month_abbreviations)
    parser.add_argument('-y', '--year',    nargs='?', type=int)
    parser.add_argument('-s', '--start',   nargs='?', type=__parse_cmd_date)

    args = parser.parse_args()

    # Use default arguments (this year, previous month) if arguments are not set
    today           = datetime.datetime.now().date()
    query_class     = queries[args.query]
    outfile         = args.outfile or 'params.tex'
    month           = month_abbreviations.index(args.month) + 1 if args.month else today.month - 1
    year            = args.year    or today.year
    first_year_date = args.start   or datetime.date(year, 1, 1)

    # Run query
    spark_processes = util.get_spark_num_processes()
    spark           = SparkSession.builder.master(f'local[{spark_processes}]') \
                                          .appName('deucalion-query')          \
                                          .getOrCreate()

    query = query_class(month, year, first_year_date)
    query.run(spark, args.dataset, outfile)
