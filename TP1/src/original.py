# ABOUT --------------------------------------------------------------------------------------------
#
# Original query implementation to optimize.
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

from pyspark.sql import DataFrame
import pyspark.sql.functions as F
import os
import re

from contexts import Context, SparkContext
from query import Query

class Original(Query):
    @staticmethod
    def create_context(processes: int, **kwargs: object) -> Context:
        return SparkContext(processes, **kwargs)

    def load_dataset(self, context: Context, dataset_path: str) -> None:
        # Get Spark session from context
        assert isinstance(context, SparkContext)
        spark = context.spark

        # Iterate over all entries in the dataset directory
        year_data: DataFrame | None = None
        with os.scandir(dataset_path) as entries:
            for entry in entries:

                # Load only files with month job data
                match = re.match(r'jobs_([^\.]+)\..*', entry.name)
                if match and entry.is_file():
                    month = match.group(1)

                    # Load CSV file and add extra columns for job status and month
                    month_data = spark.read.csv(
                        os.path.join(dataset_path, entry.name),
                        sep='|', inferSchema=True, header=True
                    ).withColumn(
                        'EState', F.regexp_replace(F.col('State'), 'CANCELLED(.*)', 'CANCELLED')
                    ).withColumn(
                        'COMPLETED',
                        F.when(F.col('State') == 'COMPLETED', 'COMPLETED').otherwise('FAILED')
                    ).withColumn(
                        'Period', F.lit(month)
                    )

                    # Concatenate CSV files from all months
                    if year_data is None:
                        year_data = month_data
                    else:
                        year_data = year_data.union(month_data)

        assert isinstance(year_data, DataFrame)
        self.data = year_data

    def process_dataset(self, _: Context) -> None:
        # Add column for job cluster (ARM, AMD, or GPU) based on partition name
        self.data = self.data.withColumn(
            'cluster',
            F.when(
                F.col('Partition').contains('arm'),
                'ARM'
            ).otherwise(
                F.when(
                    F.col('Partition').contains('a100'),
                    'GPU'
                ).otherwise(
                    'AMD'
                )
            )
        )

        # Add column for job agency (FCT, EHPC, or LOCAL) based on account name
        self.data = self.data.withColumn(
            'Agency',
            F.when(
                F.col('Account').startswith('f'),
                'FCT'
            ).otherwise(
                F.when(
                    F.col('Account').startswith('ee'),
                    'EHPC'
                ).otherwise(
                    'LOCAL'
                )
            )
        )

        # Add column for number of allocated nodes, as GPU allocation may not be exclusive
        self.data = self.data.withColumn(
            'OldVNodes',
            F.when(
                F.col('Partition').contains('a100'),
                F.when(
                    F.col('AllocCPUS') % 32 == 0,
                    (F.col('AllocCPUS') / 32).cast('int')
                ).otherwise(
                    (F.col('AllocCPUS') / 32).cast('int') + 1
                )
            ).otherwise(
                F.col('NNodes') # Non-GPU node
            )
        )

        # Add column for number of allocated virtual nodes (full GPU nodes count as 4 virtual nodes)
        self.data = self.data.withColumn(
            'VNodes',
            F.when(
                F.col('Partition').contains('a100'),
                F.when(
                    F.col('AllocTRES').isNull(),
                    F.col('NNodes')
                ).otherwise(
                    F.when(
                        # Use the specified number of GPUs the user allocated
                        F.col('AllocTRES').rlike(r'gres/gpu=(\d+)'),
                        F.regexp_extract(F.col('AllocTRES'), r'gres/gpu=(\d+)', 1)
                    ).otherwise(
                        # User allocated full nodes. Count number of GPUs
                        F.col('NNodes') * 4
                    )
                )
             ).otherwise(
                F.col('NNodes') # Non-GPU node
            )
        )

        # Add column for total job seconds
        self.data = self.data.withColumn('totalJobSeconds', F.col('ElapsedRaw') * F.col('VNodes'))

        # Run query
        for tag, months in self.tag_months.items():
            # Count complete and failed jobs per cluster
            completed = self.data.filter(F.col('Period').isin(months)) \
                                 .groupby('COMPLETED', 'cluster')      \
                                 .count()                              \
                                 .collect()

            for row in completed:
                cluster = row.cluster.lower()
                if row.COMPLETED == 'COMPLETED':
                    self.output_parameters[f'{cluster}CompletedJobs{tag}'] = row.asDict()['count']
                else:
                    self.output_parameters[f'{cluster}FailedJobs{tag}'] = row.asDict()['count']

            # Count used hours per cluster
            hours: dict[str, int] = {}
            for cluster in ['ARM', 'AMD', 'GPU']:
                hours[cluster] = self.data.filter(F.col('Agency') != 'LOCAL')   \
                                          .filter(F.col('Period').isin(months)) \
                                          .groupby('cluster')                   \
                                          .sum('totalJobSeconds')               \
                                          .filter(F.col('cluster') == cluster)  \
                                          .collect()[0]                         \
                                          .asDict()['sum(totalJobSeconds)']

            # Count jobs per cluster
            job_query_result = self.data.filter(F.col('Agency') != 'LOCAL')   \
                                        .filter(F.col('Period').isin(months)) \
                                        .groupby('cluster')                   \
                                        .count()                              \
                                        .collect()

            jobs: dict[str, int] = {}
            for row in job_query_result:
                row_dict = row.asDict()
                jobs[row_dict['cluster']] = row_dict['count']

            # Fill output parameters from hour and job data
            for k, v in hours.items():
                self.output_parameters[f'{k.lower()}usedhours{tag}'] = v / 3600

            for k, v in jobs.items():
                self.output_parameters[f'{k.lower()}Jobs{tag}'] = v

            # Count EuroHPC jobs
            ehpc_job_query_result = self.data.filter(F.col('Period').isin(months)) \
                                            .groupby(['Agency', 'cluster'])       \
                                            .count()                              \
                                            .orderBy('Agency')                    \
                                            .filter(F.col('Agency') == 'EHPC')    \
                                            .collect()

            for row in ehpc_job_query_result:
                self.output_parameters[f'{row.cluster.lower()}JobsEuroHPC{tag}'] = \
                    row.asDict()['count']

            # Count EuroHPC hours
            ehpc_hour_query_result = self.data.filter(F.col('Agency') == 'EHPC')    \
                                              .filter(F.col('Period').isin(months)) \
                                              .groupby(['Agency', 'cluster'])       \
                                              .sum()                                \
                                              .collect()

            for row in ehpc_hour_query_result:
                self.output_parameters[f'{row.cluster.lower()}usedhoursEuroHPC{tag}'] = \
                    row.asDict()['sum(totalJobSeconds)'] / 3600
