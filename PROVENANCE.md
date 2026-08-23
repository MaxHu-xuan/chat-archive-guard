# Provenance

ChatArchiveGuard is a clean-room implementation of a behavioral and security
specification. Its implementation was written independently for this package.

The package does not incorporate production source code, production Git
history, production configuration, production fixtures, or production user
data. Tests construct synthetic records and databases at runtime and do not
depend on network access.

This statement records the intended development process; it is not a legal
opinion or a substitute for ongoing provenance review. Maintainers must confirm
authorship and ownership for every shipped file and review third-party
obligations before each release.

The bundled privacy audit mechanically checks the candidate release tree for
required metadata, the approved license file, generated or persistent
artifacts, common sensitive literals, and direct network/process imports. A
passing audit supports this review but does not establish authorship or replace
inspection of the final source archive.

The package is licensed under the Apache License, Version 2.0. See `LICENSE`.
Contributions intentionally submitted for inclusion are accepted under the
same license as described in `CONTRIBUTING.md`.
