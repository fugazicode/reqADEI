#!/bin/bash
cd /c/Users/02/Documents/reqADEI
echo "Staging changes..."
git add -A
echo "Committing..."
git commit -m "Add queue-based submission system with PortalSession

- Add Playwright and pypdf to requirements
- Add portal_username/portal_password to Settings
- Implement PortalSession for portal login and navigation
- Implement SubmissionWorker and SubmissionJob for async submissions
- Add FormFiller skeleton with tab structure
- Add test_portal.py smoke test

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

echo "Running test..."
python3 test_portal.py
