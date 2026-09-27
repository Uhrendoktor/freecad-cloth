# Simulation visual review

Simulation changes are accepted through human-reviewable rendered evidence.

## Required evidence
Every simulation implementation PR or experiment issue must expose actual rendered PNG screenshots containing:
- launch / step 0;
- representative intermediate checkpoints, normally steps 15, 45 and 90;
- final front, rear, right, left, top and bottom views;
- any diagnostic/control image needed to distinguish the stated hypothesis.

The images must be visible from the PR or issue conversation. Downloading a workflow artifact ZIP is secondary evidence.

## Review order
Human reviewers inspect the images first, without relying on the implementer's conclusion. Only afterward should logs, manifests, numerical gates and provenance be used.

## Experimental discipline
One bounded hypothesis, one active implementation PR, one falsifier. Rejected or superseded experiments remain historical evidence and must not become competing implementation authorities.

## CI contract
The canonical simulation job publishes its PNG evidence to a per-PR `simulation-evidence/<PR number>` branch and posts actual image links inline on the PR. A run that produces no PNG evidence fails closed.
