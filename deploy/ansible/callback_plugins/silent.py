from ansible import constants as C
from ansible.plugins.callback.default import (
    CallbackModule as DefaultCallback,
    DOCUMENTATION as DEFAULT_DOCUMENTATION,
)

# Reuse default callback's documentation so get_option() works
DOCUMENTATION = DEFAULT_DOCUMENTATION

class CallbackModule(DefaultCallback):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'silent'


    # ----------------------------------+---------------------------------------
    def __init__(self):
        super().__init__()
        self._loop_summary = {}
        self._silent_task_tags = {
            "silent_task_v0": 0,
            "silent_task_v1": 1,
            "silent_task_v2": 2,
            "silent_task_v3": 3,
            }
        self._silent_loop_tags = {
            "silent_loop_v0": 0,
            "silent_loop_v1": 1,
            "silent_loop_v2": 2,
            "silent_loop_v3": 3,
            }


    # ----------------------------------+---------------------------------------
    def _display_ok_header_only(self, result, changed: bool = False):
        # Use the same host labeling as default (includes delegation like "x -> localhost")
        host_label = self.host_label(result)

        # Mimic default coloring
        # (Default uses COLOR_OK for ok and COLOR_CHANGED for changed) 【1-7573b8】
        msg = ("changed: [%s] => [%s]" if changed else "ok: [%s] => [%s]") % (host_label, "Output suppressed by silent tag, increase verbosity to see details")
        color = C.COLOR_CHANGED if changed else C.COLOR_OK

        self._display.display(msg, color=color)


    # ----------------------------------+---------------------------------------
    def _display_item_ok_header_only(self, result, changed: bool = False):
        host_label = self.host_label(result)
        status = "changed" if changed else "ok"
        color = C.COLOR_CHANGED if changed else C.COLOR_OK

        # Default callback uses _get_item_label() for "(item=...)" formatting
        try:
            item_label = self._get_item_label(result._result)
        except Exception:
            item_label = result._result.get("item", None)

        if item_label is None:
            self._display.display(f"{status}: [{host_label}] =>", color=color)
        else:
            self._display.display(f"{status}: [{host_label}] => (item={item_label}) =>", color=color)


    # ----------------------------------+---------------------------------------
    def _silent_level(self, tags, tag_map):
        """Return the min verbosity threshold from matching silent tags, or -1 if none match."""
        levels = [level for tag, level in tag_map.items() if tag in tags]
        return min(levels) if levels else -1


    # ----------------------------------+---------------------------------------
    def v2_playbook_on_task_start(self, task, is_conditional):
        # Let DefaultCallback do its normal caching/state
        super().v2_playbook_on_task_start(task, is_conditional)

        # Force the TASK [...] banner to be shown even if results are silenced
        # Avoid duplicate banners
        if self._last_task_banner != task._uuid:
            self._print_task_banner(task)


    # ----------------------------------+---------------------------------------
    def v2_runner_on_ok(self, result, **kwargs):
        """Called when a task succeeds."""

        tags = set(getattr(result._task, "tags", []) or [])
        verbosity = getattr(self._display, "verbosity", 0)
        required_task_level = self._silent_level(tags, self._silent_task_tags)  # Find which silent tags apply (if any)

        # Check for a loop summary accumulated by v2_runner_item_on_ok/skipped
        task_id = result._task._uuid
        host_name = result._host.get_name()
        summary_key = (task_id, host_name)
        if required_task_level >= 0 and getattr(result._task, "loop", None) and summary_key in self._loop_summary:
            summary = self._loop_summary.pop(summary_key)                       # remove so it doesn't leak into future tasks
            host_label = self.host_label(result)

            # choose color: changed wins
            color = C.COLOR_CHANGED if summary["changed"] > 0 else C.COLOR_OK

            # minimal one-line summary
            msg = f"ok: [{host_label}] => {summary['ok']} ok, {summary['changed']} changed, {summary['skipped']} skipped => Output suppressed by silent tag, increase verbosity to see details"
            self._display.display(msg, color=color)
            return None

        # If no silent tags, behave exactly like default
        if required_task_level < 0:
            return super().v2_runner_on_ok(result, **kwargs)

        if verbosity > required_task_level:
            return super().v2_runner_on_ok(result, **kwargs)

        # Otherwise: print ONLY the header line
        changed = bool(result._result.get("changed", False))
        self._display_ok_header_only(result, changed=changed)

        # else: suppress output by doing nothing
        return None


    # ----------------------------------+---------------------------------------
    def v2_runner_item_on_ok(self, result, **kwargs):
        tags = set(getattr(result._task, "tags", []) or [])
        verbosity = getattr(self._display, "verbosity", 0)
        required_task_level = self._silent_level(tags, self._silent_task_tags)
        required_loop_level = self._silent_level(tags, self._silent_loop_tags)

