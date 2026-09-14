import pytest

from src.shared.base import Base


class DummyDomain(Base):
    """Minimal subclass used only to exercise the Base contract in tests."""

    pass


def test_extract_raises_not_implemented_error() -> None:
    domain = DummyDomain(name="dummy")
    with pytest.raises(NotImplementedError):
        domain.extract()


def test_transform_raises_not_implemented_error() -> None:
    domain = DummyDomain(name="dummy")
    with pytest.raises(NotImplementedError):
        domain.transform()


def test_load_raises_not_implemented_error() -> None:
    domain = DummyDomain(name="dummy")
    with pytest.raises(NotImplementedError):
        domain.load()
