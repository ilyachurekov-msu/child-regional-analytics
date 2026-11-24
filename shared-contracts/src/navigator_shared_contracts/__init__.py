"""Versioned contract candidate. Do not rename existing IDs without migration."""

from importlib.resources import files
from uuid import NAMESPACE_URL, uuid5
from .identity import canonical_source_uuid

VERSION = "1.0.0"
SOURCE_UUID_NAMESPACE = NAMESPACE_URL
PLATFORM_AGREED = False


def resource(name):
    if name not in (
        "regions.csv",
        "topics.json",
        'topics.csv',
        'source.schema.json',
        "platform.schema.json",
        "manifest.json",
        'topics.csv',
        'source.schema.json',
    ):
        raise ValueError("Unknown contract resource")
    return files(__package__).joinpath(name)


def source_uuid(normalized_identifier):
    """Legacy API retained; canonical_source_uuid(kind,url) is the integration profile."""
    return uuid5(SOURCE_UUID_NAMESPACE, normalized_identifier)


__all__ = ['canonical_source_uuid', 'source_uuid', 'resource', 'VERSION', 'PLATFORM_AGREED']
