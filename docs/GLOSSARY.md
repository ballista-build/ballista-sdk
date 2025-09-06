# Glossary
## Terms
### Artifact
An individual package of code/data/etc. with an explicit type. Allows configuration for execution in an Environment. Allows configuration to be built and packaged.

#### Build Requirements
The requirements of how to build a specific [Artifact](#artifact).

#### Execution Parameters
The parameters given to an [Artifact](#artifact) at runtime to control the way it is executed. Maintained by an [Environment Manager](#environment-manager).

#### Execution Requirements
The requirements for executing a specific [Artifact](#artifact). This includes all [Resource](#resource), [Service](#service), etc. definitions used by the [Artifact](#artifact). Maintained by a [Project Author](#project-author) inside a [Bolt](#bolt).

#### Resource
An entity maintained by an [Artifact](#artifact) that can be requested by other [Artifacts](#artifact) for their own execution.

Examples: a PostgreSQL database, a Redis index, etc.

#### Service
A named network interface to communicate with an executing [Artifact](#artifact).

### Bolt
A bundle of multiple [Artifact](#artifact)s that belong to a single [Project](#project). This contains the known [Artifact](#artifact)s  with their related [Build Requirements](#build-requirements) and [Execution Requirements](#execution-requirements).

### Environment
A destination where [Bolts](#bolt) are launched and [Artifact](#artifact) are executed.

### Launch
A single deployment of a [Bolt](#bolt) to an [Environment](#environment).

### Project
A collection of [Artifacts](#artifact) that represent a single piece of software. A project's [Launch](#launch) history includes the [Bolts](#bolt) that represented it at those times.

## Personas
Different kinds of people have different needs, demands, and experiences met by Ballista and they are defined as "Personas".

### Project Author
A user that creates a piece of software and a corresponding [Bolt](#bolt) to enable Launching with Ballista.

#### Goals and Responsibilities
- Writes a [Project's](#project) artifact definitions into a [Bolt](#bolt) as a `ballista.yaml` file.
- Launches their [Bolt](#bolt) into [Environments](#environment).

### Environment Manager
A user that is maintaining and controlling one or more Ballista-enabled [Environments](#environment).

#### Goals and Responsibilities
- Creates persistent [Environments](#environment) as destinations to Launch [Bolts](#bolt).
- Launches and maintains common Platform Resources across Environments.
- Configures [Execution Parameters](#execution-parameters) for [Projects](#project) and [Artifacts](#artifact).
