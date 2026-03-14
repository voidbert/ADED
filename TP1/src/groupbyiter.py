# ABOUT --------------------------------------------------------------------------------------------
#
# GroupBy iteration level query implementation.
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

class GroupByIter(Query):
    @staticmethod
    def create_context(threads: int, **kwargs: object) -> Context:
        return SparkContext(threads, **kwargs)

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

        for tag, months in self.tag_months.items():
            hours = dict()
            jobs  = dict()

            in_months = self.data.filter(F.col("Period").isin(months))
            summary = in_months.groupby("Period", "Cluster", "Agency", "COMPLETED") \
                            .agg(F.count("*").alias("job_count"),
                                    F.sum("TotalJobSeconds").alias("total_secs")) \
                            .collect()

            for row in summary:
                if row.COMPLETED == "COMPLETED":
                    self.output_parameters[f"{row.Cluster.lower()}CompletedJobs{tag}"] = self.output_parameters.get(f"{row.Cluster.lower()}CompletedJobs{tag}", 0) + row.job_count
                else:
                    self.output_parameters[f"{row.Cluster.lower()}FailedJobs{tag}"] = self.output_parameters.get(f"{row.Cluster.lower()}FailedJobs{tag}", 0) + row.job_count

                if row.Agency != "LOCAL":
                    hours[row.Cluster] = hours.get(row.Cluster, 0) + row.total_secs
                    jobs[row.Cluster] = jobs.get(row.Cluster, 0) + row.job_count

                if row.Agency == "EHPC":
                    self.output_parameters[f"{row.Cluster.lower()}usedhoursEuroHPC{tag}"] = self.output_parameters.get(f"{row.Cluster.lower()}usedhoursEuroHPC{tag}", 0) + row.total_secs / 3600
                    self.output_parameters[f"{row.Cluster.lower()}JobsEuroHPC{tag}"] = self.output_parameters.get(f"{row.Cluster.lower()}JobsEuroHPC{tag}", 0) + row.job_count

            for key, value in hours.items():
                self.output_parameters[f"{key.lower()}usedhours{tag}"] = value / 3600
            for key, value in jobs.items():
                self.output_parameters[f"{key.lower()}Jobs{tag}"] = value