#!/usr/bin/env python3
"""
S3 Bucket Configuration Script for Otto AI
Sets up proper CORS, lifecycle rules, and access policies
"""
import boto3
import json
from botocore.exceptions import ClientError
import os

def setup_s3_bucket():
    """Configure S3 bucket with proper settings for Otto AI"""
    
    # AWS credentials (from environment variables)
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_DEFAULT_REGION', 'ap-southeast-2')
    bucket_name = os.getenv('S3_BUCKET', 'otto-documents-staging')
    
    print(f"🏗️  Setting up S3 bucket: {bucket_name} in region: {aws_region}")
    
    # Initialize S3 client
    s3_client = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )
    
    try:
        # 1. Create bucket if it doesn't exist
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            print(f"✅ Bucket {bucket_name} already exists")
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                print(f"📦 Creating bucket {bucket_name}...")
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={'LocationConstraint': aws_region}
                )
                print(f"✅ Bucket {bucket_name} created successfully")
            else:
                raise e
        
        # 2. Configure CORS
        print("🌐 Setting up CORS configuration...")
        cors_configuration = {
            'CORSRules': [
                {
                    'AllowedHeaders': ['*'],
                    'AllowedMethods': ['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                    'AllowedOrigins': [
                        'http://localhost:3000',
                        'https://tv-mvp-staging.fly.dev',
                        'https://tv-mvp.fly.dev',
                        'https://otto.shunyalabs.ai'
                    ],
                    'ExposeHeaders': ['ETag'],
                    'MaxAgeSeconds': 3000
                }
            ]
        }
        
        s3_client.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_configuration
        )
        print("✅ CORS configuration applied")
        
        # 3. Configure lifecycle rules
        print("⏰ Setting up lifecycle rules...")
        lifecycle_configuration = {
            'Rules': [
                {
                    'ID': 'AudioFileLifecycle',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'audio/'},
                    'Transitions': [
                        {
                            'Days': 30,
                            'StorageClass': 'STANDARD_IA'
                        },
                        {
                            'Days': 90,
                            'StorageClass': 'GLACIER'
                        }
                    ],
                    'Expiration': {'Days': 2555}  # 7 years for compliance
                },
                {
                    'ID': 'DocumentLifecycle',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'documents/'},
                    'Transitions': [
                        {
                            'Days': 30,
                            'StorageClass': 'STANDARD_IA'
                        }
                    ]
                },
                {
                    'ID': 'TempFileCleanup',
                    'Status': 'Enabled',
                    'Filter': {'Prefix': 'temp/'},
                    'Expiration': {'Days': 1}  # Clean up temp files after 1 day
                }
            ]
        }
        
        s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration=lifecycle_configuration
        )
        print("✅ Lifecycle rules applied")
        
        # 4. Configure bucket policy for secure access
        print("🔒 Setting up bucket policy...")
        bucket_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "AllowOttoAIAccess",
                    "Effect": "Allow",
                    "Principal": {
                        "AWS": f"arn:aws:iam::{aws_access_key}:root"
                    },
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject"
                    ],
                    "Resource": f"arn:aws:s3:::{bucket_name}/*"
                },
                {
                    "Sid": "AllowPublicReadAudio",
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/audio/*",
                    "Condition": {
                        "StringEquals": {
                            "aws:Referer": [
                                "https://tv-mvp-staging.fly.dev/*",
                                "https://tv-mvp.fly.dev/*"
                            ]
                        }
                    }
                }
            ]
        }
        
        s3_client.put_bucket_policy(
            Bucket=bucket_name,
            Policy=json.dumps(bucket_policy)
        )
        print("✅ Bucket policy applied")
        
        # 5. Enable versioning
        print("📝 Enabling versioning...")
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={'Status': 'Enabled'}
        )
        print("✅ Versioning enabled")
        
        # 6. Configure server-side encryption
        print("🔐 Setting up encryption...")
        encryption_configuration = {
            'Rules': [
                {
                    'ApplyServerSideEncryptionByDefault': {
                        'SSEAlgorithm': 'AES256'
                    }
                }
            ]
        }
        
        s3_client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration=encryption_configuration
        )
        print("✅ Encryption configured")
        
        # 7. Create folder structure
        print("📁 Creating folder structure...")
        folders = [
            'audio/',
            'documents/',
            'temp/',
            'exports/',
            'backups/'
        ]
        
        for folder in folders:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=folder,
                Body=''
            )
        
        print("✅ Folder structure created")
        
        print(f"\n🎉 S3 bucket {bucket_name} configured successfully!")
        print(f"📍 Region: {aws_region}")
        print(f"🌐 CORS: Enabled for Otto AI domains")
        print(f"⏰ Lifecycle: Audio files → IA → Glacier → Delete (7 years)")
        print(f"🔒 Policy: Secure access for Otto AI services")
        print(f"📝 Versioning: Enabled")
        print(f"🔐 Encryption: AES256")
        
        return True
        
    except ClientError as e:
        print(f"❌ Error configuring S3: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = setup_s3_bucket()
    if success:
        print("\n✅ S3 setup completed successfully!")
    else:
        print("\n❌ S3 setup failed!")
        exit(1)
