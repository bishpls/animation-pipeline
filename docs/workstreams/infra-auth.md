# infra-auth: box control through a service account

Until 2026-09-30 every box call from the laptop (instances describe/start/stop, the stockout reshape, the IAP tunnel
under ssh and rsync, `gcloud storage` and the access tokens bucketsync uses) ran on the owner's personal gcloud login.
Google Cloud session control makes that login reauthenticate every few hours, and when it lapsed overnight (09:50) every
agent's box work stopped. The calls now run on a dedicated service account whose key never needs a reauth. The write-up
this follows is tool/infra3's "For Michael: box control without the nightly reauth" (docs/workstreams/infra3.md).

## What runs where

- **The service account** (created by the coordinator, least privilege): per instance on the two boxes, get, start,
  stop, update and the machine-type/resources/scheduling setters, plus OS Login admin; project-level reads the start and
  the reshape need (zone operations, zones, machine and accelerator types, disks); IAP tunnel use conditioned to port 22
  on the two boxes; actAs on the boxes' own service account; object admin on the box bucket. Its key and its gcloud
  configuration live outside every repo and worktree; the env files name the configuration's path.
- **Laptop.** Each gitignored env file (`infra/gcp/build.env`, `render.env`, `gpu.env`, in every worktree) has
  `export CLOUDSDK_CONFIG=<the service account's gcloud config>` and `BOX_OWNER=<the owner's posix user>`.
  - build.sh, gpu.sh and gpu-start.sh source the env file, so their gcloud calls and reshape.py get it.
  - remote.py reads it (`_gcloud()`; `_env` now reads `export KEY=` lines and expands `$HOME`) for its own gcloud
    calls (`_box_status`, the big-file `gcloud storage cp`) and its ssh sessions.
  - bucketsync.py gets it from build.sh's environment, or finds it itself (`gcloud_config()`: `CHARKIT_BOX_ENV`,
    else the repo's build.env). Its token cache is per gcloud config (`token-<hash>.json`), so a token never crosses
    accounts.
  - reshape.py, run on its own, takes it from the env file beside it whose VM matches.
- **The ssh configs** `~/.ssh/charkit-<vm>.config` that build.sh writes now start with a `# gcloud: <config>` line.
  Their User is that account's OS Login posix user, and their ProxyCommand runs
  `env CLOUDSDK_CONFIG=<config> gcloud compute start-iap-tunnel ...`. So a plain `ssh -F` works from any process,
  whatever its environment. build.sh and remote.py rewrite a config whose marker doesn't match the env file's gcloud
  config (`fresh`). So changing or deleting the env line is enough: the next box call writes the matching config.
- **Boxes: the owner stays the owner.** All box state (/srv/work, the worktree copies, /srv/work/.jobs, the build
  slots in ~/.cache/charkit/slots, the crontab's load sampler) belongs to the owner's Unix user. The service account
  logs in as a different one, so nothing was migrated. Instead, `infra/gcp/as-owner.sh install` put two files on each
  box:
  - `/etc/ssh/sshd_config.d/90-charkit-as-owner.conf`: `Match User <the service account's posix user>` with
    `ForceCommand /usr/local/bin/charkit-as-owner`;
  - the wrapper itself. It changes to the owner's home, then runs
    `sudo -n -u <owner> -H -- bash -c "$SSH_ORIGINAL_COMMAND"`, or a login shell (`sudo -i`) when there's no command.

  An sftp session arrives as the sftp server's path in SSH_ORIGINAL_COMMAND and runs as the owner too. Both files are
  on disk, outside what the boot scripts write (build-startup.sh, gpu-startup.sh and render-setup.sh don't touch sshd)
  and outside the guest agent's edits (it rewrites only its OS Login section at the top of /etc/ssh/sshd_config). So
  they survive a reboot.

## Measured (2026-09-30)

- **`sshd -T`, before against after, on both boxes:** the owner's effective config is identical (an empty diff over its
  91 lines). The service account's differs in one line, `forcecommand none` -> `forcecommand /usr/local/bin/charkit-as-owner`.
- **The same probe, run by a session of each login:** id, pwd, umask and `ulimit -a` are identical. The environment
  differs only in what sudo resets: no SSH_CLIENT/SSH_CONNECTION, XDG_RUNTIME_DIR or DBUS (nothing in charkit, infra or
  tools reads them), and PATH is sudo's secure_path (without /usr/games). The commands that need more source
  /opt/anim-build/env, as before.
- **Transports through the wrapper, on the build box:**
  - exit codes pass through (`exit 7` -> 7);
  - 5 MB of random bytes on stdin arrive with the same sha256;
  - a tty session runs as the owner on a pts;
  - rsync push and pull round-trip, and the pushed files are the owner's;
  - scp works both ways, over sftp (the default) and with -O (legacy);
  - sftp works;
  - a `setsid nohup` process outlives its ssh session.
- **End to end with the service account's config only** (no CLOUDSDK_CONFIG from the shell, a scratch HOME for the ssh
  configs):
  - `remote run ps`: up, bucket sync, detached job, follow; exit 0;
  - `remote build charkit/spec/clawd.json`;
  - `remote jobs` on both boxes (other agents' running jobs listed);
  - `remote attach` of a finished job;
  - bucketsync push, a box-side publish and a pull, with matching sha256s;
  - `gpu.sh status`, and `gpu.sh ssh` (gcloud compute ssh as the service account -> the owner, the T4 listed);
  - `remote --box render jobs`.
- **The pre-flight on a dead credential:** a config with no key fails in one line, no traceback:
  `remote: gcloud (config ...) cannot act for the box: ... Fix: ...`. charkit/tests/test_remote_auth.py checks this
  with a fake gcloud, along with the env parsing.

## Pre-flight

`remote` checks the credential before it starts a job and before `up`: `gcloud auth print-access-token`, without a
prompt, once per gcloud config per command. On failure it prints one line naming the config and what to run: activate
the service account's key in that config, or delete the CLOUDSDK_CONFIG line and `gcloud auth login`. With a key this
should never trigger. `CHARKIT_NO_PREFLIGHT=1` skips it.

## Not covered by the service account (use your own login)

These need the owner's own login, with the CLOUDSDK_CONFIG line commented out while they run:
- provisioning (gpu-provision.sh, build-provision.sh);
- `gpu.sh snapshot`;
- anything that changes IAM, networks or secrets.

The service account can't do them, by design.

## Rollback

- **Laptop:** delete the `export CLOUDSDK_CONFIG=` line from the env files. The next box call rewrites
  `~/.ssh/charkit-*.config` for the default login (`fresh`). To force it, delete those files.
- **Boxes:** `CHARKIT_BOX_ENV=infra/gcp/<box>.env infra/gcp/as-owner.sh remove`, run with the service account's config.
  It runs as the owner, whose sudo removes both files, checks `sshd -t` and reloads. Or, as the owner:
  `sudo rm /etc/ssh/sshd_config.d/90-charkit-as-owner.conf && sudo systemctl reload ssh`. The owner's own login
  never changed, so nothing else needs undoing. Reloading sshd leaves open sessions and detached jobs alone.
