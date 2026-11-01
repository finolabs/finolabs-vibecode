---
name: fnl-security-review-gate
description: Security review for changes that cross a sensitive boundary. Use when a change or pull request adds or alters authentication, authorization, permissions, sharing or tenancy, private or personal data, secrets, untrusted input, payments, or file and network access, and before merging it.
---

# Security review gate

## Triggers

A change needs security scrutiny when it touches any of:

- authentication, sessions, tokens or credentials handling;
- authorization: permissions, roles, grants, tenancy, sharing, scopes;
- private or personal data, its storage, export, logging or deletion;
- untrusted input: parsing, queries, templates, uploads, paths, deserialization, prompts sent to models;
- payments or other irreversible effects;
- network, file system or process boundaries opened to outside callers.

Name the triggered boundaries in the receipt. A trigger raises depth to at least NORMAL (`fnl-coding-workflow`).

## Scope of the review

- **Diff review** covers an exact diff or commit range; **audit** covers an authorized wider scope. Fixing findings or verifying fixes needs its own explicit scope.
- The reviewer is independent, as `fnl-review-gate` says, with the security coverage named in the packet.

## Permission-boundary review

For every protected resource and action the change touches:

1. List each actor class: owner, permitted member, other member, other tenant, anonymous, revoked or expired grant.
2. For each, state the expected result of read, list, search, write and delete.
3. **Negative tests** prove denial for every actor that must be denied, through every entry point (API, CLI, tool, search, export, background job).
4. **No existence leak**: a denied caller gets the same response as for a resource that does not exist: same status, same error shape, no count, timing or field that tells them otherwise. Search, list and count paths never include hidden items.
5. Revocation takes effect on the next request, including cached and long-lived paths.

## Other checks

- Secrets never appear in code, commands, logs, test fixtures or commits; credentials come through the approved injection mechanism.
- Untrusted input is validated at the boundary and parameterized at the sink.
- Errors and logs carry no secrets or personal data beyond what the purpose needs.
- New dependencies are pinned, from a trusted source, and justified.

## Findings

Dispositions, regression tests and re-review follow `fnl-review-gate`. A security finding that is accepted as risk needs the owner's explicit approval. On any secret or personal-data leak: stop, tell the owner, keep the traces for rotation.
