# Ballista Python SDK
Create Python systems that implement the Ballista.build capabilities.

## Big Mega Still In-Development Warning
Highly volatile and in heavy development. Probably do not want to use this yet.

## Prerequisites
- uv
- just

## Glossary
See [GLOSSARY](docs/GLOSSARY.md)

## Repo commands
Common repository commands provided by `just`. Run `just` to get a list of them.



# Architecture
## Resource Providers
InfrastructureAdapter -> transport method (HTTP, GRPC, etc.) -> ResourceProvider protocol implementation


Lifecycle Interpretations
- Large change to resource (not sure what that means yet)
  - `copy_resource` copies existing resource A to new resource B
  - `get_resource_status` waits for copy to complete (maybe?)
  - something swaps from resource A to B
  - `destroy_resource` destroys resource A
- Small change to resource
  - `update_resource` on resource A
