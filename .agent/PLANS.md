# Agent execution plan template

Use this file for multi-step refactors or architectural changes that need a durable plan while work is in progress. The governing GitHub issue/PR remains the durable record of evidence and review.

## Required sections

# <Task title>

## Objective
Concrete outcome.

## Current evidence
Exact branch/HEAD and authoritative evidence identifiers.

## Architecture
Boundaries and invariants that must remain true.

## Scope
Files, modules and interfaces that may change.

## Non-goals
Frozen behavior and explicitly excluded work.

## Implementation steps
Small independently verifiable steps.

## Verification
Focused tests, integration checks and acceptance evidence.

## Falsifier / stop condition
The result that would invalidate the approach.

## Result
Final change, remaining risks and follow-up after verification.

Keep the plan concrete, current, and smaller than the governing issue/PR. Do not turn it into a history log.
