#!/usr/bin/env python3
import os

import aws_cdk as cdk

from vibes.vibes_stack import VibesStack


app = cdk.App()
VibesStack(app, "VibesStack",
    # Using the current CLI configuration for account and region
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
    )

app.synth()
