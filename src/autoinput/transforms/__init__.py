"""Value transforms. Spec syntax in mappings: "name" or "name:arg1,arg2"."""

from collections.abc import Callable

from autoinput.core.registry import Registry
from autoinput.domain import MappingError

TransformFn = Callable[..., str]
transform_registry: Registry[TransformFn] = Registry("transform")
transform = transform_registry.register


def parse_spec(spec: str) -> tuple[str, list[str]]:
    name, _, raw_args = spec.partition(":")
    return name.strip(), raw_args.split(",") if raw_args else []


def apply_transforms(value: str, specs: list[str]) -> str:
    for spec in specs:
        name, args = parse_spec(spec)
        try:
            value = transform_registry.get(name)(value, *args)
        except KeyError as e:
            raise MappingError(str(e)) from e
        except (ValueError, TypeError) as e:
            raise MappingError(f"{name}: {e}") from e
    return value


def validate_specs(specs: list[str]) -> list[str]:
    return [
        f"Unknown transform '{n}'" for n, _ in map(parse_spec, specs) if n not in transform_registry
    ]


from autoinput.transforms import builtins  # noqa: E402, F401 - register built-ins

__all__ = ["apply_transforms", "transform", "transform_registry", "validate_specs"]