#
#                   Verbosity levels: Task v1, Loop v2
#                   0       1       2       3
#   Task summary    x       x       -       -           
#   Loop Header     -       -       x       -          
#   Detailsx        -       -       -       x
#
#   if no silent tags:    show everything as normal
#   if verbosity > loop and task:  show everything as normal
#   if verbosity > task and <= loop: show loop header only
#   if verbosity <= task: show task summary only
#

        # No silent tags => default behavior
        if required_task_level < 0 and required_loop_level < 0:
            return super().v2_runner_item_on_ok(result, **kwargs)

        # If verbosity is high enough to show details, show everything as normal
        if verbosity > required_task_level and verbosity > required_loop_level:
            return super().v2_runner_item_on_ok(result, **kwargs)

        # Silent at this verbosity => header-only per loop item
        if verbosity > required_task_level and verbosity <= required_loop_level:
            changed = bool(result._result.get("changed", False))
            self._display_item_ok_header_only(result, changed=changed)
            return None

        # Task Summary
        task_id = result._task._uuid
        host_name = result._host.get_name()
        summary_key = (task_id, host_name)
        r = result._result
        if summary_key not in self._loop_summary:
            self._loop_summary[summary_key] = {
                "ok": 0,
                "changed": 0,
                "skipped": 0,
            }
        if r.get("skipped", False):   self._loop_summary[summary_key]["skipped"] += 1
        elif r.get("changed", False): self._loop_summary[summary_key]["changed"] += 1
        else:                         self._loop_summary[summary_key]["ok"]      += 1

        # suppress per‑item output entirely
        return None


    # ----------------------------------+---------------------------------------
    def v2_runner_item_on_skipped(self, result, **kwargs):
        tags = set(getattr(result._task, "tags", []) or [])
        verbosity = getattr(self._display, "verbosity", 0)
        required_task_level = self._silent_level(tags, self._silent_task_tags)
        required_loop_level = self._silent_level(tags, self._silent_loop_tags)

        if required_loop_level < 0:
            return super().v2_runner_item_on_skipped(result, **kwargs)

        if verbosity > required_task_level and verbosity > required_loop_level:
            return super().v2_runner_item_on_skipped(result, **kwargs)

        # If verbosity is in the "silent loop" range, show header-only for each loop item
        if verbosity > required_task_level and verbosity <= required_loop_level:
            return super().v2_runner_item_on_skipped(result, **kwargs)

        # Task Summary
        task_id = result._task._uuid
        host_name = result._host.get_name()
        summary_key = (task_id, host_name)
        r = result._result
        if summary_key not in self._loop_summary:
            self._loop_summary[summary_key] = {
                "ok": 0,
                "changed": 0,
                "skipped": 0,
            }
        if r.get("skipped", False):   self._loop_summary[summary_key]["skipped"] += 1
        elif r.get("changed", False): self._loop_summary[summary_key]["changed"] += 1
        else:                         self._loop_summary[summary_key]["ok"]      += 1

        # Silent => suppress item-skipped output
        return None


    # ----------------------------------+---------------------------------------
    def v2_runner_on_failed(self, result, ignore_errors=False, **kwargs):
        """Clean up any accumulated loop summary before delegating to default."""
        task_id = result._task._uuid
        host_name = result._host.get_name()
        self._loop_summary.pop((task_id, host_name), None)
        return super().v2_runner_on_failed(result, ignore_errors=ignore_errors, **kwargs)


    # ----------------------------------+---------------------------------------
    def v2_runner_on_unreachable(self, result, **kwargs):
        """Clean up any accumulated loop summary before delegating to default."""
        task_id = result._task._uuid
        host_name = result._host.get_name()
        self._loop_summary.pop((task_id, host_name), None)
        return super().v2_runner_on_unreachable(result, **kwargs)

