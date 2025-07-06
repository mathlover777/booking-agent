import os
from dotenv import load_dotenv
from aws_cdk import (
    Duration,
    Stack,
    aws_s3 as s3,
    aws_ses as ses,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3_notifications as s3n,
    aws_ses_actions as ses_actions,
    CfnOutput,
)
from constructs import Construct

# Load environment variables
load_dotenv('.env.base')


class EmailProcessorStack(Stack):
    """
    Email processor stack containing stage-specific resources:
    - Lambda functions
    - IAM roles
    - ReceiptRules with stage-specific email addresses
    - S3 triggers
    """

    def __init__(self, scope: Construct, construct_id: str, stage: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.stage = stage

        # Import the shared S3 bucket from infrastructure stack
        # Note: This requires the infrastructure stack to be deployed first
        email_bucket = s3.Bucket.from_bucket_name(
            self, "ImportedEmailBucket",
            bucket_name=os.getenv('EMAIL_BUCKET_NAME')
        )

        # Import the shared ReceiptRuleSet from infrastructure stack
        ses_receipt_rule_set = ses.ReceiptRuleSet.from_receipt_rule_set_name(
            self, "ImportedReceiptRuleSet",
            receipt_rule_set_name=os.getenv('RECEIPT_RULE_SET_NAME')  # Use environment variable
        )

        # Central IAM role for all lambdas in this stage
        lambda_role = iam.Role(
            self, f"VibesLambdaRole{stage.title()}",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Add S3 read permissions to the lambda role
        email_bucket.grant_read(lambda_role)

        # Lambda function for email processing
        email_processor = lambda_.Function(
            self, f"EmailProcessor{stage.title()}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="email_processor.lambda_handler",
            code=lambda_.Code.from_asset("src"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "LOG_LEVEL": "INFO",
                "STAGE": stage
            }
        )

        # Add S3 trigger to lambda with stage-specific prefix
        email_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(email_processor),
            s3.NotificationKeyFilter(prefix=f"{stage}/emails/")  # Stage-specific prefix
        )

        # SES ReceiptRule with stage-specific email address
        booking_prefix = os.getenv('BOOKING_EMAIL_PREFIX')
        recipient_email = f"{booking_prefix}{stage}@{os.getenv('DOMAIN_NAME')}" if stage != "prod" else f"{booking_prefix}@{os.getenv('DOMAIN_NAME')}"
        
        ses.ReceiptRule(
            self, f"EmailReceiptRule{stage.title()}",
            rule_set=ses_receipt_rule_set,
            recipients=[recipient_email],
            actions=[
                ses_actions.AddHeader(
                    name="X-SES-RECEIPT-RULE",
                    value=f"email-processor-{stage}"
                ),
                ses_actions.S3(
                    bucket=email_bucket,
                    object_key_prefix=f"{stage}/emails/",  # Stage-specific prefix
                    topic=None
                )
            ],
            scan_enabled=True,
            tls_policy=ses.TlsPolicy.OPTIONAL,
            enabled=True 
        )

        # Outputs
        CfnOutput(self, f"EmailProcessorFunctionName{stage.title()}", 
                 value=email_processor.function_name)
        CfnOutput(self, f"StageEmailAddress{stage.title()}", 
                 value=recipient_email)
        CfnOutput(self, f"StageS3Prefix{stage.title()}", 
                 value=f"{stage}/emails/") 