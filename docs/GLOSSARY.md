# Glossary
## Terms
### Artifact
An individual package of code/data/etc. with an explicit type. Allows configuration for execution in an Environment. Allows configuration to be built and packaged.

#### Build Requirements
The requirements of how to build a specific [Artifact](#Artifact).

#### Execution Parameters
The parameters given to an [Artifact](#Artifact) at runtime to control the way it is executed. Maintained by an [Environment Manager](#Environment-Manager).

#### Execution Requirements
The requirements for executing a specific [Artifact](#Artifact). This includes all [Resource], [Service], etc. definitions used by the [Artifact](#Artifact). Maintained by a [Project Author](#Project-Author) inside a [Bolt](#Bolt).

### Bolt
A bundle of multiple [Artifact](#Artifact)s that belong to a single [Project](#Project). This contains all known [Artifact](#Artifact)s  with their related [Build Requirements](#Build-Requirements) and [Execution Requirements](#Execution-Requirements).

### Environment
A destination where [Bolts](#Bolt) are launched and [Artifact](#Artifact) are executed.

### Launch
A single deployment of a [Project](#Project). to an Environment.

### Project
A collection of [Artifacts](#Artifact) that represent a single piece of software.

### Resource
An entity maintained by [Artifacts](#Artifact) that can be requested by other [Artifacts](#Artifact) for their own execution.

Examples: a PostgreSQL database, a Redis index, etc.

### Service
A named network interface to communicate with an executing [Artifact](#Artifact).

## Personas
Different kinds of people have different needs, demands, and experiences met by Ballista and they are defined as "Personas".

### Project Author
A user that creates a piece of software and a corresponding [Bolt](#Bolt) to enable Launching with Ballista.

#### Goals and Responsibilities
- Writes a [Project's](#Project) requirements into a [Bolt](#Bolt) as a `ballista.yaml` file.
- Launches their [Bolt](#Bolt) into [Environments](#Environment).

### Environment Manager
A user that is maintaining and controlling one or more Ballista-enabled [Environments](#Environment).

#### Goals and Responsibilities
- Creates persistent [Environments](#Environment) as destinations to Launch [Bolts](#Bolt).
- Launches and maintains common Platform Resources across Environments.
- Configures [Execution Parameters](#Execution-Parameters) for [Projects](#Project) and [Artifacts](#Artifact).
