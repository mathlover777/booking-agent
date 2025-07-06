import os
from dotenv import load_dotenv
from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ses as ses,
    aws_route53 as route53,
    CfnOutput,
    aws_iam as iam,
)
from constructs import Construct

# Load environment variables - only .env.base for common resources
load_dotenv('.env.base')


class CommonStack(Stack):
    """
    Common stack containing stage-independent resources:
    - SES Domain Identity
    - ReceiptRuleSet
    - S3 Bucket
    - Route53 records
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 bucket for storing emails (shared across stages)
        self.email_bucket = s3.Bucket(
            self, "EmailBucket",
            bucket_name=os.getenv('EMAIL_BUCKET_NAME'),
            removal_policy=RemovalPolicy.RETAIN,
            auto_delete_objects=False,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True
        )

        # Allow SES to write to the bucket
        self.email_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                actions=["s3:PutObject"],
                resources=[f"{self.email_bucket.bucket_arn}/*"],
                principals=[iam.ServicePrincipal("ses.amazonaws.com")],
                conditions={
                    "StringEquals": {
                        "aws:Referer": os.getenv("CDK_DEFAULT_ACCOUNT")
                    }
                }
            )
        )

        # Import existing hosted zone for bhaang.com
        hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone",
            domain_name=os.getenv('DOMAIN_NAME')
        )

        # SES Domain configuration for bhaang.com
        self.ses_domain = ses.EmailIdentity(
            self, "SESDomain",
            identity=ses.Identity.domain(os.getenv('DOMAIN_NAME'))
        )
        
        # Add MX record to point email traffic to SES
        route53.MxRecord(
            self, "SESMxRecord",
            zone=hosted_zone,
            record_name=os.getenv('DOMAIN_NAME'),
            values=[
                route53.MxRecordValue(
                    priority=int(os.getenv('SES_MX_PRIORITY', '10')),
                    host_name=os.getenv('SES_MX_HOST')
                )
            ]
        )

        # Add SPF record to authorize SES to send emails from this domain
        route53.TxtRecord(
            self, "SPFRecord",
            zone=hosted_zone,
            record_name=os.getenv('DOMAIN_NAME'),
            values=[os.getenv('SES_SPF_RECORD')]
        )

        # SES ReceiptRuleSet (region-wide, shared across stages)
        self.ses_receipt_rule_set = ses.ReceiptRuleSet(
            self, "EmailReceiptRuleSet",
            receipt_rule_set_name=os.getenv('RECEIPT_RULE_SET_NAME')
        )

        # Outputs
        CfnOutput(self, "EmailBucketName", value=self.email_bucket.bucket_name)
        CfnOutput(self, "SESDomainName", value=os.getenv('DOMAIN_NAME'))
        CfnOutput(self, "ReceiptRuleSetName", value=self.ses_receipt_rule_set.receipt_rule_set_name)
        CfnOutput(self, "HostedZoneId", value=hosted_zone.hosted_zone_id) 