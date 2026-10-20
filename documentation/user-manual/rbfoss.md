<!--
SPDX-FileCopyrightText: 2026 Robert Bosch GmbH
SPDX-FileContributor: Tolga Dalman

SPDX-License-Identifier: MIT
-->

# About

*rbfoss* is a wrapper tool for OSS tools and services, in particular the FossID
service. Being part of the *rbbuild* suite, *rbfoss* makes use of the
dependencies and repository information from *manifest.json*.


# User Setup

Access to the FossID service requires an API KEY, which is created or renewed in the
user profile of the FossID web UI. Register the API KEY together with your  user ID
as credentials of the FossID remote service of the selected profile:

```
rbbconf -s service.<service-id>.user=<user ID>
rbbconf -s service.<service-id>.credentials=<API-KEY>
```

The `<service-id>` is the `remote_service` entry of the `[profile.oss.*]` section
(see below). For details on user credentials, see [rbbconf](rbbconf.md).

Do NOT share the API KEY with anyone!


# Use Cases

## Use Case 1: Dependency Check of Third-Party provided software

In this use case, a software release is provided in parts or entirely by a third-party
supplier and source code may not be even available. However, since OSS license obligations
must be fulfilled, dependency clearing must be performed to provide:
1. OSS disclosure bundle.
2. A machine readable SBOM document (required by EU CRA and derived guidelines).
A scan report is not required but recommended if possible.

To check the OSS disclosure bundle, it must be verified that the dependencies
(provided by the supplier) are "cleared", i.e., the license obligations can be
fulfilled.


## Use Case 2: Scan & Check of an in-house developed rbbuild release package

While it is not strictly required, scanning OSS software with FossID is helpful
and necessary to identify transient dependencies and assurance that no
other licensed snippets are incorporated.

Thus, *rbfoss* extends the regular *rbbuild* workflow such that:
* Clearance of dependencies is checked
* FossID project and scan is automatically generated, based on the rbbuild package name and version
* A FossID scan is conducted
* Findings and pending files are being cleared using the FossID Web UI.
* Once everything is ready, a scan report is generated.


# rbfoss Actions

The workflow of *rbfoss* consists of the following steps (i.e., with no other actions defined):

1. Traverse all dependencies and check each component (*dependendencies*)
2. Setup FossID project and scan entry (*setup*)
3. Upload sources from git (*upload*)
4. Start FossID scan run (*run*)
5. Generate a FossID scan report
6. Clean a previously created FossID project or scan entry (*clean*)


## Dependency clearing (-D)

OSS packages (called *components* in FossID), together with their licenses,
must be cleared and approved in order to be included as dependencies in
commercial products.

To check whether dependencies are cleared, the following command is executed:
```
rbfoss -D
```
The command will read the *manifest.json* file (as a result from a local rbbuild call)
and check each (direct and indirect) dependency object.
If the dependency is an rbbuild object, it will be checked whether an appropriate FossID scan code is present.
Otherwise, a component and license check will be performed.


## Setup FossID Project and Scan entry (-s)

Before running a scan, a FossID project and scan entry must be created.
This is done with the following command in the current git repository:
```
rbfoss -s
```

FossID project code and scan code will be created, following these naming
conventions:
```
project code: <org prefix>_<package name>
project name: same as project code
scan code:    <org prefix>_<package name>-<package-version>
scan name:    same as scan code
```

Examples:

| project code/name   | scan code/name                         |
|---------------------|----------------------------------------|
| MYORG\_mypackage    | MYORG\_mypackage-1.0.0.99              |


## Upload sources location from git (-u)

FossID supports downloading sources from a git repositories. To do
so, the FossID public SSH key must be registered in git.

The Git repository information is automatically passed from rbbuild manifest.json
to FossID during setup time. By calling
```
rbfoss -u
```
The upload from git to FossID will be started and *rbfoss* will synchronously wait
until the operation is completed. This operation can be interrupted and will be
seamlessly continued if the command is called again at a later point.

A scan run can only be started if this operation was completed successfully.
The *rbfoss* CLI will report this accordingly.


## Run a FossID scan (-r)

Once sources are uploaded to FossID, a scan can be run with
```
rbfoss -r
```
Like other commands, this command will poll for completion (or failure) of
the scan indefinitely.
Findings from a previous run in the same project will be reused, if exists.
Clearing of the findings must be performed in the WebUI and is not controlled
by *rbfoss* at all.


## Generate FossID scan report (-g)

*rbfoss* is run with the target release package in question:
```
rbfoss -g
```
If a FossID scan code of the package in question is present, the scan
information is retrieved and added to the generated scan report.
In this case, the presence of scan reports for all dependencies can be assumed.
Thus, the dependency tree is traversed recursively and the reports for each
dependency package is retrieved.
The HTML report file is placed under `obj/<tcid>/rbfoss`, thus, following the usual
*rbbuild* rules.


## Delete / Clean (-c)

This is meant to be a help utility for FossID (power) users. The Web UI is rather cumbersome and bears the risk
that an unrelated project or scan is being deleted.

Similar to the *rbbuild* clean options, the following commands are available:

```
rbfoss -c   # delete FossID scan of last built rbbuild project
rbfoss -cf  # delete FossiD project of the same project IF it is empty (no other scans)
```


# Repository and scan configuration

Following the general *rbbuild* configuration mechanism, *rbfoss* parameters
are specified in the package's *pyproject.toml* file.


## Profile configuration

OSS scanning is configured per profile under the `[profile.oss.*]` section.
Each entry names an OSS scanner configuration and must include a `type` field
that selects the backend scanner (currently only `'fossid'` is supported):

```toml
[profile.oss.project]
type               = 'fossid'
project_org_prefix = 'MYORG'
remote_service     = 'fossid_service'
users              = ['jdoe', 'asmith']
ignore_files       = ['.gitignore', 'Jenkinsfile']
ignore_folders     = ['.git']
```

The `remote_service` value refers to a matching file `remote-services/fossid_service.toml`:

```toml
[profile.services.fossid_service]
type = 'fossid'
url  = 'https://fossid.service/'
```

Profile-level `ignore_files`, `ignore_folders`, and `ignore_extensions` are merged with
repository-level settings from `pyproject.toml`.


## rbfoss configuration specification

| option                  |  type  | description                                                      |
|-------------------------|--------|------------------------------------------------------------------|
| exclude\_dependencies   |  list  | Packages will be excluded from dependency check.                 |
| ignore\_files           |  list  | Exclude files from scanning.                                     |
| ignore\_folders         |  list  | Exclude folders from scanning.                                   |


Example:
```
[tool.rbfoss]
exclude_dependencies = ['build_tools', 'sign_supplicant-1.2.3.4']
ignore_extensions = ['ism']
ignore_folders = ['unit_test', 'component_test', '.git']
ignore_files = ['.gitignore']
```

