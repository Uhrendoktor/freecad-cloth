---
applyTo: ".github/workflows/**/*.yml,.github/workflows/**/*.yaml"
---

- Keep one canonical workflow and fail-closed acceptance checks.
- Preserve least-privilege permissions and exact PR-head checkout.
- Keep untrusted pull-request code off privileged self-hosted runners.
- Do not introduce parallel workflows or pull_request_target-based brokers.
