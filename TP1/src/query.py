# ABOUT --------------------------------------------------------------------------------------------
#
# Abstract base class for the Deucalion report query. Contains code common to all query
# implementations.
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

import abc
import calendar
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from contexts import Context

# Deucalion report query -- abstract base class.
#
# This class fills in basic report parameters that do not change between query implementations.
#
# Query execution methods can be overridden to develop query implementations with different
# performance characteristics.
class Query(abc.ABC):
    def __init__(self, month: int, year: int, first_year_date: date) -> None:
        # Get calendar month name abbreviations
        month_abbreviations = list(calendar.month_abbr)

        # Determine ranges of months to be analyzed
        self.tag_months = {
            '':          [month_abbreviations[month]],
            'Trimester': month_abbreviations[1:month + 1] if month < 3 else
                         month_abbreviations[month - 2 : month + 1],
            'Year':      month_abbreviations[1:month + 1]
        }

        # Determine limit dates of month and trimester ranges
        first_month_date     = date(year, month, 1)
        next_month_date      = first_month_date + relativedelta(months=1)
        last_month_date      = next_month_date  - relativedelta(days=1)
        first_trimester_date = date(year, 1, 1) if month < 3 else date(year, month - 2, 1)

        # Initialize parameters to be outputted to a file
        self.output_parameters = {
            # Reporting period
            'reportPeriod':          self.__format_date_range(first_month_date, last_month_date),
            'reportPeriodTrimester': self.__format_date_range(first_trimester_date, last_month_date),
            'reportPeriodYear':      self.__format_date_range(first_year_date, last_month_date),
            'reportMonth':           list(calendar.month_name)[month],
            'reportYear':            year,

            # Deucalion configuration and allocation
            'armnodes': 1632,
            'amdnodes':  500,
            'gpunodes':  132,

            'percentaviail': 0.80, # Yes, we know this is misspelled. So is the original.
            'eurohpcavail':  0.35,

            # Month job data
            'ndays': (next_month_date - first_month_date).days,

            'armusedhours': 0,
            'amdusedhours': 0,
            'gpuusedhours': 0,

            'gpuusedhoursEuroHPC': 0,
            'amdusedhoursEuroHPC': 0,
            'armusedhoursEuroHPC': 0,

            'armJobs': 0,
            'amdJobs': 0,
            'gpuJobs': 0,

            'gpuCompletedJobs': 0,
            'gpuFailedJobs':    0,
            'armCompletedJobs': 0,
            'amdCompletedJobs': 0,
            'amdFailedJobs':    0,
            'armFailedJobs':    0,

            'gpuJobsEuroHPC': 0,
            'amdJobsEuroHPC': 0,
            'armJobsEuroHPC': 0,

            # Trimester job data
            'ndaysTrimester': (next_month_date - first_trimester_date).days,

            'gpuCompletedJobsTrimester': 0,
            'gpuFailedJobsTrimester':    0,
            'armCompletedJobsTrimester': 0,
            'amdCompletedJobsTrimester': 0,
            'amdFailedJobsTrimester':    0,
            'armFailedJobsTrimester':    0,

            'armusedhoursTrimester': 0,
            'amdusedhoursTrimester': 0,
            'gpuusedhoursTrimester': 0,

            'armJobsTrimester': 0,
            'amdJobsTrimester': 0,
            'gpuJobsTrimester': 0,

            'gpuusedhoursEuroHPCTrimester': 0,
            'amdusedhoursEuroHPCTrimester': 0,
            'armusedhoursEuroHPCTrimester': 0,

            'gpuJobsEuroHPCTrimester': 0,
            'amdJobsEuroHPCTrimester': 0,
            'armJobsEuroHPCTrimester': 0,

            # Year job data
            'ndaysYear': (next_month_date - first_year_date).days,

            'gpuCompletedJobsYear': 0,
            'gpuFailedJobsYear':    0,
            'armCompletedJobsYear': 0,
            'amdCompletedJobsYear': 0,
            'amdFailedJobsYear':    0,
            'armFailedJobsYear':    0,

            'armusedhoursYear': 0,
            'amdusedhoursYear': 0,
            'gpuusedhoursYear': 0,

            'armJobsYear': 0,
            'amdJobsYear': 0,
            'gpuJobsYear': 0,

            'gpuJobsEuroHPCYear': 0,
            'amdJobsEuroHPCYear': 0,
            'armJobsEuroHPCYear': 0,

            'gpuusedhoursEuroHPCYear': 0,
            'amdusedhoursEuroHPCYear': 0,
            'armusedhoursEuroHPCYear': 0,

            # Additional LaTeX macros
            'monthhours':     '{\\inteval{\\ndays * 24}}',
            'hoursTrimester': '{\\inteval{\\ndaysTrimester * 24}}',
            'hoursYear':      '{\\inteval{\\ndaysYear * 24}}'
        }

    # Creates a context (e.g.: Spark session) that can be used for multiple query executions
    @staticmethod
    @abc.abstractmethod
    def create_context(processes: int) -> Context:
        pass

    # Runs the query: loads a dataset, processes it, and writes the results to a LaTeX file
    def run(self, spark: Context, dataset_path: str, output_file: str) -> None:
        self.load_dataset(spark, dataset_path)
        self.process_dataset(spark)
        self.output_result(output_file)

    # Loads a dataset directory
    @abc.abstractmethod
    def load_dataset(self, spark: Context, dataset_path: str) -> None:
        pass

    # Fills in query output parameters from an already loaded dataset
    @abc.abstractmethod
    def process_dataset(self, spark: Context) -> None:
        pass

    # Writes the query results (output parameters) to an output file
    def output_result(self, output_file: str) -> None:
        with open(output_file, 'w') as f:
            for key, value in self.output_parameters.items():
                f.write(f'\\def\\{key}{{{value}}}\n')

    # Formats a range of dates for the output file
    def __format_date_range(self, start: date, end: date) -> str:
        return f'{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}'
