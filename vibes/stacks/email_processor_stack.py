import os
from dotenv import load_dotenv
from aws_cdk import (
    Duration,
    Stack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ses as ses,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_s3_notifications as s3n,
    aws_ses_actions as ses_actions,
    aws_apigateway as apigateway,
    aws_dynamodb as dynamodb,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_certificatemanager as acm,
    CfnOutput,
    Fn,
)
from constructs import Construct

# Load base environment variables
load_dotenv('.env.base')


class EmailProcessorStack(Stack):
    """
    Email processor stack containing stage-specific resources:
    - Lambda functions (email processor, user email API, authorizer)
    - IAM roles
    - ReceiptRules with stage-specific email addresses
    - S3 triggers
    - API Gateway with Lambda authorizer
    """

    def __init__(self, scope: Construct, construct_id: str, stage: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        self.stage = stage
        
        # Load stage-specific environment variables
        load_dotenv(f'.env.{stage}')

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

        # Import the shared Lambda Layers from common stack using cross-stack reference
        # Get the layer ARNs from the common stack's outputs
        common_layer_arn = Fn.import_value("VibesCommonStackCommonLayerArn")
        auth_layer_arn = Fn.import_value("VibesCommonStackAuthLayerArn")
        
        common_layer = lambda_.LayerVersion.from_layer_version_arn(
            self, "ImportedCommonLayer",
            layer_version_arn=common_layer_arn
        )
        
        auth_layer = lambda_.LayerVersion.from_layer_version_arn(
            self, "ImportedAuthLayer",
            layer_version_arn=auth_layer_arn
        )

        # Create DynamoDB table for user email mappings (stage-specific)
        user_emails_table = dynamodb.Table(
            self, f"UserEmailsTable{stage.title()}",
            table_name=f"vibes-user-emails-{stage}",
            partition_key=dynamodb.Attribute(
                name="pk",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="sk",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.RETAIN,
            point_in_time_recovery=True,
        )

        # Add GSI for assist_local lookups
        user_emails_table.add_global_secondary_index(
            index_name="assist_local-index",
            partition_key=dynamodb.Attribute(
                name="assist_local",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
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

        # Add DynamoDB permissions to the lambda role
        user_emails_table.grant_read_write_data(lambda_role)

        # Add Secrets Manager permissions for Clerk secret key
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue"
                ],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:{stage}/vibecal*"
                ]
            )
        )

        # Add SES permissions for sending emails
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ses:SendRawEmail",
                    "ses:SendEmail"
                ],
                resources=[
                    f"arn:aws:ses:{self.region}:{self.account}:identity/*"
                ]
            )
        )



        # Lambda function for email processing
        email_processor = lambda_.Function(
            self, f"EmailProcessor{stage.title()}",
            function_name=f"EmailProcessor-{stage}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="email_processor.lambda_handler",
            code=lambda_.Code.from_asset("src"),
            role=lambda_role,
            timeout=Duration.seconds(900),
            memory_size=256,
            layers=[common_layer],
            environment={
                "LOG_LEVEL": "INFO",
                "STAGE": stage,
                "BOOKING_EMAIL": os.getenv('BOOKING_EMAIL'),
                "USER_EMAILS_TABLE_NAME": user_emails_table.table_name
            }
        )

        # Lambda function for user email API
        user_email_api = lambda_.Function(
            self, f"UserEmailApi{stage.title()}",
            function_name=f"UserEmailApi-{stage}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="apis.user_email_api.lambda_handler",
            code=lambda_.Code.from_asset("src"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            layers=[common_layer],
            environment={
                "LOG_LEVEL": "INFO",
                "STAGE": stage,
                "USER_EMAILS_TABLE_NAME": user_emails_table.table_name
            }
        )

        # Lambda function for JWT authorizer
        jwt_authorizer = lambda_.Function(
            self, f"JwtAuthorizer{stage.title()}",
            function_name=f"JwtAuthorizer-{stage}",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="apis.jwt_authorizer.lambda_handler",
            code=lambda_.Code.from_asset("src"),
            role=lambda_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            layers=[auth_layer],
            environment={
                "LOG_LEVEL": "INFO",
                "STAGE": stage,
                "JWKS_PUBLIC_KEY": os.getenv('JWKS_PUBLIC_KEY')
            }
        )

        # Add S3 trigger to lambda with stage-specific prefix
        email_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(email_processor),
            s3.NotificationKeyFilter(prefix=f"{stage}/emails/")  # Stage-specific prefix
        )

        # SES ReceiptRule for all emails to the domain
        # This captures all emails to @DOMAIN_NAME, then Lambda determines the user
        ses.ReceiptRule(
            self, f"EmailReceiptRule{stage.title()}",
            rule_set=ses_receipt_rule_set,
            recipients=[os.getenv('DOMAIN_NAME')],  # All emails to @DOMAIN_NAME
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

        # Import SSL certificate
        certificate = acm.Certificate.from_certificate_arn(
            self, f"ApiCertificate{stage.title()}",
            certificate_arn=os.getenv('CERTIFICATE')
        )

        # Create custom domain name
        custom_domain_name = f"{os.getenv('BACKEND_SUBDOMAIN')}-{stage}.{os.getenv('DOMAIN_NAME')}"
        
        # Create API Gateway
        api = apigateway.RestApi(
            self, f"VibesApi{stage.title()}",
            rest_api_name=f"vibes-api-{stage}",
            description=f"Vibes API for {stage} environment",
            endpoint_types=[apigateway.EndpointType.REGIONAL],
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["*"]
            )
        )

        # Create custom domain for API Gateway
        custom_domain = apigateway.DomainName(
            self, f"ApiCustomDomain{stage.title()}",
            domain_name=custom_domain_name,
            certificate=certificate,
            endpoint_type=apigateway.EndpointType.REGIONAL,
            security_policy=apigateway.SecurityPolicy.TLS_1_2
        )

        # Create base path mapping
        apigateway.BasePathMapping(
            self, f"ApiBasePathMapping{stage.title()}",
            domain_name=custom_domain,
            rest_api=api,
            base_path=None  # Root path mapping
        )

        # Import the hosted zone for Route53
        hosted_zone = route53.HostedZone.from_lookup(
            self, f"HostedZone{stage.title()}",
            domain_name=os.getenv('DOMAIN_NAME')
        )

        # Create Route53 A record pointing to the custom domain
        route53.ARecord(
            self, f"ApiARecord{stage.title()}",
            zone=hosted_zone,
            record_name=f"{os.getenv('BACKEND_SUBDOMAIN')}-{stage}",
            target=route53.RecordTarget.from_alias(
                targets.ApiGatewayDomain(custom_domain)
            )
        )

        # Create Lambda authorizer
        authorizer = apigateway.TokenAuthorizer(
            self, f"JwtTokenAuthorizer{stage.title()}",
            handler=jwt_authorizer,
            identity_source="method.request.header.Authorization"
        )

        # Create user resource and endpoints
        user_resource = api.root.add_resource("user")
        email_resource = user_resource.add_resource("email")

        # GET /user/email - Get user's concierge email
        email_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(user_email_api),
            authorizer=authorizer,
            authorization_type=apigateway.AuthorizationType.CUSTOM
        )

        # PUT /user/email - Update user's concierge email
        email_resource.add_method(
            "PUT",
            apigateway.LambdaIntegration(user_email_api),
            authorizer=authorizer,
            authorization_type=apigateway.AuthorizationType.CUSTOM
        )

        # POST /user/email - Check email availability
        email_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(user_email_api),
            authorizer=authorizer,
            authorization_type=apigateway.AuthorizationType.CUSTOM
        )

        # Grant API Gateway permission to invoke JWT authorizer Lambda
        jwt_authorizer.grant_invoke(iam.ServicePrincipal("apigateway.amazonaws.com"))

        # Outputs
        CfnOutput(self, f"EmailProcessorFunctionName{stage.title()}", 
                 value=email_processor.function_name)
        CfnOutput(self, f"UserEmailApiFunctionName{stage.title()}", 
                 value=user_email_api.function_name)
        CfnOutput(self, f"JwtAuthorizerFunctionName{stage.title()}", 
                 value=jwt_authorizer.function_name)
        CfnOutput(self, f"StageEmailAddress{stage.title()}", 
                 value=os.getenv('DOMAIN_NAME'))
        CfnOutput(self, f"StageS3Prefix{stage.title()}", 
                 value=f"{stage}/emails/")
        CfnOutput(self, f"ApiGatewayUrl{stage.title()}", 
                 value=api.url)
        CfnOutput(self, f"ApiCustomDomainUrl{stage.title()}", 
                 value=f"https://{custom_domain_name}")
