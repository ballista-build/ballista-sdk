# Glossary
## Terms
### Artifact
An individual item of code/data/etc. with an explicit type. Allows configuration to be executed in an Environment. Allows configuration to be built and packaged.

#### Execution Parameters
The configuration given to an artifact to finely control the way it executes.

#### Execution Requirements
The requirements an artifact needs/requests to properly operate.

### Bolt
A unique version of multiples Artifacts that belong to an identified Project. The smallest "unit" in which Ballista acts on and deploys.

### Environment
A environment of executing artifacts and projects.

### Launch
A single deployment of a Project to an Environment.

### Platform Resource
A resource that is fulfilled by other services running inside the environment.

### Project
Contains history of Bolts deployed.

## Personas
Different kinds of people have different needs and experiences with Ballista and they are defined as "Personas".

### Project Author
A user that creates a piece of software and a corresponding Bolt to enable deploying with Ballista.

#### Goals and Responsibilities
- Writes a project's `ballista.yaml` file.
- Launches their Project into Environments.

### Cluster Operator
A user that is maintaining and controlling a Ballista-powered cluster.

#### Goals and Responsibilities
- Creates persistent Environments.
- Launches and maintains common Platform Resources across Environments.
- Configures Execution Parameters for projects and artifacts.
