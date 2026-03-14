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
                        'ARM'
                    WHEN Partition LIKE '%a100%' THEN
                        'GPU'
                    ELSE
                        'AMD'
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
        # Group job count and hours by month, partition, account, state
        assert isinstance(context, DuckDBContext)
        connection = context.connection

        aggregated_results = connection.execute('''
            SELECT Period, Partition, Account, State, COUNT(*), SUM(totalJobSeconds)
            FROM jobs GROUP BY 1, 2, 3, 4
        ''').fetchall()

        # Use aggregated data to for computing query results
        for tag, months in self.tag_months.items():
            hours: dict[str, int] = {}
            jobs: dict[str, int]  = {}

            for row in aggregated_results:
                if row[0] in months:
                    # Count complete and failed jobs per cluster
                    if row[3] == 'COMPLETED':
                        self.output_parameters[f'{row[1].lower()}CompletedJobs{tag}'] += row[4]
                    else:
                        self.output_parameters[f'{row[1].lower()}FailedJobs{tag}'] += row[4]

                    # Count jobs and hours per cluster
                    if row[2] != 'LOCAL':
                        hours[row[1]] = hours.get(row[1], 0) + row[5]
                        jobs[row[1]]  = jobs.get(row[1], 0)  + row[4]

                    for k, v in hours.items():
                        self.output_parameters[f'{k.lower()}usedhours{tag}'] = v / 3600

                    for k, v in jobs.items():
                        self.output_parameters[f'{k.lower()}Jobs{tag}'] = v

                    # Count EuroHPC jobs and hours
                    if row[2] == 'EHPC':
                        self.output_parameters[f'{row[1].lower()}usedhoursEuroHPC{tag}'] += \
                            row[5] / 3600
                        self.output_parameters[f'{row[1].lower()}JobsEuroHPC{tag}'] += row[4]
