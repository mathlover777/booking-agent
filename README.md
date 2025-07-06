
# Welcome to your CDK Python project!

This is a blank project for CDK development with Python.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project is set up like a standard Python project.  The initialization
process also creates a virtualenv within this project, stored under the `.venv`
directory.  To create the virtualenv it assumes that there is a `python3`
(or `python` for Windows) executable in your path with access to the `venv`
package. If for any reason the automatic creation of the virtualenv fails,
you can create the virtualenv manually.

To manually create a virtualenv on MacOS and Linux:

```
$ python3 -m venv .venv
```

After the init process completes and the virtualenv is created, you can use the following
step to activate your virtualenv.

```
$ source .venv/bin/activate
```

If you are a Windows platform, you would activate the virtualenv like this:

```
% .venv\Scripts\activate.bat
```

Once the virtualenv is activated, you can install the required dependencies.

```
$ pip install -r requirements.txt
```

At this point you can now synthesize the CloudFormation template for this code.

```
$ cdk synth
```

To add additional dependencies, for example other CDK libraries, just add
them to your `setup.py` file and rerun the `pip install -r requirements.txt`
command.

## Useful commands

 * `cdk ls`          list all stacks in the app
 * `cdk synth`       emits the synthesized CloudFormation template
 * `cdk deploy`      deploy this stack to your default AWS account/region
 * `cdk diff`        compare deployed stack with current state
 * `cdk docs`        open CDK documentation

Enjoy!

## Email Processing Setup

This project sets up an email processing system using AWS SES, S3, and Lambda. The system receives emails for `bhaang.com` and processes them through a Lambda function.

### Deployment Workflow

**Option 1: Two-step deployment**
1. **Deploy the CDK stack:**
   ```bash
   make deploy
   ```

2. **Set up SES domain records (after deployment):**
   ```bash
   # Install development dependencies
   pip install -r requirements-dev.txt
   
   # Run the SES domain setup script using Makefile
   make setup-ses-domain
   ```

**Option 2: Complete deployment in one command**
```bash
make deploy-with-ses
```

   The SES domain setup script will:
   - Get the domain verification token from SES
   - Wait for SES to generate DKIM tokens (up to 3 minutes)
   - Create the necessary TXT and CNAME records in Route53
   - Verify the changes are applied

### Architecture

- **S3 Bucket**: Stores incoming emails with `.eml` extension
- **SES Domain**: Configured for `bhaang.com` with receiving rules
- **Lambda Function**: Processes emails when they arrive in S3
- **Route53**: DNS records for email routing and authentication

### Notes

- SES domain records (verification TXT and DKIM CNAME) are created separately after deployment because the tokens are not immediately available during CDK deployment
- The system is configured for the `ap-south-1` region
- All emails sent to `@bhaang.com` will be processed by the Lambda function
