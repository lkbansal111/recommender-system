import os
import pandas as pd
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from src.logger import get_logger
from src.custom_exception import CustomException
from config.paths_config import *
from utils.common_functions import read_yaml

from dotenv import load_dotenv

load_dotenv()

logger = get_logger(__name__)

class DataIngestion:
    def __init__(self, config):
        self.config = config["data_ingestion"]
        self.bucket_name = self.config["bucket_name"]
        self.file_names = self.config["bucket_file_names"]

        os.makedirs(RAW_DIR, exist_ok=True)
        logger.info("Data Ingestion Started....")

    def download_csv_from_s3(self):
        try:
            s3_client = boto3.client(
                's3',
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
                region_name='eu-north-1'  # or your region
                )

            for file_name in self.file_names:
                file_path = os.path.join(RAW_DIR, file_name)

                try:
                    s3_client.download_file(self.bucket_name, file_name, file_path)
                except ClientError as e:
                    if e.response['Error']['Code'] == "404":
                        logger.error(f"File {file_name} not found in bucket {self.bucket_name}")
                        raise FileNotFoundError(f"{file_name} not found in S3 bucket.")
                    else:
                        raise

                if file_name == "animelist.csv":
                    data = pd.read_csv(file_path, nrows=5000000)
                    data.to_csv(file_path, index=False)
                    logger.info("Large file detected. Only downloading 5M rows.")
                else:
                    logger.info(f"Downloading smaller file: {file_name}")

        except (NoCredentialsError, ClientError) as e:
            logger.error("AWS S3 client error")
            raise CustomException("Failed to access or download from S3", e)
        except Exception as e:
            logger.error(f"Error while downloading data from S3 {e}")
            raise CustomException("Failed to download data", e)

    def run(self):
        try:
            logger.info("Starting Data Ingestion Process....")
            self.download_csv_from_s3()
            logger.info("Data Ingestion Completed...")
        except CustomException as ce:
            logger.error(f"CustomException: {str(ce)}")
        finally:
            logger.info("Data Ingestion DONE...")

if __name__ == "__main__":
    data_ingestion = DataIngestion(read_yaml(CONFIG_PATH))
    data_ingestion.run()
