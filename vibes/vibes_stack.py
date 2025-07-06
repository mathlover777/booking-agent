from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ses as ses,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_logs as logs,
    aws_s3_notifications as s3n,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_ses_actions as ses_actions,
    CfnOutput,
)
from constructs import Construct


class VibesStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create new S3 bucket for storing emails
        email_bucket = s3.Bucket(
            self, "EmailBucket",
            bucket_name="booking-agent-vibes2",
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True
        )

        # Import existing hosted zone for bhaang.com
        # Note: This requires the domain to exist in Route53
        hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone",
            domain_name="bhaang.com"
        )

        # Central IAM role for all lambdas in this stack
        lambda_role = iam.Role(
            self, "VibesLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Add S3 read permissions to the lambda role
        email_bucket.grant_read(lambda_role)

        # Lambda function for email processing
        email_processor = lambda_.Function(
            self, "EmailProcessor",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="email_processor.lambda_handler",
            code=lambda_.Code.from_asset("src"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "LOG_LEVEL": "INFO"
            }
        )

        # Add S3 trigger to lambda
        email_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(email_processor),
            s3.NotificationKeyFilter(prefix="emails/")  # Only trigger on .eml files
        )

        # SES Domain configuration for bhaang.com with automatic DNS setup
        ses_domain = ses.EmailIdentity(
            self, "SESDomain",
            identity=ses.Identity.domain("bhaang.com")
        )
        
        # Add MX record to point email traffic to SES
        # Note: The correct endpoint depends on your SES region
        # For us-east-1: inbound-smtp.us-east-1.amazonaws.com
        # For us-west-2: inbound-smtp.us-west-2.amazonaws.com
        # For eu-west-1: inbound-smtp.eu-west-1.amazonaws.com
        # etc.
        route53.MxRecord(
            self, "SESMxRecord",
            zone=hosted_zone,
            record_name="bhaang.com",
            values=[
                route53.MxRecordValue(
                    priority=10,
                    host_name="inbound-smtp.ap-south-1.amazonaws.com"
                )
            ]
        )

        # Note: Domain verification TXT record is created separately after deployment using setup_dkim.py
        # This is because the verification token is not immediately available during CDK deployment

        # Add SPF record to authorize SES to send emails from this domain
        route53.TxtRecord(
            self, "SPFRecord",
            zone=hosted_zone,
            record_name="bhaang.com",
            values=["v=spf1 include:amazonses.com ~all"]
        )

        # Note: DKIM records are created separately after deployment using setup_dkim.py
        # This is because DKIM tokens are not immediately available during CDK deployment

        # SES configuration for receiving emails
        ses_receipt_rule_set = ses.ReceiptRuleSet(
            self, "EmailReceiptRuleSet",
        )
        ses_receipt_rule_set.node.default_child.set_as_active_rule_set = True
        ses.ReceiptRule(
            self, "EmailReceiptRule",
            rule_set=ses_receipt_rule_set,
            recipients=[
                "book@bhaang.com"
            ],
            actions=[
                ses_actions.AddHeader(
                    name="X-SES-RECEIPT-RULE",
                    value="email-processor"
                ),
                ses_actions.S3(
                    bucket=email_bucket,
                    object_key_prefix="emails/",
                    topic=None
                )
            ],
            scan_enabled=True,
            tls_policy=ses.TlsPolicy.OPTIONAL,
            enabled=True 
        )

        # Output the bucket name and lambda function name
        self.email_bucket_name = email_bucket.bucket_name
        self.email_processor_function_name = email_processor.function_name
        
        # Add outputs for debugging
        CfnOutput(self, "EmailBucketName", value=email_bucket.bucket_name)
        CfnOutput(self, "EmailProcessorFunctionName", value=email_processor.function_name)
        CfnOutput(self, "SESDomainName", value="bhaang.com")
        CfnOutput(self, "ReceiptRuleSetName", value=ses_receipt_rule_set.receipt_rule_set_name)