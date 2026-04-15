# SCR Roles — Overview

This directory contains all Ansible roles used by the **SAP System Copy and Refresh (SCR)** automation framework. Each role has a single, well-defined responsibility and is designed to be composable — roles call one another rather than duplicating logic.

---

## Directory Structure

```
roles-scr/
├── scr_common/              # Shared configuration and utility task files
├── scr_kernel/              # SAP and DB kernel inventory, compare, and sync
├── scr_keys/                # Azure Key Vault credential retrieval
├── scr_log_function/        # Generic logging and Azure Blob Storage function
└── scr_system_discovery/    # Comprehensive SAP system fact gathering
```

---

## Roles at a Glance

| Role | Purpose | Called As |
|---|---|---|
| `scr_common` | Central defaults file; shared utility tasks | `vars_files:` (defaults) or `include_role tasks_from:` (tasks) |
| `scr_kernel` | SAP and DB kernel inventory, compare, and sync report | `include_role` |
| `scr_keys` | Pulls SSH credentials from Azure Key Vault via MSI | `include_role` |
| `scr_log_function` | Generic log appending and Azure Blob Storage CRUD (summary, detail, object, file) | `include_role` |
| `scr_system_discovery` | Discovers OS, SAP, DB, topology, network, and storage facts on each SAP host | `include_role` |

---

## How They Fit Together

The main entry point is `playbook_scr_initialize.yaml`. Here is the end-to-end flow:

```
playbook_scr_initialize.yaml
│
├── vars_files: scr_common/defaults/main.yaml   ← loads all shared vars
│
├── PRE_TASKS
│   ├── [logging]    Write summary log header; scr_log_function log_summary ← STEP 1-3
│   └── [secrets]    scr_keys  ← pull SSH creds from Key Vault (source + dest)
│
├── TASKS  (runs in parallel across all 4 hosts)
│   ├── [discovery]  scr_system_discovery  ← gather facts on source hosts
│   ├── [discovery]  scr_system_discovery  ← gather facts on dest hosts
│   ├── [kernel]     scr_kernel  ← inventory + compare + sync report
│   └── [fetch]      Fetch per-host reports → controller; scr_log_function log_summary ← STEP 4-9
│
└── POST_TASKS  (runs once, after ALL hosts finish)
    ├── [fetch,upload]  scr_log_function file/store ← upload artifacts to filestore
    └── [cleanup]       scr_keys  ← remove temp SSH key files
```

### Why `pre_tasks` / `tasks` / `post_tasks` layout?

- **`pre_tasks`**: Runs on every host *before* the main task block. Used for setup (log init, credentials) that must complete before discovery starts.
- **`tasks`**: The main parallel work — discovery runs simultaneously on all four SAP hosts (`X90_PAS`, `X90_DB`, `X91_PAS`, `X91_DB`).
- **`post_tasks`**: Runs only *after* every host has finished its `tasks` block. This guarantees all discovery reports are on the controller before the final upload to Azure — no race condition.

---

## Running the Playbook

### Full run (all steps)

```bash
cd /home/azureadm/DHRUV-SCR-TESTING/sap-automation/deploy/ansible

ansible-playbook \
  --inventory x_scr_testing_inventory_X90.yaml \
  --inventory x_scr_testing_inventory_X91.yaml \
  --extra-vars "scr_source_sid=X90 scr_dest_sid=X91" \
  playbook_scr_initialize.yaml
```

### Selective runs using tags

Each step has a tag so you can run only what you need:

| Tag | What it runs |
|---|---|
| `logging` | Step 1 — Write summary log header and log STEP 1 |
| `secrets` | Step 2 — Pull SSH credentials from Azure Key Vault |
| `discovery` | Step 4 — Run system discovery on all SAP hosts |
| `fetch` | Step 5 — Fetch per-host reports, log STEP 4-5 |
| `kernel` | Steps 6-9 — SAP kernel inventory, compare, reports, log STEP 6-9 |
| `upload` | pre_tasks / post_tasks — write and upload summary log, upload artifacts to filestore |
| `cleanup` | Cleanup — Remove temp SSH key files from the controller |
| `always` | Setup tasks that always run regardless of other tags (date/time facts, run_id) |

```bash
# Discovery only
ansible-playbook ... --tags "discovery,fetch"

# Skip cleanup (leave keys in place for debugging)
ansible-playbook ... --skip-tags "cleanup"

# Just upload whatever is already in the log directory
ansible-playbook ... --tags "upload"
```

---

## Authentication

All roles use **MSI (Managed Identity)** — no client secrets or passwords are required. The deployer VM's managed identity must have the following RBAC assignments:

| Resource | Role Required |
|---|---|
| Azure Key Vault (`MKDS1EUS2SAP00user54B`) | Key Vault Secrets User |
| Storage Account (`mkds0eus2tfstate152`) | Storage Blob Data Contributor |

> **Why MSI?** The storage account has key-based authentication disabled (`KeyBasedAuthenticationNotPermitted`). MSI is the only supported auth mode. The `az storage blob upload --auth-mode login` CLI command is used instead of the `azure_rm_storageblob` Ansible module for this reason.

---

## Azure Blob Storage Layout

All SCR artifacts land in the `tfstate` container of `mkds0eus2tfstate152`:

```
tfstate/
└── scr-runs/
    └── <run_id>/                         ← unique per run (ISO8601, set in pre_tasks)
        ├── logs/
        │   ├── <run_id>_summary.log      ← high-level step log (log_summary)
        │   ├── <run_id>_detail.log       ← verbose/diagnostic log (log_detail)
        │   └── <fact_name>.json          ← serialised Ansible facts (object store)
        └── filestore/
            └── <filename>               ← discovery reports, kernel reports, etc.
```

---

## Role READMEs

Each role has its own detailed README:

- [`scr_common/README.md`](scr_common/README.md) — Shared defaults and utility tasks
- [`scr_kernel/readme.md`](scr_kernel/readme.md) — SAP and DB kernel inventory, compare, and sync
- [`scr_log_function/README.md`](scr_log_function/README.md) — Generic logging and Azure Blob Storage function
- [`scr_system_discovery/README.md`](scr_system_discovery/README.md) — SAP system fact discovery

---

## Future Roles (Planned)

| Role | Purpose |
|---|---|
| `scr_parity` | Pre-copy parity validation (OS, SAP kernel, DB kernel) |
| `scr_refresh` | Database refresh orchestration |

The utility task files `scr_common/tasks/build_scr_state.yaml` and `scr_common/tasks/add_step_marker.yaml` are already in place and will be wired up as these future roles are added.
