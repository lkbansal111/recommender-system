import boto3
import os
from boto3.s3.transfer import TransferConfig
from dotenv import load_dotenv

load_dotenv()



s3 = boto3.client(
    's3',
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name='eu-north-1'  # or your region
)


config = TransferConfig(multipart_threshold=100*1024*1024, max_concurrency=8)

s3.upload_file(
    Filename=r"C:\Users\lkbansal111\Downloads\archive\animelist.csv",
    Bucket='kubernetes-project-111',
    Key='animelist.csv',
    Config=config
)
