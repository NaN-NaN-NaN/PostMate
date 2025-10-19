"""
Create DynamoDB tables for local development

Usage:
    python -m app.scripts.create_tables_local
"""

import boto3
from botocore.exceptions import ClientError
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.config import settings


def create_tables():
    """Create all required DynamoDB tables"""

    print("Creating DynamoDB tables...")
    print(f"Endpoint: {settings.dynamodb_endpoint}")
    print(f"Region: {settings.AWS_REGION}")

    dynamodb = boto3.client(
        'dynamodb',
        endpoint_url=settings.dynamodb_endpoint,
        region_name=settings.AWS_REGION,
        aws_access_key_id='local',
        aws_secret_access_key='local'
    )

    tables = [
        {
            'name': settings.DYNAMODB_TABLE_DOCUMENTS,
            'key_schema': [
                {'AttributeName': 'document_id', 'KeyType': 'HASH'}
            ],
            'attribute_definitions': [
                {'AttributeName': 'document_id', 'AttributeType': 'S'}
            ]
        },
        {
            'name': settings.DYNAMODB_TABLE_ANALYSES,
            'key_schema': [
                {'AttributeName': 'analysis_id', 'KeyType': 'HASH'}
            ],
            'attribute_definitions': [
                {'AttributeName': 'analysis_id', 'AttributeType': 'S'}
            ]
        },
        {
            'name': settings.DYNAMODB_TABLE_CHATS,
            'key_schema': [
                {'AttributeName': 'message_id', 'KeyType': 'HASH'}
            ],
            'attribute_definitions': [
                {'AttributeName': 'message_id', 'AttributeType': 'S'}
            ]
        },
        {
            'name': settings.DYNAMODB_TABLE_REMINDERS,
            'key_schema': [
                {'AttributeName': 'reminder_id', 'KeyType': 'HASH'}
            ],
            'attribute_definitions': [
                {'AttributeName': 'reminder_id', 'AttributeType': 'S'}
            ]
        }
    ]

    for table_config in tables:
        try:
            print(f"\nCreating table: {table_config['name']}")

            dynamodb.create_table(
                TableName=table_config['name'],
                KeySchema=table_config['key_schema'],
                AttributeDefinitions=table_config['attribute_definitions'],
                BillingMode='PAY_PER_REQUEST'
            )

            print(f"✓ Table created: {table_config['name']}")

        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceInUseException':
                print(f"⚠ Table already exists: {table_config['name']}")
            else:
                print(f"✗ Error creating table {table_config['name']}: {e}")
                raise

    print("\n✓ All tables created successfully!")


if __name__ == "__main__":
    create_tables()
