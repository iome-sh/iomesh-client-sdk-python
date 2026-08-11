# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| `0.1.x` (latest on `main`) | ✅ security fixes |
| pre-release / untagged | best-effort |

## Reporting a vulnerability

**Please do not open public GitHub issues for security vulnerabilities.**

Preferred channels (in order):

1. **GitHub Security Advisory** (private) — Security → Advisories → Report a vulnerability  
2. Email **security@iome.sh** (or the security contact listed at [iome.sh](https://iome.sh))

Include:

1. Description of the issue and impact  
2. Steps to reproduce (PoC if available)  
3. Affected package version / commit  
4. Whether you plan coordinated disclosure  

We aim to acknowledge within **2 business days** and provide a status update within **7 days**.

## Scope

In scope for this repository:

- Client credential handling and HTTP auth headers (`Bearer`, tenant/org/workspace headers)
- URL validation (reject `file://`, userinfo in broker URL)
- Dependency and packaging supply-chain issues for this package

Out of scope:

- Security of a remote I/O Mesh broker / control plane deployment
- Third-party connectors or applications that import this SDK

## Practice

- Never commit API keys, bearer tokens, or `.env` files  
- Prefer environment variables (`IOMESH_API_KEY`, …) on the operator machine  
- Report issues privately first when in doubt  
