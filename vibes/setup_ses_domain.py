#!/usr/bin/env python3
"""
Script to create SES domain verification and DKIM records after CDK deployment.
This script should be run after the CDK stack is deployed.

The script handles:
- Domain verification TXT record (_amazonses.bhaang.com)
- DKIM CNAME records for email authentication
"""

import boto3
import time
import sys

DOMAIN = "bhaang.com"

route53 = boto3.client("route53")
ses = boto3.client("ses")


def get_hosted_zone_id(domain: str) -> str:
    """Get the hosted zone ID for the given domain."""
    paginator = route53.get_paginator("list_hosted_zones")
    for page in paginator.paginate():
        for zone in page["HostedZones"]:
            if zone["Name"] == f"{domain}." and not zone["Config"]["PrivateZone"]:
                return zone["Id"].split("/")[-1]
    raise Exception(f"Hosted zone not found for {domain}")


def get_dkim_tokens(domain: str) -> list[str]:
    """Get DKIM tokens for the SES domain."""
    resp = ses.get_identity_dkim_attributes(Identities=[domain])
    return resp["DkimAttributes"][domain]["DkimTokens"]


def get_verification_token(domain: str) -> str:
    """Get domain verification token for SES."""
    resp = ses.get_identity_verification_attributes(Identities=[domain])
    return resp["VerificationAttributes"][domain]["VerificationToken"]


def create_dkim_changes(tokens: list[str]) -> list[dict]:
    """Create Route53 change records for DKIM CNAME records."""
    changes = []
    for token in tokens:
        record_name = f"{token}._domainkey.{DOMAIN}."
        target = f"{token}.dkim.amazonses.com."
        print(f"Creating DKIM record {record_name} -> {target}")
        changes.append({
            "Action": "UPSERT",
            "ResourceRecordSet": {
                "Name": record_name,
                "Type": "CNAME",
                "TTL": 300,
                "ResourceRecords": [{"Value": target}]
            }
        })
    return changes


def create_verification_changes(verification_token: str) -> list[dict]:
    """Create Route53 change records for domain verification TXT record."""
    record_name = f"_amazonses.{DOMAIN}."
    print(f"Creating verification record {record_name} -> {verification_token}")
    return [{
        "Action": "UPSERT",
        "ResourceRecordSet": {
            "Name": record_name,
            "Type": "TXT",
            "TTL": 300,
            "ResourceRecords": [{"Value": f'"{verification_token}"'}]
        }
    }]


def apply_route53_changes(hosted_zone_id: str, changes: list[dict]):
    """Apply the Route53 changes."""
    if not changes:
        print("No DKIM changes to apply.")
        return
    
    resp = route53.change_resource_record_sets(
        HostedZoneId=hosted_zone_id,
        ChangeBatch={
            "Comment": "Auto-created DKIM records for SES",
            "Changes": changes
        }
    )
    print("Change submitted:", resp["ChangeInfo"]["Id"])
    print("Change status:", resp["ChangeInfo"]["Status"])


def main():
    """Main function to set up DKIM and verification records."""
    print(f"Setting up SES domain records for {DOMAIN}")
    
    try:
        print(f"Looking up hosted zone for {DOMAIN}")
        zone_id = get_hosted_zone_id(DOMAIN)
        print(f"Found hosted zone: {zone_id}")

        # Get verification token
        print("Getting domain verification token...")
        verification_token = get_verification_token(DOMAIN)
        print(f"Verification token retrieved: {verification_token}")

        # Get DKIM tokens
        print("Polling for DKIM tokens...")
        for attempt in range(12):  # Try for 3 minutes (12 * 15 seconds)
            tokens = get_dkim_tokens(DOMAIN)
            if len(tokens) == 3:
                print(f"DKIM tokens retrieved: {tokens}")
                break
            print(f"Attempt {attempt + 1}/12: waiting for tokens... (found {len(tokens)})")
            time.sleep(15)
        else:
            raise TimeoutError("DKIM tokens not available after waiting 3 minutes.")

        # Create all changes
        all_changes = []
        all_changes.extend(create_verification_changes(verification_token))
        all_changes.extend(create_dkim_changes(tokens))
        
        # Apply all changes
        apply_route53_changes(zone_id, all_changes)
        
        print("SES domain setup completed successfully!")
        
    except Exception as e:
        print(f"Error setting up SES domain records: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 