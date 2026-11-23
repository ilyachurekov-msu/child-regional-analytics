"""Versioned contract candidate. Do not rename existing IDs without migration."""

from importlib.resources import files
from uuid import NAMESPACE_URL, uuid5

VERSION = "1.0.0"
SOURCE_UUID_NAMESPACE = NAMESPACE_URL
PLATFORM_AGREED = False


def resource(name):
    if name not in (
        "regions.csv",
        "topics.json",
        "platform.schema.json",
        "manifest.json",
    ):
        raise ValueError("Unknown contract resource")
    return files(__package__).joinpath(name)


def source_uuid(normalized_identifier):
    return uuid5(SOURCE_UUID_NAMESPACE, normalized_identifier)
