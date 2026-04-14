# Role: scr_log_upload

Uploads files from a directory on the Ansible controller to Azure Blob Storage using **Managed Identity (MSI)** authentication. Designed as a generic, reusable uploader — not tied to any specific playbook or workflow.

> **For colleagues:** This role is safe to use in your own playbooks without any changes. Point it at your log directory and it will handle the rest. See [Standalone Usage](#standalone-usage) below.

---

## What It Does

1. Scans a directory on the controller for files matching a glob pattern (default: `*.log` and `*.txt`)
2. For each file found, uploads it to Azure Blob Storage under a configurable path prefix
3. Uses `az storage blob upload --auth-mode login` (MSI) — no storage keys or SAS tokens needed
4. Succeeds silently if no files are found (configurable — can be set to fail instead)

---

## File Structure

```
scr_log_upload/
├── defaults/
│   └── main.yaml          ← all configurable variables with defaults
└── tasks/
    ├── main.yaml           ← finds files, loops to upload_logs.yaml
    └── upload_logs.yaml    ← uploads a single file; called in a loop
```

---

## Variables

All variables have defaults in `defaults/main.yaml`. Override any of them via inventory, group vars, or `--extra-vars`.

### Upload Configuration

| Variable | Default | Description |
|---|---|---|
| `scr_log_upload_dir` | `$HOME/scr/logs` | Directory to scan for files (on the controller/localhost) |
| `scr_log_upload_pattern` | `["*.log", "*.txt"]` | List of glob patterns to match; all matched files are uploaded |
| `scr_log_upload_blob_prefix` | `scr-runs/{{ scr_blob_prefix }}logs/` | Blob path prefix; files land at `<container>/<prefix><filename>` |
| `scr_log_upload_content_type` | `text/plain` | MIME type set on each uploaded blob |
| `scr_log_upload_fail_if_none` | `false` | Set to `true` to fail the play when no files are found |

### Azure Connection (inherited from `scr_common` or set directly)

| Variable | Description |
|---|---|
| `scr_azure_storage_account` | Storage account name |
| `scr_azure_container` | Blob container name |
| `scr_auth_mode` | Authentication mode — must be `msi` (key-based auth is disabled on the storage account) |

---

## How to Use

### In the SCR playbook (default usage)

The role is called in `playbook_scr_initialize.yaml` twice:

```yaml
# pre_tasks — upload initial log right after it's written
- name: "Azure - Upload initial log to storage account"
  ansible.builtin.include_role:
    name: roles-scr/scr_log_upload
  run_once: true
  tags: [upload]

# post_tasks — re-upload everything once all hosts finish
- name: "Azure - Upload all logs and discovery reports"
  ansible.builtin.include_role:
    name: roles-scr/scr_log_upload
  run_once: true
  tags: [fetch, upload]
```

The `scr_common` defaults are already loaded via `vars_files:` so no extra variable setup is needed.

---

### Standalone Usage

You can use this role in **any playbook** without the rest of the SCR framework. You just need to provide the Azure connection variables and point it at a directory.

#### Minimal example (MSI, all defaults)

```yaml
- hosts: localhost
  gather_facts: false

  pre_tasks:
    - ansible.builtin.setup:   # required for ansible_env.HOME

  tasks:
    - ansible.builtin.include_role:
        name: roles-scr/scr_log_upload
      vars:
        scr_azure_storage_account: "mystorageaccount"
        scr_azure_container:       "mylogs"
        scr_log_upload_dir:        "/tmp/my_playbook_logs"
```

#### Custom blob prefix per run

```yaml
    - ansible.builtin.include_role:
        name: roles-scr/scr_log_upload
      vars:
        scr_azure_storage_account:  "mystorageaccount"
        scr_azure_container:        "mylogs"
        scr_log_upload_dir:         "/tmp/my_playbook_logs"
        scr_log_upload_blob_prefix: "my-workflow/{{ lookup('pipe', 'date +%Y%m%d-%H%M%S') }}/logs/"
```

#### Upload only `.log` files, fail if none found

```yaml
    - ansible.builtin.include_role:
        name: roles-scr/scr_log_upload
      vars:
        scr_azure_storage_account:   "mystorageaccount"
        scr_azure_container:         "mylogs"
        scr_log_upload_dir:          "/tmp/my_playbook_logs"
        scr_log_upload_pattern:      ["*.log"]
        scr_log_upload_fail_if_none: true
```

#### Upload files of any type

```yaml
      vars:
        scr_log_upload_pattern: ["*.log", "*.txt", "*.json", "*.xml"]
```

---

## Authentication Requirements

This role uses **MSI (Managed Identity)** exclusively. The controller VM's managed identity must have:

| Resource | RBAC Role |
|---|---|
| Storage Account | **Storage Blob Data Contributor** |

No storage account keys, SAS tokens, or client secrets are used. The underlying command is:

```bash
az storage blob upload \
  --account-name <scr_azure_storage_account> \
  --container-name <scr_azure_container> \
  --name <scr_log_upload_blob_prefix><filename> \
  --file <local_path> \
  --overwrite \
  --auth-mode login
```

> **Why CLI instead of the `azure_rm_storageblob` module?**
> The storage account has key-based authentication disabled at the account level (`KeyBasedAuthenticationNotPermitted`). The Ansible `azure_rm_storageblob` module uses key-based auth internally and cannot be overridden to use MSI. The `az` CLI with `--auth-mode login` correctly uses the VM's managed identity token.

---

## Where Files Land in Azure

With the SCR playbook defaults, files are uploaded to:

```
tfstate/
└── scr-runs/
    └── scr/
        └── 2026-03-24T10:30:00/     ← scr_blob_prefix (set per run)
            └── logs/
                ├── scr_initialize.log
                └── scr_discovery_x90app00l5a4_scr_discovery_source_X90_1711276200.txt
```

With a custom `scr_log_upload_blob_prefix`, you control the full path.

---

## Behaviour Notes

- **`run_once: true`** — the role always runs on the controller (`delegate_to: localhost`) regardless of how many hosts are in the play. Setting `run_once: true` at the call site prevents it from being triggered once per host.
- **Overwrite** — existing blobs at the same path are overwritten. This is intentional: calling the role early (initial log) and then again at the end (final log + reports) uses the same blob path, giving you the most up-to-date version.
- **Empty directory** — if `scr_log_upload_fail_if_none` is `false` (the default), the role emits a debug message and exits cleanly. This is the expected behaviour on the very first run before any logs exist.
- **File disappears between find and upload** — the `stat` check in `upload_logs.yaml` guards against race conditions. If a file is removed between the `find` and the upload loop, that file is skipped with a debug message rather than failing.





- name:                     LOG_FUNCTION
  LOG_FUNCTION:
    activity:               [log_summary | log_detail | object | file]
    action:                 [store | retrieve | update | delete] (CRUD)
    payload:                [fact | file_path | var_message]
  vars:
    payload_message:        "string"
    payload_message:      
                            - object1
                            - object2

Function                    Method                                  Object
----------------------      -------------------------------------   -----------------------------------
log_summary                 store                                   string or list of strings
log_detail                  store                                   string or list of strings
object                      [store | retrieve | update | delete]    fact or list of facts
file                        [store | retrieve | update | delete]    file_path or list of file_paths

Calls
------
LOG_TOOL > [LOG_SUMMARY|LOG_DETAIL] > RETURN
LOG_TOOL > [OBJECT|FILE] > LOG_DETAIL > RETURN



