# Role: scr_log_function

Generic logging and storage function for SCR automation. Replaces `scr_log_upload`.

Call this role from anywhere in a playbook or included task file to append a log line, dump a fact, or push/pull a file — all in one consistent interface.

---

## Calling Convention

```yaml
- name:                                 "LOG - <description>"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           log_summary | log_detail | object | file
    action:                             store | retrieve | update | delete
    payload_message:                    "string"   # or a list
  run_once:                             true       # add when running in a multi-host play
```

---

## Activities and Actions

| Activity | Actions | `payload_message` | Notes |
|---|---|---|---|
| `index` | `register` `update` | register → dict `{ activity, source_sid, dest_sid }` / update → status string | Manages the global run index; `register` sets `scr_run_id` fact |
| `log_summary` | `store` | string or list of strings | Appends timestamped line(s) to `<run_id>_summary.log` and re-uploads it |
| `log_detail` | `store` | string or list of strings | Same but writes to `<run_id>_detail.log` — use for verbose/diagnostic output |
| `log_detail` | `store` | file path(s) with `payload_type: file_content` | Appends raw file content as a named block in the detail log |
| `object` | `store` `retrieve` `update` `delete` | Ansible fact name(s) | Serialises fact to JSON; retrieve loads it back into `result_var` |
| `file` | `store` `retrieve` `update` `delete` | File path(s) on the controller | Pushes/pulls files to/from the `filestore/` prefix in Azure |

---

## Blob Layout in Azure (tfstate container)

```
tfstate/
└── scr-runs/
    ├── scr_global_index.json             ← global run index (all runs, all time)
    └── <run_id>/                         ← e.g. 0001/, 0002/ — set by index/register
        ├── logs/
        │   ├── <run_id>_summary.log      ← high-level step log (log_summary)
        │   └── <run_id>_detail.log       ← verbose log + file content (log_detail)
        ├── objectstore/
        │   └── <fact_name>.json          ← serialised Ansible facts (object store)
        └── filestore/
            └── <filename>               ← on-demand files (file store)
```

---

## Examples

### Register a new SCR run (sets `scr_run_id`)

```yaml
- name:                                 "LOG - Register SCR run"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           index
    action:                             register
    payload_message:
      activity:                         SCR
      source_sid:                       "{{ scr_source_sid }}"
      dest_sid:                         "{{ scr_dest_sid }}"
  run_once:                             true
```

### Mark a run complete (or aborted)

```yaml
- name:                                 "LOG - Mark run completed"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           index
    action:                             update
    payload_message:                    "Completed-Success"   # or Aborted / Completed-Failed
  run_once:                             true
```

### Append a summary log line

```yaml
- name:                                 "LOG - Starting Compare"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           log_summary
    action:                             store
    payload_message:                    "Starting SAP Kernel Compare"
  run_once:                             true
```

### Append multiple lines at once

```yaml
- name:                                 "LOG - Discovery summary"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           log_summary
    action:                             store
    payload_message:
      - "STEP 4 : Discovery completed"
      - "Source  : {{ scr_source_sid }}"
      - "Target  : {{ scr_dest_sid }}"
  run_once:                             true
```

### Store a fact as a JSON blob

```yaml
- name:                                 "LOG - Store kernel sync state"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           object
    action:                             store
    payload_message:                    scr_kernel_sync_state
  run_once:                             true
```

### Retrieve a fact back from Azure

```yaml
- name:                                 "LOG - Retrieve kernel sync state"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           object
    action:                             retrieve
    payload_message:                    scr_kernel_sync_state
    result_var:                         loaded_sync_state
  run_once:                             true
```

### Upload files to filestore

```yaml
- name:                                 "LOG - Store discovery reports"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           file
    action:                             store
    payload_message:
      - "{{ scr_log_dir }}/scr_discovery_source.txt"
      - "{{ scr_log_dir }}/scr_discovery_target.txt"
  run_once:                             true
```

### Retrieve a file from filestore

```yaml
- name:                                 "LOG - Retrieve kernel report"
  ansible.builtin.include_role:
    name:                               roles-scr/scr_log_function
  vars:
    activity:                           file
    action:                             retrieve
    payload_message:                    "kernel_sync_report_X90_to_X91.log"
    result_path:                        "/tmp/restore"
  run_once:                             true
```

---

## File Structure

```
scr_log_function/
├── defaults/
│   └── main.yaml          ← blob prefixes, index blob path, local log dir defaults
└── tasks/
    ├── main.yaml           ← storage account discovery + activity router
    ├── index.yaml          ← global run index CRUD (register / update)
    ├── log_summary.yaml    ← append + upload summary log
    ├── log_detail.yaml     ← append + upload detail log (message or file content)
    ├── object.yaml         ← CRUD on Ansible facts (JSON blobs in objectstore)
    └── file.yaml           ← CRUD on files (filestore blobs)
```

---

## Variables

### Defaults (override via inventory or `--extra-vars`)

| Variable | Default | Description |
|---|---|---|
| `scr_log_function_log_dir` | `$HOME/scr/logs` | Local directory for log files on the controller |
| `scr_log_function_index_blob` | `scr-runs/scr_global_index.json` | Fixed blob path for the global run index |
| `scr_log_function_logs_prefix` | `scr-runs/<run_id>/logs/` | Blob prefix for summary and detail logs |
| `scr_log_function_objectstore_prefix` | `scr-runs/<run_id>/objectstore/` | Blob prefix for serialised Ansible facts |
| `scr_log_function_filestore_prefix` | `scr-runs/<run_id>/filestore/` | Blob prefix for files |

### Required at runtime (from `scr_common` or `--extra-vars`)

| Variable | Description |
|---|---|
| `scr_azure_storage_account` | Storage account name — auto-discovered from `scr_azure_resource_group` if not set |
| `scr_azure_container` | Blob container (default: `tfstate`) |
| `scr_run_id` | Unique run ID; set in playbook `pre_tasks` via `set_fact` |
