# Wishlist

This document records useful future features that are intentionally not current
Skuld behavior.

## Stack Discovery Providers

Skuld should eventually discover adjacent runtime and exposure stacks without
turning into a deployment framework or configuration editor.

### Docker

Potential value:

- Show containers related to tracked services.
- Correlate service ports with container published ports.
- Surface image, container name, and status in `describe` and optional table
  columns.

Initial boundary:

- Read-only discovery through Docker CLI or socket access.
- No container creation, deletion, image pulls, compose editing, or restart
  orchestration until a separate operation contract exists.

### Caddy

Potential value:

- Show Caddy site labels, reverse proxy targets, and exposed domains.
- Correlate Caddy routes with tracked service ports.
- Surface route metadata in `describe` and optional table columns.

Initial boundary:

- Read-only discovery from Caddy config/API where available.
- No Caddyfile edits, admin API mutations, certificate operations, or reloads.

## Design Constraint

These providers should enrich Skuld's visibility first. They should not weaken
the rule that host-mutating service operations resolve through Skuld's registry
and an explicit backend operation contract. nginx already follows that shape as
a Linux-only explicit read-only provider; Docker and Caddy should keep the same
discipline when they move out of wishlist status.
