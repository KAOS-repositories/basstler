Plan
- Publish to PyPI only from publish.yml; reusable packaging model in basstler-packaging; install from PyPI with a tag-clone fallback.

Done
- publish.yml (PyPI only), LICENSE/NOTICE in every distribution, PyPI-first session start.
- Review round 1 and 2: basstler-packaging (PythonWheel, BuiltRelease, PublishWorkflow, PackageIndex), DistributionFamily in basstler-build, BasstlerFamily in the meta package, TriggerEvent reused, NO_AMBIGUOUS_NAMES rule. Pushed at b3d82143.

Next
- Read CI at b3d82143; the README "by hand" thread is open for the owner.
- Owner: register 13 pending trusted publishers on PyPI and create the pypi environment, then run publish.yml for a tag.
