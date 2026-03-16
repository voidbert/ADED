# ABOUT --------------------------------------------------------------------------------------------
#
# Query implementation based on PostgreSQL.
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
import re

from contexts import Context, PostgreSQLContext
from query import Query

class PostgreSQL(Query):
    @staticmethod
    def create_context(threads: int, **kwargs: object) -> Context:
        return PostgreSQLContext(threads, **kwargs)

    def load_dataset(self, context: Context, dataset_path: str) -> None:
        assert isinstance(context, PostgreSQLContext)
        cursor = context.cursor

        # Create table with CSV schema for data loading
        cursor.execute('''
            CREATE TEMP TABLE jobs_csv (
                JobID         TEXT       NOT NULL,
                JobIDRaw      INT        NOT NULL,
                ElapsedRaw    INT        NOT NULL,
                Account       TEXT       NOT NULL,
                AllocCPUS     INT        NOT NULL,
                CPUTimeRAW    BIGINT     NOT NULL,
                NNodes        INT        NOT NULL,
                AllocNodes    VARCHAR(4) NOT NULL,
                NCPUS         INT        NOT NULL,
                Partition     TEXT       NOT NULL,
                TotalCPU      TEXT       NOT NULL,
                "User"        TEXT       NOT NULL,
                ExitCode      TEXT       NOT NULL,
                State         TEXT       NOT NULL,
                Reservation   TEXT,
                ReservationID TEXT,
                AllocTRES     TEXT
            )
        ''')

        # Create table for storing job data
        cursor.execute('''
            CREATE TEMP TABLE jobs (
                Period          CHAR(3)    NOT NULL,
                COMPLETED       VARCHAR(9) NOT NULL,
                cluster         CHAR(3)    NOT NULL,
                Agency          VARCHAR(5) NOT NULL,
                totalJobSeconds INT        NOT NULL
            )
        ''')

        # Iterate over all entries in the dataset directory
        with os.scandir(dataset_path) as entries:
            for entry in entries:
                # Load only files with month job data
                match = re.match(r'jobs_([^\.]+)\..*', entry.name)
                if match and entry.is_file():
                    month         = match.group(1)
                    file_path     = os.path.join(dataset_path, entry.name)
                    postgres_path = context.convert_file_path(file_path)

                    # Load CSV file
                    cursor.execute(f'''
                    COPY jobs_csv
                            FROM '{postgres_path}'
                            WITH (FORMAT csv, DELIMITER '|', HEADER true);
                    ''')

                    # Copy data to final table, adding all new columns
                    cursor.execute(rf'''
                        INSERT INTO jobs (Period, COMPLETED, cluster, Agency, totalJobSeconds)
                        SELECT
                            '{month}',

                            CASE
                                WHEN State = 'COMPLETED' THEN
                                    'COMPLETED'
                                ELSE
                                    'FAILED'
                            END,

                            CASE
                                WHEN Partition LIKE '%arm%' THEN
                                    'arm'
                                WHEN Partition LIKE '%a100%' THEN
                                    'gpu'
                                ELSE
                                    'amd'
                            END,

                            CASE
                                WHEN Account LIKE 'f%'  THEN
                                    'FCT'
                                WHEN Account LIKE 'ee%' THEN
                                    'EHPC'
                                ELSE
                                    'LOCAL'
                            END,

                            CASE
                                WHEN Partition LIKE '%a100%' THEN
                                    CASE
                                        WHEN AllocTRES IS NULL OR AllocTRES = '' THEN
                                            NNodes
                                        WHEN AllocTRES ~ 'gres/gpu=\d+' THEN
                                            CAST(substring(AllocTRES FROM 'gres/gpu=(\d+)') AS INT)
                                        ELSE
                                            NNodes * 4
                                    END
                                ELSE
                                    NNodes
                            END * ElapsedRaw

                            FROM jobs_csv
                    ''')

                    # Clear CSV data table for next CSV file
                    cursor.execute('TRUNCATE TABLE jobs_csv;')

    def process_dataset(self, context: Context) -> None:
        # Group job count and hours by month, partition, account, and state
        assert isinstance(context, PostgreSQLContext)
        cursor = context.cursor

        cursor.execute('''
            SELECT Period, cluster, Agency, COMPLETED, COUNT(*), SUM(totalJobSeconds)
                FROM jobs
                GROUP BY 1, 2, 3, 4
        ''')

        aggregated_results = cursor.fetchall()

        # Use aggregated data to for computing query results
        for tag, months in self.tag_months.items():
            hours: dict[str, int] = {'arm': 0, 'amd': 0, 'gpu': 0}

            for row in aggregated_results:
                if row[0] in months:
                    row_cluster   = row[1]
                    row_agency    = row[2]
                    row_completed = row[3]
                    row_jobs      = row[4]
                    row_seconds   = row[5]

                    # Count complete and failed jobs per cluster
                    if row_completed == 'COMPLETED':
                        self.output_parameters[f'{row_cluster}CompletedJobs{tag}'] += row_jobs
                    else:
                        self.output_parameters[f'{row_cluster}FailedJobs{tag}'] += row_jobs

                    # Count jobs and hours per cluster
                    if row_agency != 'LOCAL':
                        hours[row_cluster]                                += row_seconds
                        self.output_parameters[f'{row_cluster}Jobs{tag}'] += row_jobs

                    for k, v in hours.items():
                        self.output_parameters[f'{k}usedhours{tag}'] = v / 3600

                    # Count EuroHPC jobs and hours
                    if row_agency == 'EHPC':
                        self.output_parameters[f'{row_cluster}usedhoursEuroHPC{tag}'] += \
                            row_seconds / 3600
                        self.output_parameters[f'{row_cluster}JobsEuroHPC{tag}'] += row_jobs
