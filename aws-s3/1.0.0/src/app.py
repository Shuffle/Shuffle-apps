import socket
import asyncio
import time
import random
import json
import boto3
import botocore
from botocore.config import Config

from walkoff_app_sdk.app_base import AppBase

class AWSS3(AppBase):
    __version__ = "1.0.0"
    app_name = "AWS S3"  

    def __init__(self, redis, logger, console_logger=None):
        """
        Each app should have this __init__ to set up Redis and logging.
        :param redis:
        :param logger:
        :param console_logger:
        """
        super().__init__(redis, logger, console_logger)

    def auth_s3(self, access_key, secret_key, region, endpoint_url=None):
        my_config = Config(
            region_name = region,
            signature_version = "s3v4",
            retries = {
                'max_attempts': 10,
                'mode': 'standard'
            },
        )

        resource_args = {
            "service_name": 's3',
            "config": my_config,
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key
        }

        if endpoint_url and endpoint_url != 'default':
            resource_args['endpoint_url'] = endpoint_url

        self.s3 = boto3.resource(**resource_args)

        return self.s3

    def list_buckets(self, access_key, secret_key, region, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client
        try:
            newlist = client.list_buckets()
            return newlist
        except botocore.exceptions.ClientError as e:
            return "Error: %s" % e

    def create_bucket(self, access_key, secret_key, region, bucket_name, access_type, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client
        try:
            creation = client.create_bucket(
                Bucket=bucket_name,
                ACL=access_type,
                CreateBucketConfiguration={
                    'LocationConstraint': region
                },
            )

            return creation 
        except botocore.exceptions.ClientError as e:
            return "Error: %s" % e

    def block_ip_access(self, access_key, secret_key, region, bucket_name, ip, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client

        ip_policy = {
            'Effect': 'Deny',
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::%s/*" % bucket_name,
                "arn:aws:s3:::%s" % bucket_name
            ],
            "Condition": {
                "IpAddress": {
                    "aws:SourceIp": [
                        ip,
                    ]
                }
            }
        }

        json_policy = {}
        try:
            result = client.get_bucket_policy(Bucket=bucket_name)
            try:
                policy = result["Policy"]
                print(policy)
                if ip in policy:
                    return "IP %s is already in this policy" % ip

                json_policy = json.loads(policy)
                try:
                    json_policy["Statement"].append(ip_policy)
                except KeyError:
                    json_policy["Statement"] = [ip_policy]
            except KeyError as e:
                return "Couldn't find key: %s" % e
        except botocore.exceptions.ClientError:
            # FIXME: If here, create new policy
            json_policy = {
                'Version': '2012-10-17',
                'Statement': [ip_policy]
            }

        #new_policy = json.loads(bucket_policy)
        bucket_policy = json.dumps(json_policy)
        print(bucket_policy)
        print()

        try:
            putaction = client.put_bucket_policy(Bucket=bucket_name, Policy=bucket_policy)
        except botocore.exceptions.ClientError as e:
            return "Failed setting policy: %s" % e

        print(putaction)
        return "Successfully blocked IP %s" % ip

    def bucket_request_payment(self, access_key, secret_key, region, bucket_name, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client

        try:
            return client.get_bucket_request_payment(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            return "Error: %s" % e

    def bucket_replication(self, access_key, secret_key, region, bucket_name, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client

        try:
            return client.get_bucket_replication(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            return "Error: %s" % e

    def bucket_policy_status(self, access_key, secret_key, region, bucket_name, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client

        try:
            return client.get_bucket_policy_status(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            return "Error: %s" % e

    def bucket_logging(self, access_key, secret_key, region, bucket_name, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client

        try:
            return client.get_bucket_logging(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            return "Error: %s" % e

    def upload_file_to_bucket(self, access_key, secret_key, region, bucket_name, bucket_path, file_id, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client

        found_file = self.get_file(file_id)
        print(found_file)

        s3_response = client.put_object(Bucket=bucket_name, Key=bucket_path, Body=found_file["data"])

        #s3_response = client.upload_file('LOCAL PATH', bucket_name, bucket_path)
        return s3_response

    def delete_file_from_bucket(self, access_key, secret_key, region, bucket_name, bucket_path, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client

        s3_response = client.delete_object(Bucket=bucket_name, Key=bucket_path)
        return s3_response

    def download_file_from_bucket(self, access_key, secret_key, region, bucket_name, filename, endpoint_url):
        self.s3 = self.auth_s3(access_key, secret_key, region, endpoint_url)
        client = self.s3.meta.client

        s3_response_object = client.get_object(Bucket=bucket_name, Key=filename)
        object_content = s3_response_object['Body'].read()

        filedata = {
            "data": object_content,
            "filename": filename,
        }
        ret = self.set_files(filedata)

        if isinstance(ret, list):
            if len(ret) == 1:
                return {
                    "success": True,
                    "file_id": ret[0],
                    "filename": filename,
                    "length": len(object_content),
                }

        return {
            "success": False,
            "reason": "Bad return from file upload: %s" % ret
        }

if __name__ == "__main__":
    AWSS3.run()
