# ABOUT --------------------------------------------------------------------------------------------
#
# Query implementation based on DuckDB. This file is not named 'duckdb.py' not to shadow the duckdb
# module.
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

import duckdb
import os

from contexts import Context, DuckDBContext
from query import Query

class DuckDB(Query):
    @staticmethod
    def create_context(threads: int, **kwargs: object) -> Context:
        return DuckDBContext(threads, **kwargs)

    def load_dataset(self, context: Context, dataset_path: str) -> None:
        # List CSV files to load
        csv_files = [
            os.path.join(dataset_path, entry.name)
            for entry in os.scandir(dataset_path)
            if entry.name.startswith('job') and entry.is_file()
        ]

        # Load CSV files
        assert isinstance(context, DuckDBContext)
        connection = context.connection

        connection.execute(rf'''
            CREATE OR REPLACE VIEW jobs AS SELECT
                regexp_replace(filename, '.*jobs_(.+)\.txt', '\1') AS Period,
                TRY_CAST(NNodes     AS BIGINT)                     AS NNodes,
                TRY_CAST(ElapsedRaw AS BIGINT)                     AS ElapsedRaw,
                AllocTRES,

                CASE
                    WHEN State = 'COMPLETED' THEN
                        'COMPLETED'
                    ELSE
                        'FAILED'
                END AS State,

                CASE
                    WHEN Partition LIKE '%arm%'  THEN
                        'arm'
                    WHEN Partition LIKE '%a100%' THEN
                        'gpu'
                    ELSE
                        'amd'
                END AS Partition,

                CASE
                    WHEN Account LIKE 'f%'  THEN
                        'FCT'
                    WHEN Account LIKE 'ee%' THEN
                        'EHPC'
                    ELSE
                        'LOCAL'
                END AS Account,

                CASE
                    WHEN Partition LIKE '%a100%' THEN
                        CASE
                            WHEN AllocTRES IS NULL OR AllocTRES = '' THEN
                                TRY_CAST(NNodes AS BIGINT)
                            WHEN regexp_matches(AllocTRES, 'gres/gpu=\d+') THEN
                                CAST(regexp_extract(AllocTRES, 'gres/gpu=(\d+)', 1) AS BIGINT)
                            ELSE
                                TRY_CAST(NNodes AS BIGINT) * 4
                        END
                    ELSE
                        TRY_CAST(NNodes AS BIGINT)
                END * TRY_CAST(ElapsedRaw AS BIGINT) AS totalJobSeconds

            FROM read_csv(
                {csv_files},
                delim='|',
                header=true,
                filename=true,
                types={{'NNodes': 'VARCHAR', 'ElapsedRaw': 'VARCHAR'}}
            )
        ''')

    def process_dataset(self, context: Context) -> None:
        # Group job count and hours by month, partition, account, and state
        assert isinstance(context, DuckDBContext)
        connection = context.connection

        aggregated_results = connection.execute('''
            SELECT Period, Partition, Account, State, COUNT(*), SUM(totalJobSeconds)
            FROM jobs GROUP BY 1, 2, 3, 4
        ''').fetchall()

        # Use aggregated data to for computing query results
        for tag, months in self.tag_months.items():
            hours: dict[str, int] = {'arm': 0, 'amd': 0, 'gpu': 0}

            for row in aggregated_results:
                if row[0] in months:
                    row_cluster = row[1]
                    row_account = row[2]
                    row_state   = row[3]
                    row_jobs    = row[4]
                    row_hours   = row[5]

                    # Count complete and failed jobs per cluster
                    if row_state == 'COMPLETED':
                        self.output_parameters[f'{row_cluster}CompletedJobs{tag}'] += row_jobs
                    else:
                        self.output_parameters[f'{row_cluster}FailedJobs{tag}'] += row_jobs

                    # Count jobs and hours per cluster
                    if row_account != 'LOCAL':
                        hours[row_cluster]                                += row_hours
                        self.output_parameters[f'{row_cluster}Jobs{tag}'] += row_jobs

                    for k, v in hours.items():
                        self.output_parameters[f'{k}usedhours{tag}'] = v / 3600

                    # Count EuroHPC jobs and hours
                    if row_account == 'EHPC':
                        self.output_parameters[f'{row_cluster}usedhoursEuroHPC{tag}'] += \
                            row_hours / 3600
                        self.output_parameters[f'{row_cluster}JobsEuroHPC{tag}'] += row_jobs
