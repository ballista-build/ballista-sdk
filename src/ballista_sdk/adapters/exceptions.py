class UnknownArtifact(ValueError):
    pass


class UnknownResourceRequirement(ValueError):
    """A Resource need cannot be met because the Resource is unknown."""

    pass


class SettingMissing(ValueError):
    pass
