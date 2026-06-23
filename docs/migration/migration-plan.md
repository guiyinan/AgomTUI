# Migration Plan

## Phase 1
- extract schema and validator
- copy reference runtime shell
- define host contracts
- scaffold compiler package with collector / AI synthesizer / validator / publisher boundaries

## Phase 2
- move runtime to host-agnostic asset packaging
- introduce adapter-based metadata repository and action executor
- replace hardcoded Agom vocabulary with pluggable formatters
- replace static compiler candidate loading with a real LLM synthesis backend

## Phase 3
- split compiler into generic collectors plus host adapters
- add package tests and CI
- add demo host with minimal metadata

## Phase 4
- publish `agomtui-core`
- publish `agomtui-runtime`
- add first official Django adapter

## Extraction rule
Never move Agom business assumptions into the new product unless they are behind an adapter or vocabulary pack.
