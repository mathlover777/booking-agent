#!/usr/bin/env python3
import os
import sys

import aws_cdk as cdk

from vibes.stacks.common_stack import CommonStack
from vibes.stacks.email_processor_stack import EmailProcessorStack


def main():
    app = cdk.App()
    
    # Get stage from command line argument or environment variable, default to 'dev'
    stage = app.node.try_get_context('stage') or os.getenv('STAGE', 'dev')
    
    # Validate stage
    valid_stages = ['dev', 'staging', 'prod']
    if stage not in valid_stages:
        print(f"Error: Invalid stage '{stage}'. Valid stages are: {valid_stages}")
        sys.exit(1)
    
    # Environment configuration
    env = cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'), 
        region=os.getenv('CDK_DEFAULT_REGION')
    )
    
    # Common Stack (deploy once, shared across stages)
    common_stack = CommonStack(
        app, "VibesCommonStack",
        env=env,
        description="Shared infrastructure for Vibes email processing (SES, S3, Route53)"
    )
    
    # Email Processor Stack (deploy per stage)
    email_processor_stack = EmailProcessorStack(
        app, f"VibesEmailProcessorStack{stage}",
        stage=stage,
        env=env,
        description=f"Email processor resources for Vibes {stage} environment"
    )
    
    # Add dependency: email processor stack depends on common stack
    email_processor_stack.add_dependency(common_stack)
    
    app.synth()


if __name__ == "__main__":
    main()
