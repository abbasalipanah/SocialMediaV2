# Changelog

All notable changes to Social Media V2 are documented in this file.

## [Unreleased]

### Fixed

- Align the Phase 2 projection/session adapter with the existing
  `social_projection_state.payload_json` schema without adding DDL.
- Enforce the existing `varchar(255)` projection-key limit before persistence.
- Exercise PostgreSQL integration tests against the V1-compatible table contract.

## [0.1.0] - 2026-07-13

### Added

- Immutable source baselines and a downstream-only source write guard.
- Fail-closed runtime, database, write-policy and TikTok bootstrap configuration.
- Hash-locked Python dependencies and a locked React 19/Vite frontend bootstrap.
- Canonical platform and command/query boundary enforcement.
- Accumulate SSO v1 verification, one-time JTI consumption and hash-only local sessions.
- Signed provisioning receiver with HMAC, nonce/event replay protection and version ordering.
- PostgreSQL-backed session and authority projection adapter with immediate session revocation.
- Unit, API, replay and disposable PostgreSQL integration tests.
- GitHub Actions verification for backend, PostgreSQL, frontend and generated artifacts.

### Security

- Production-like database and secret configuration remains blocked before final cutover.
- Runtime writes remain disabled by default and provider/worker gates remain off.
- Auth responses are non-cacheable; browser logout requires same-origin requests.
