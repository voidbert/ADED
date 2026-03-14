# ABOUT --------------------------------------------------------------------------------------------
#
# Query implementation based on PostgreSQL.
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

import psycopg2
import os

from contexts import Context, PostgreSQLContext
from query import Query

class PostgreSQL(Query):
    @staticmethod
    def create_context(threads: int, **kwargs: object) -> Context:
        return PostgreSQLContext(threads, **kwargs)

    def load_dataset(self, context: Context, dataset_path: str) -> None:
        csv_files = [
            os.path.join(dataset_path, entry.name)
            for entry in os.scandir(dataset_path)
            if entry.name.startswith('job') and entry.is_file()
        ]

        assert isinstance(context, PostgreSQLContext)
        connection = context.connection

        with connection.cursor() as cur:
            cur.execute('TRUNCATE TABLE jobs;')

            cur.execute("""
                CREATE TEMP TABLE temp_jobs_raw (
                    JobID TEXT, JobIDRaw TEXT, ElapsedRaw TEXT, Account TEXT,
                    AllocCPUS TEXT, CPUTimeRAW TEXT, NNodes INT, AllocNodes TEXT,
                    NCPUS TEXT, Partition TEXT, TotalCPU TEXT, "User" TEXT,
                    ExitCode TEXT, State TEXT, Reservation TEXT,
                    ReservationId TEXT, AllocTRES TEXT
                );
            """)
    
            for f in csv_files:
                period = "_".join(f.split("_")[1:]).split(".")[0]
                with open(f, 'r') as csvfile:
                    cur.execute('TRUNCATE TABLE temp_jobs_raw;')
                    cur.copy_expert(
                        "COPY temp_jobs_raw FROM STDIN WITH (FORMAT csv, DELIMITER '|', HEADER true);",
                        csvfile
                    )

                    cur.execute(r"""
                        INSERT INTO jobs (
                            "JobID", "State", "Account", "Partition",
                            "NNodes", "AllocTRES", "ElapsedRaw", "Period", "totalJobSeconds"
                        )
                        SELECT
                            JobID,
                            CASE WHEN State = 'COMPLETED' THEN 'COMPLETED' ELSE 'FAILED' END,
                            CASE
                                WHEN Account LIKE 'f%%' THEN 'FCT'
                                WHEN Account LIKE 'ee%%' THEN 'EHPC'
                                ELSE 'LOCAL'
                            END,
                            CASE
                                WHEN Partition LIKE '%%arm%%' THEN 'ARM'
                                WHEN Partition LIKE '%%a100%%' THEN 'GPU'
                                ELSE 'AMD'
                            END,
                            NNodes, AllocTRES,
                            CAST(NULLIF(ElapsedRaw, '') AS BIGINT),
                            %s,
                            (CASE
                                WHEN Partition LIKE '%%a100%%' THEN
                                    CASE
                                        WHEN AllocTRES IS NULL OR AllocTRES = '' THEN NNodes
                                        WHEN AllocTRES ~ 'gres/gpu=\d+' THEN
                                            CAST(substring(AllocTRES from 'gres/gpu=(\d+)') AS INT)
                                        ELSE NNodes * 4
                                    END
                                ELSE NNodes
                            END) * CAST(NULLIF(ElapsedRaw, '') AS BIGINT)
                        FROM temp_jobs_raw
                        WHERE ElapsedRaw IS NOT NULL AND ElapsedRaw != '';
                    """, (period,))

            connection.commit()

    def process_dataset(self, context: Context) -> None:
        assert isinstance(context, PostgreSQLContext)
        connection = context.connection

        with connection.cursor() as cur:
            cur.execute("""
                SELECT 
                    "Period" as Period, 
                    "Partition" as cluster, 
                    "Account" as agency, 
                    "State" as completed,
                    COUNT(*) as job_count,
                    SUM("totalJobSeconds") as total_secs
                FROM jobs
                GROUP BY 1, 2, 3, 4
            """)
            results = cur.fetchall()

            for tag, months in self.tag_months.items():
                hours: dict[str, int] = {}
                jobs: dict[str, int]  = {}

                for row in results:
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