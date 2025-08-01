import os
from dotenv import load_dotenv
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    aws_s3 as s3,
    aws_ses as ses,
    aws_ses_actions as ses_actions,
    aws_s3_notifications as s3n,
    aws_route53 as route53,
    CfnOutput,
    aws_iam as iam,
    aws_lambda as lambda_,
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
    - Lambda Layers (shared dependencies and auth)
    - EmailRouter Lambda (routes emails to stage-specific folders)
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

        # Create Lambda Layer with common dependencies
        self.common_layer = lambda_.LayerVersion(
            self, "VibesCommonLayer",
            layer_version_name="vibes-common-dependencies",
            description="Common dependencies for Vibes Lambda functions",
            code=lambda_.Code.from_asset("lambda-layer/common"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Create Lambda Layer with auth dependencies
        self.auth_layer = lambda_.LayerVersion(
            self, "VibesAuthLayer",
            layer_version_name="vibes-auth-dependencies",
            description="Authentication dependencies for Vibes Lambda functions",
            code=lambda_.Code.from_asset("lambda-layer/auth"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            removal_policy=RemovalPolicy.RETAIN,
        )

        # Create IAM role for EmailRouter Lambda
        email_router_role = iam.Role(
            self, "EmailRouterRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )

        # Add S3 permissions to the EmailRouter role
        self.email_bucket.grant_read(email_router_role)
        self.email_bucket.grant_write(email_router_role)

        # Add SQS permissions to the EmailRouter role (for all SQS queues)
        email_router_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sqs:SendMessage",
                    "sqs:GetQueueUrl"
                ],
                resources=[
                    f"arn:aws:sqs:*:{self.account}:email-processor-queue-*"
                ]
            )
        )

        # Create EmailRouter Lambda function
        email_router = lambda_.Function(
            self, "EmailRouter",
            function_name="EmailRouter",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="email_router.lambda_handler",
            code=lambda_.Code.from_asset("src"),
            role=email_router_role,
            timeout=Duration.seconds(60),
            memory_size=256,
            layers=[self.common_layer],
            environment={
                "LOG_LEVEL": "INFO",
                "DOMAIN_NAME": os.getenv('DOMAIN_NAME'),
                "EMAIL_BUCKET_NAME": self.email_bucket.bucket_name
            }
        )

        # Add S3 trigger to EmailRouter for incoming emails
        self.email_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(email_router),
            s3.NotificationKeyFilter(prefix="incoming/")
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

        # SES ReceiptRule for all emails to the domain - stores in incoming/ prefix
        ses.ReceiptRule(
            self, "EmailReceiptRule",
            rule_set=self.ses_receipt_rule_set,
            recipients=[os.getenv('DOMAIN_NAME')],  # All emails to @DOMAIN_NAME
            actions=[
                ses_actions.AddHeader(
                    name="X-SES-RECEIPT-RULE",
                    value="email-router"
                ),
                ses_actions.S3(
                    bucket=self.email_bucket,
                    object_key_prefix="incoming/",  # Neutral prefix for routing
                    topic=None
                )
            ],
            scan_enabled=True,
            tls_policy=ses.TlsPolicy.OPTIONAL,
            enabled=True 
        )

        # Outputs
        CfnOutput(self, "EmailBucketName", value=self.email_bucket.bucket_name)
        CfnOutput(self, "SESDomainName", value=os.getenv('DOMAIN_NAME'))
        CfnOutput(self, "ReceiptRuleSetName", value=self.ses_receipt_rule_set.receipt_rule_set_name)
        CfnOutput(self, "HostedZoneId", value=hosted_zone.hosted_zone_id)
        CfnOutput(self, "CommonLayerArn", value=self.common_layer.layer_version_arn, export_name="VibesCommonStackCommonLayerArn")
        CfnOutput(self, "AuthLayerArn", value=self.auth_layer.layer_version_arn, export_name="VibesCommonStackAuthLayerArn")
        CfnOutput(self, "EmailRouterFunctionName", value=email_router.function_name) 