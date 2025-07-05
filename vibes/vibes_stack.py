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
            s3.NotificationKeyFilter(prefix="emails/")  # Trigger on all files in emails/ folder
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

        # Add TXT record for domain verification
        route53.TxtRecord(
            self, "DomainVerificationRecord",
            zone=hosted_zone,
            record_name="_amazonses.bhaang.com",
            values=["9jBHm71kqVtneGEMn6/m/YL1I6IjfN+7tJ8IuJrECxo="]
        )

        # Add SPF record to authorize SES to send emails from this domain
        route53.TxtRecord(
            self, "SPFRecord",
            zone=hosted_zone,
            record_name="bhaang.com",
            values=["v=spf1 include:amazonses.com ~all"]
        )

        # Add DKIM CNAME records for email authentication
        route53.CnameRecord(
            self, "DKIMRecord1",
            zone=hosted_zone,
            record_name="eq4e3eustqjzle7jgttfmszw72d5ylgc._domainkey.bhaang.com",
            domain_name="eq4e3eustqjzle7jgttfmszw72d5ylgc.dkim.amazonses.com"
        )
        
        route53.CnameRecord(
            self, "DKIMRecord2",
            zone=hosted_zone,
            record_name="k3jpjfgck6q54sbwh6ep5tbw25olcco5._domainkey.bhaang.com",
            domain_name="k3jpjfgck6q54sbwh6ep5tbw25olcco5.dkim.amazonses.com"
        )
        
        route53.CnameRecord(
            self, "DKIMRecord3",
            zone=hosted_zone,
            record_name="onogetj6inprtuyzaabbyado52asqcft._domainkey.bhaang.com",
            domain_name="onogetj6inprtuyzaabbyado52asqcft.dkim.amazonses.com"
        )

        # SES configuration for receiving emails
        ses_receipt_rule_set = ses.ReceiptRuleSet(
            self, "EmailReceiptRuleSet"
        )

        # Create the receipt rule with specific email addresses
        ses.ReceiptRule(
            self, "EmailReceiptRule",
            rule_set=ses_receipt_rule_set,
            recipients=[
                # Define specific email addresses that will receive emails
                "info@bhaang.com",
                "support@bhaang.com", 
                "bookings@bhaang.com",
                "contact@bhaang.com",
                "hello@bhaang.com",
                # Add more email addresses as needed
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
            enabled=True  # Ensure the rule is enabled
        )

        # Output the bucket name and lambda function name
        self.email_bucket_name = email_bucket.bucket_name
        self.email_processor_function_name = email_processor.function_name
        
        # Output the configured email addresses for reference
        self.configured_emails = [
            "info@bhaang.com",
            "support@bhaang.com", 
            "bookings@bhaang.com",
            "contact@bhaang.com",
            "hello@bhaang.com"
        ]