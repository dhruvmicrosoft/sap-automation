# Custom Ansible Callback Plugin Example
# Save this file in callback_plugins/my_callback.py

# from __future__ import (absolute_import, division, print_function)
# __metaclass__ = type

# from ansible.plugins.callback import CallbackBase
from ansible.plugins.callback.default import CallbackModule as DefaultCallback

# DOCUMENTATION = '''
#     callback: silent
#     type: stdout
#     short_description: Custom callback to log task results
#     description:
#         - This callback logs task start, success, and failure events with timestamps.
#     version_added: "2.9"
#     requirements:
#         - None
# '''

class CallbackModule(DefaultCallback):
# class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'stdout'
    CALLBACK_NAME = 'silent'
    
    def __init__(self):
        super(CallbackModule, self).__init__()
        # self.silent = False  # Set to True to suppress output
        self.silent_v0 = 'silent_v0'
        self.silent_v1 = 'silent_v1'
        self.silent_v2 = 'silent_v2'
        self.silent_v3 = 'silent_v3'


    def v2_runner_on_ok(self, result):
        """Called when a task succeeds."""
        # self._display.display(f"[MKD] ✅ Task succeeded: {result._task.get_name()}")
        # Call the original default behavior
        tags = getattr(result._task, 'tags', [])
        # if not self.silent_v1 in tags:
        # if self.silent_v1 in tags and self._display.verbosity > 1:
        if (self.silent_v0 in tags and self._display.verbosity > 0) or \
           (self.silent_v1 in tags and self._display.verbosity > 1) or \
           (self.silent_v2 in tags and self._display.verbosity > 2) or \
           (self.silent_v3 in tags and self._display.verbosity > 3):
            super(CallbackModule, self).v2_runner_on_ok(result)
        elif  not self.silent_v0 in tags and \
              not self.silent_v1 in tags and \
              not self.silent_v2 in tags and \
              not self.silent_v3 in tags:
            super(CallbackModule, self).v2_runner_on_ok(result)

