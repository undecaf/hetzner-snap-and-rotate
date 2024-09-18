# Creating and rotating snapshots of Hetzner cloud servers

This script can perform the following tasks for selected servers of a [Hetzner cloud project](https://www.hetzner.com/cloud/):

- Creating a new snapshot
- Shutting down the server before taking a snapshot and restarting it afterwards
- Rotating snapshots, retaining a limited number of quarter-hourly, hourly, daily, weekly, monthly, quarterly and
  yearly snapshots
- Generating names of new and rotated snapshots from templates
- Linking rotation periods to either fixed clock/calendar instants or to the most recent snapshot

These tasks can be configured independently per server in a [JSON configuration file](#creating-the-configuration-file).

Additional features:

- The secret API token can be read from the configuration file, from an environment variable or from `stdin`
- Log messages are sent to the console or to syslog


## Content

- [Generating an API token](#generating-an-api-token)
- [Installing this script](#installing-this-script)
- [Creating the configuration file](#creating-the-configuration-file)
  - [Taking snapshots](#taking-snapshots)
  - [Rotating snapshots](#rotating-snapshots)
  - [Snapshot name templates](#snapshot-name-templates)
- [Running the script natively](#running-the-script-natively)
  - [Command line options](#command-line-options)
  - [Passing the API token](#passing-the-api-token)
  - [Creating and rotating snapshots in a cron job](#creating-and-rotating-snapshots-in-a-cron-job)
  - [Snapshots seem to be missing after rotation](#snapshots-seem-to-be-missing-after-rotation)
- [Running the script in a container](#running-the-script-in-a-container)
  - [Passing the configuration file to the container](#passing-the-configuration-file-to-the-container)
  - [Environment variables](#environment-variables)
  - [Examples](#examples)
- [Licenses](#licenses)


## Generating an API token

[This document](https://docs.hetzner.com/cloud/api/getting-started/generating-api-token/) describes in detail
how to generate an API token for your Hetzner cloud project. This script requires a token with "Read & Write"
permission.

Guard your API token well since it provides unlimited read/write/delete access to all servers, snapshots, backups etc. 
of your Hetzner cloud project!


## Installing this script

This script is available as a [PyPI project](https://pypi.org/project/hetzner-snap-and-rotate/). It can be installed by:

```shell
python3 -m pip install hetzner-snap-and-rotate
```


## Creating the configuration file

The configuration file is expected to be a JSON document in UTF-8 encoding with the following structure:

```
{
  "api-token": "...",          // optional, can also be passed via the command line;
                               // see section "Command line options" below

  "defaults": {                // optional defaults, can be overriden per server
      "create-snapshot":       // create a new snapshot whenever the script is invoked
        true,
      "snapshot-timeout":      // timeout (in s) after which snapshot creation is considered to have failed
         120,
      "snapshot-name":         // template for the snapshot name; see section "Snapshot name templates" below
        "{server}_{period_type}#{period_number}_{timestamp:%Y-%m-%d_%H:%M:%S}_by_{env[USER]}",
      "shutdown-and-restart":  // shut down the server before taking a snapshot
        true,                  // and restart it afterwards
      "shutdown-timeout":      // timeout (in s) after which graceful shutdown is considered to have failed
         15,
      "allow-poweroff":        // power off the server if it cannot be shut down gracefully
         false,
      "rotate":                // rotate the existing snapshots and the new one, if any 
         true,
      "sliding-periods":       // whether rotation periods are sliding or clock/calendar-based;
         false,                // see section "Rotating snapshots" below
      "quarter-hourly":        // number of quarter-hourly snapshots to retain (intended for testing)
         0,
      "hourly":                // number of hourly snapshots to retain
         2,
      "daily":                 // number of daily snapshots to retain
         3,
      "weekly":                // number of weekly snapshots to retain
         4,
      "monthly":               // number of monthly snapshots to retain
         3,
      "quarter-yearly":        // number of quarter-yearly snapshots to retain
         2,
      "yearly":                // number of yearly snapshots to retain
         1
    },

  "servers": {                 // one entry per server
    "server-1": {              // Hetzner cloud server name
                               // uses only "defaults" settings
    },

    "server-2": {              // another server; override a few defaults
      "snapshot-name": "snapshot_{timestamp:%Y-%m-%d_%H:%M:%S}",
      "snapshot-timeout": 300,
      "shutdown-timeout": 30,
      "allow-poweroff": true,

      "sliding-periods": true,
      "hourly": 0,
      "daily": 0,
      "monthly": 6,
      "quarter-yearly": 0,
      "yearly": 0
    }
  }
}
```

Omitted `defaults` default to `0`, `false` or `''` except for:

- `snapshot-timeout`: defaults to `300`
- `shutdown-timeout`: defaults to `30`

Please note that this is not valid JSON due to the comments.
File [resources/config-example.json](https://raw.githubusercontent.com/undecaf/hetzner-snap-and-rotate/refs/heads/main/resources/config-example.json) contains the same example
as a valid JSON file without comments.


### Taking snapshots

This script takes a snapshot of every `server` in the configuration file
for which `create-snapshot` is `true`. If taking the snapshot takes longer 
than `snapshot-timeout` then that operation is considered to have failed.

If `shutdown-and-restart` is `true` and the server is running
then the script attempts to shut down the server gracefully before taking the snapshot.
If the server cannot be shut down gracefully within the `shutdown-timeout` then it
will be powered down instead if `allow-poweroff` is `true`, or else the snapshot operation will fail.
If the server was running before taking the snapshot then it is restarted afterwards.


### Rotating snapshots

This script rotates the snapshots of every `server` in the configuration file
for which `rotate-snapshots` is `true`.

"Rotating" means that existing snapshots will be renamed
according to `snapshot-name`, or will be deleted if they are not contained in any of the
configured `quarter-hourly`, `hourly`, ... `yearly` periods. These settings determine
for how many such periods the snapshots will be retaind.

The rotation process is governed by the following rules:

- Periods are counted backwards from the instant of the rotation process.
- If `sliding-periods` is `true` then the last period starts at
the rotation instant minus the respective period length, i.e. periods slide along with
the instant of rotation.
- If `sliding-periods` is `false` then the last period 
starts at the latest of the following instants that lies before the rotation instant:

  | Rotation period  | Starts at                                                          |
  |------------------|--------------------------------------------------------------------|
  | `quarter-hourly` | :00, :15, :30 or :45 in the current hour                           |
  | `hourly`         | :00 in the current hour                                            |
  | `daily`          | 00:00 on the current day                                           |
  | `weekly`         | 00:00 on Monday of the current week                                |
  | `monthly`        | 00:00 on the first day of the current month                        |
  | `quarterly`      | 00:00 on the first day of Jan, Apr, Jul or Oct of the current year |
  | `yearly`         | 00:00 on Jan 1 of the current year                                 |

  These instants refer to the timezone of the system running this script.

- If a period contains multiple snapshots then only the most recent one will be retaind for that period.
- Retaining a snapshot for some period takes precedence over deleting that snapshot for some other period.
- Rotated snapshots are renamed according to the template `snapshot-name`. This allows the server name,
the period, the snapshot timestamp and environment variables to become part of the snapshot name.  
See section [Snapshot name templates](#snapshot-name-templates) below for details.
- If the same snapshot is contained in multiple periods then `snapshot-name` uses the longest period.


### Snapshot name templates

`snapshot-name` must be a string and may contain [Python format strings](https://docs.python.org/3/library/string.html#format-string-syntax).
The following field names are available for formatting:

| Field name      |                                   Type                                   | Rendered as                                                                                                                                                                                                                                                                      |
|-----------------|:------------------------------------------------------------------------:|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `server`        |                                  `str`                                   | Server name, same as `server` in the [configuration file](#creating-the-configuration-file)                                                                                                                                                                                      |
| `period_type`   |                                  `str`                                   | Type of period: `quarter-hourly`, `hourly`, ... `yearly`, or `latest` for a new snapshot that is not contained in any period                                                                                                                                                     |
| `period_number` |                                  `int`                                   | Rotation number of the period: `1` = latest, `2` = next to latest and so on; always `0` for for a new snapshot with period `latest`                                                                                                                                              |
| `timestamp`     | [`datetime.datetime`](https://docs.python.org/3.8/library/datetime.html) | _Creation_ instant of the snapshot (_not changed by rotation_), expressed in the timezone of the system running this script. [`datetime`-specific formatting](https://docs.python.org/3.10/library/datetime.html#strftime-and-strptime-format-codes) may be used for this field. |
| `env`           |                               `dict[str]`                                | Environment variables, may be referred to like e.g. `env[USER]`                                                                                                                                                                                                                  |

If the same snapshot is contained in multiple periods then the longest period
determines `period_type` and `period_number`.


## Running the script natively

```shell
python3 -m hetzner_snap_and_rotate [options ...]
```


### Command line options

| Option                                                                                   | Description                                                                                                                                                                               |
|------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| <code>--config <u>config_file</u></code><br><code>-c <u>config_file</u></code>           | Read the configuration from <code><u>config_file</u></code>. Default: `config.json`                                                                                                       |
| <code>--api-token-from <u>env_var</u></code><br><code>-t <u>env_var</u></code>           | Read the API token from environment variable <code><u>env_var</u></code>, or read it from `stdin` if `'-'` is specified. Default: get the API token from <code><u>config_file</u></code>. |
| <code>--facility <u>syslog_facility</u></code><br><code>-f <u>syslog_facility</u></code> | Send the log messages to <code><u>syslog_facility</u></code> (`SYSLOG`, `USER`, `DAEMON`, `CRON`, etc.). Default: send log messages to `stdout`.                                          |
| <code>--priority <u>pri</u></code><br><code>-p <u>pri</u></code>                         | Log only messages up to syslog priority <code><u>pri</u></code> (`ERR`, `WARNING`, `NOTICE`, `INFO`, `DEBUG`, or `OFF` to disable logging). Default: `NOTICE`.                            |
| `--dry-run`<br>`-n`                                                                      | Perform a trial run with no changes made. This requires only an [API token](#generating-an-api-token) with "Read" permission.                                                             |
| `--version`<br>`-v`                                                                      | Display the version number and exit.                                                                                                                                                      | 
| `--help`<br>`-h`                                                                         | Display a help message and exit.                                                                                                                                                          |


### Passing the API token

The API token provides complete control over your Hetzner cloud project, therefore it must be protected against
unauthorized access. The following methods are available for passing the API token to the script:

- Inlcuding it as `api-token` in the configuration file. The configuration file then must be protected adequately.
- Passing it via an environent variable and specifying the variable name on the command line as `api-token-from`.
- Piping it to the script through `stdin` and specifying `api-token-from -` on the command line.


### Creating and rotating snapshots in a cron job

As a cron job, this script should run at least once per the shortest period for which snapshots are to be retained.  
If, for example, the shortest retention period has been set to `daily` then the script should run at least daily.


### Snapshots seem to be missing after rotation

If several types of retention period (e.g. `daily`, `weekly` and `monthly`) have been defined then the latest snapshot
will be contained in the latest period of each type at the same time.  
Since the snapshot will be named after the longest period (`monthly`), there will not be any snapshots named 
after the latest ones of the shorter retention periods (`daily` and `weekly`).


## Running the script in a container

[This image on Docker Hub](https://hub.docker.com/r/undecaf/hetzner-snap-and-rotate) runs the script
in a [Docker](https://www.docker.com/) or [Podman](https://podman.io/) container
(for Podman, substitute `podman` for `docker` in the following commands):

```shell
docker run [Docker options] undecaf/hetzner-snap-and-rotate:latest [script command line options]
```

The same [command line options](#command-line-options) are available as for the native script.


### Passing the configuration file to the container

[The configuration file](#creating-the-configuration-file) needs to be prepared on the host.
It can be passed to the container in various ways:

- As a [bind mount](https://docs.docker.com/storage/bind-mounts/), e.g.

  ```shell
  docker run --mount type=bind,source=/path/to/your/config.json,target=/config.json [other Docker options] undecaf/hetzner-snap-and-rotate:latest [script command line options]
  ```
  
- As a [secret](https://docs.docker.com/engine/swarm/secrets/); this requires [Podman](https://podman.io/) or 
[Docker swarm](https://docs.docker.com/engine/swarm/).  
  First, your configuration file needs to be saved as a secret (e.g. called `config_json`):

  ```shell
  docker secret create config_json /path/to/your/config.json
  ```
  
  That secret becomes part of your Docker/Podman configuration and then can be passed to the container:

  ```shell
  docker run --secret=config_json,target=/config.json [other Docker options] undecaf/hetzner-snap-and-rotate:latest [script command line options]
  ```


### Environment variables

Environment variables referenced in your [snapshot name templates](#snapshot-name-templates) must be
passed to the container as `--env` options, e.g.

```shell
docker run --env USER=your_username [other Docker options] undecaf/hetzner-snap-and-rotate:latest [script command line options]
```


### Examples

Display the script version and exit:

```shell
# does not require a configuration file
docker run --rm  undecaf/hetzner-snap-and-rotate:latest --version
```

Dry run with the API token in the configuration file, log priority `DEBUG`:

```shell
# option --tty/-t displays log output in real time
docker run \
  --rm \
  --tty \
  --mount type=bind,source=/path/to/your/config.json,target=/config.json \
  undecaf/hetzner-snap-and-rotate:latest --dry-run --priority DEBUG
```

Live run with the API token in the configuration file:

```shell
# option --tty/-t displays log output in real time
docker run \
  --rm \
  --tty \
  --mount type=bind,source=/path/to/your/config.json,target=/config.json \
  undecaf/hetzner-snap-and-rotate:latest
```

Passing the API token through `stdin`:

```shell
# requires option --interactive/-i, adding --tty/-t would display the API token :-(
cat /your/api/token/file | docker run \
  --rm \
  --interactive \
  --mount type=bind,source=/path/to/your/config.json,target=/config.json \
  undecaf/hetzner-snap-and-rotate:latest --api-token-from -
```


## Licenses

Software: [MIT](https://opensource.org/license/mit)

Documentation: [CC-BY-SA 4.0](http://creativecommons.org/licenses/by-sa/4.0/)
