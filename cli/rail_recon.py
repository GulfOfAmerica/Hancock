#!/usr/bin/env python3
"""Simple CLI for Rails/Cloudflare Recon"""
import sys
from collectors.rails_cloudflare_recon import run_rails_cloudflare_recon

if len(sys.argv) < 2:
    print("Usage: python cli/rail_recon.py <target>")
    sys.exit(1)

target = sys.argv[1]
result = run_rails_cloudflare_recon(target)
print(result)
