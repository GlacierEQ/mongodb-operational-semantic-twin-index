# Issue contract — Operational-Semantic Twin Index

## Problem
integrating AI retrieval/memory without turning a general operational database into an overcomplex bundle or duplicating state across systems

## Desired outcome
A bounded, open, testable implementation of **Operational-Semantic Twin Index** that demonstrates Derive semantic indexes directly from authoritative document mutations with provenance and transaction linkage so app state and retrieval state cannot silently diverge.

## Non-goals
- MongoDB affiliation or proprietary integration
- Portfolio-wide scale/performance claims
- UI marketing site

## Acceptance
1. Mechanism module implements allow + refuse with structured receipts
2. pytest behavioral suite green
3. operate.py cold-start produces JSON receipt
4. Non-affiliation disclaimer preserved
