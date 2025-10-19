"""
AWS Lambda Handler - Reminder Scheduler

Purpose: Check and send pending reminders (triggered by EventBridge)

EventBridge Rule: Runs every 5 minutes
"""

import json
import boto3
import os
from datetime import datetime
import sys

# Add parent directory to path (for local testing)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Use environment variables for config
DYNAMODB_TABLE_REMINDERS = os.environ.get('DYNAMODB_TABLE_REMINDERS', 'postmate-reminders-prod')
DYNAMODB_TABLE_DOCUMENTS = os.environ.get('DYNAMODB_TABLE_DOCUMENTS', 'postmate-documents-prod')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Initialize clients
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
reminders_table = dynamodb.Table(DYNAMODB_TABLE_REMINDERS)
documents_table = dynamodb.Table(DYNAMODB_TABLE_DOCUMENTS)


def lambda_handler(event, context):
    """
    Lambda handler for reminder scheduler

    Triggered by: EventBridge rule (every 5 minutes)
    """

    print(f"Checking pending reminders at {datetime.utcnow().isoformat()}")

    try:
        # Get current time
        cutoff_time = datetime.utcnow().isoformat()

        # Scan for pending reminders that are due
        response = reminders_table.scan(
            FilterExpression='reminder_date <= :cutoff AND #status = :pending',
            ExpressionAttributeValues={
                ':cutoff': cutoff_time,
                ':pending': 'pending'
            },
            ExpressionAttributeNames={
                '#status': 'status'
            }
        )

        reminders = response.get('Items', [])

        print(f"Found {len(reminders)} pending reminders")

        # Process each reminder
        for reminder in reminders:
            try:
                send_reminder(reminder)

                # Update reminder status
                reminders_table.update_item(
                    Key={'reminder_id': reminder['reminder_id']},
                    UpdateExpression='SET #status = :sent, sent_at = :now',
                    ExpressionAttributeValues={
                        ':sent': 'sent',
                        ':now': datetime.utcnow().isoformat()
                    },
                    ExpressionAttributeNames={
                        '#status': 'status'
                    }
                )

                print(f"Reminder sent: {reminder['reminder_id']}")

            except Exception as e:
                print(f"Error sending reminder {reminder['reminder_id']}: {e}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(reminders)} reminders',
                'count': len(reminders)
            })
        }

    except Exception as e:
        print(f"Error in reminder scheduler: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }


def send_reminder(reminder):
    """
    Send reminder notification

    TODO: Implement actual notification via SES, SNS, or SendGrid
    """

    # Get document info
    try:
        doc_response = documents_table.get_item(
            Key={'document_id': reminder['document_id']}
        )
        document = doc_response.get('Item', {})
    except:
        document = {}

    # Build notification message
    message = f"""
    Reminder: {reminder['title']}

    {reminder.get('description', '')}

    Document ID: {reminder['document_id']}
    Uploaded: {document.get('uploaded_at', 'Unknown')}

    This is an automated reminder from PostMate.
    """

    # TODO: Send via SES/SNS
    print(f"Would send reminder: {message}")

    # For demo, just log
    return True
